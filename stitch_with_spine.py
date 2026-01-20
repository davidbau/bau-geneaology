#!/usr/bin/env python3
"""
Stitch pages with spine template fill-in.
Aligns based on thin spine border lines and fills missing spine content.
"""

import cv2
import numpy as np
from pathlib import Path

def load_and_scale_spine(spine_path, target_height):
    """Load spine template and scale to match page height."""
    spine = cv2.imread(str(spine_path))
    h, w = spine.shape[:2]
    scale = target_height / h
    new_w = int(w * scale)
    scaled = cv2.resize(spine, (new_w, target_height), interpolation=cv2.INTER_LANCZOS4)
    return scaled, scale

def detect_page_angle(img):
    """
    Detect rotation angle from vertical border lines.
    Returns angle needed to rotate the image to make borders vertical.
    Positive = rotate clockwise, Negative = rotate counter-clockwise.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # High precision Hough transform
    lines = cv2.HoughLines(edges, 1, np.pi/1440, threshold=300)

    if lines is None:
        return 0.0

    vertical_angles = []
    for line in lines[:200]:  # Check first 200 lines
        rho, theta = line[0]
        angle_deg = np.degrees(theta)

        # Near-vertical lines have theta near 0 or near 180
        if angle_deg < 5:
            vertical_angles.append(angle_deg)
        elif angle_deg > 175:
            vertical_angles.append(angle_deg - 180)

    if not vertical_angles:
        return 0.0

    # The median angle tells us how much the lines are tilted from vertical
    # To straighten, we rotate by the negative of this angle
    median_angle = np.median(vertical_angles)
    return median_angle  # Return the angle to correct (rotate by this amount)

def deskew_image(img, angle):
    """Rotate image to correct skew. Rotates by +angle to straighten."""
    if abs(angle) < 0.01:
        return img

    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    # Rotate by the angle to correct the tilt
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    cos, sin = np.abs(M[0, 0]), np.abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2

    return cv2.warpAffine(img, M, (new_w, new_h),
                          borderMode=cv2.BORDER_CONSTANT,
                          borderValue=(255, 255, 255))

def find_top_border(img):
    """Find y-coordinate of top horizontal border line."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    for y in range(min(200, h)):
        row_mean = np.mean(gray[y, :])
        if row_mean < 150:  # Dark row = border
            return y
    return 0

def find_bottom_border(img):
    """Find y-coordinate of bottom horizontal border line."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    for y in range(h - 1, max(h - 200, 0), -1):
        row_mean = np.mean(gray[y, :])
        if row_mean < 150:
            return y
    return h - 1

def find_black_border_edge(img, side, debug=False):
    """
    Find the x-position where the black border starts.
    Distinguishes black border from yellowish paper by looking for
    columns that are truly dark (not just tinted yellow).

    Returns x position of the black border edge.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    # Black pixels have low values; yellow paper has higher values
    # Look for columns where a significant portion is truly dark (< 80)
    dark_threshold = 80

    if side == 'left':
        # Scan from left edge inward to find first column with black border
        for x in range(min(100, w)):
            col = gray[:, x]
            dark_ratio = np.mean(col < dark_threshold)
            if dark_ratio > 0.3:  # 30% of column is dark = black border
                if debug:
                    print(f"    Black border (left) found at x={x}, dark_ratio={dark_ratio:.2f}")
                return x
        return 0
    else:
        # Scan from right edge inward
        for x in range(w - 1, max(w - 100, 0), -1):
            col = gray[:, x]
            dark_ratio = np.mean(col < dark_threshold)
            if dark_ratio > 0.3:
                if debug:
                    print(f"    Black border (right) found at x={x}, dark_ratio={dark_ratio:.2f}")
                return x
        return w - 1

def find_thin_spine_line(img_gray, side, search_start, search_end):
    """
    Find the x-position of the thin vertical spine border line.
    This is the darkest vertical line within the search region.

    Returns (x_position, darkness_value).
    """
    h, w = img_gray.shape

    start = max(0, search_start)
    end = min(w, search_end)
    region = img_gray[:, start:end]
    col_means = np.mean(region, axis=0)
    darkest_local = np.argmin(col_means)
    return start + darkest_local, col_means[darkest_local]

def stitch_with_spine(right_page_path, left_page_path, spine_path, output_path, debug=False):
    """
    Stitch two pages with the spine template filling in the center.

    Layout: [page 1004 (left)] | [spine template] | [page 1003 (right)]

    Alignment: The thin vertical lines in the spine template align with
    the thin vertical lines on each page's spine edge.
    - Spine's left thin line aligns with page 1004's thin line (on its right/spine side)
    - Spine's right thin line aligns with page 1003's thin line (on its left/spine side)

    The spine template already has a 7px margin and extends to image edges.
    Pages are composited on top, with ~7px of yellow paper visible around black borders.
    """
    print(f"Stitching: {right_page_path.name} + {left_page_path.name}")

    # Load pages
    right_img = cv2.imread(str(right_page_path))  # page 1003
    left_img = cv2.imread(str(left_page_path))    # page 1004

    if right_img is None or left_img is None:
        print("Error loading images")
        return None

    print(f"  Page sizes: right(1003)={right_img.shape}, left(1004)={left_img.shape}")

    # Detect and correct tilt
    right_angle = detect_page_angle(right_img)
    left_angle = detect_page_angle(left_img)
    print(f"  Detected angles: right={right_angle:.2f}°, left={left_angle:.2f}°")

    right_img = deskew_image(right_img, right_angle)
    left_img = deskew_image(left_img, left_angle)
    print(f"  After deskew: right={right_img.shape}, left={left_img.shape}")

    right_h, right_w = right_img.shape[:2]
    left_h, left_w = left_img.shape[:2]

    # Find vertical content region (top and bottom borders)
    right_top = find_top_border(right_img)
    right_bottom = find_bottom_border(right_img)
    left_top = find_top_border(left_img)
    left_bottom = find_bottom_border(left_img)
    print(f"  Top/bottom borders: right=[{right_top},{right_bottom}], left=[{left_top},{left_bottom}]")

    # Use the content region height
    right_content_h = right_bottom - right_top
    left_content_h = left_bottom - left_top
    content_h = min(right_content_h, left_content_h)

    # Load and scale spine to match content height
    spine, scale = load_and_scale_spine(spine_path, content_h)
    spine_h, spine_w = spine.shape[:2]
    spine_gray = cv2.cvtColor(spine, cv2.COLOR_BGR2GRAY)
    print(f"  Spine scaled to: {spine_h} x {spine_w} (scale={scale:.3f})")

    # Find thin vertical lines in spine template (both sides)
    spine_left_line_x, _ = find_thin_spine_line(spine_gray, 'left', 5, 25)
    spine_right_line_x, _ = find_thin_spine_line(spine_gray, 'right', spine_w - 25, spine_w - 5)
    print(f"  Spine thin lines: left_x={spine_left_line_x}, right_x={spine_right_line_x}")

    # Find thin vertical lines on pages (on their spine sides)
    right_gray = cv2.cvtColor(right_img, cv2.COLOR_BGR2GRAY)
    left_gray = cv2.cvtColor(left_img, cv2.COLOR_BGR2GRAY)

    # Page 1003 (right page): spine is on LEFT side, find thin line there
    page1003_spine_line_x, _ = find_thin_spine_line(right_gray, 'left', 0, 50)
    # Page 1004 (left page): spine is on RIGHT side, find thin line there
    page1004_spine_line_x, _ = find_thin_spine_line(left_gray, 'right', left_w - 50, left_w)

    print(f"  Page thin lines: 1003(right page) spine_line={page1003_spine_line_x}, 1004(left page) spine_line={page1004_spine_line_x}")

    # Find black border edges on each page (for determining crop with yellow margin)
    # Page 1004: black border on LEFT side (outer edge)
    page1004_black_edge = find_black_border_edge(left_img, 'left', debug)
    # Page 1003: black border on RIGHT side (outer edge)
    page1003_black_edge = find_black_border_edge(right_img, 'right', debug)

    print(f"  Black borders: 1004 left edge={page1004_black_edge}, 1003 right edge={page1003_black_edge}")

    # Calculate output dimensions
    # The spine template defines the height and goes edge-to-edge (no extra margin)
    # Output width: determined by alignment of thin lines

    # Margin of yellow paper to show around black borders
    yellow_margin = 7

    # For page 1004 (left page):
    # - Include from (black_edge - yellow_margin) to spine_line
    # - The spine_line aligns with spine's left thin line
    page1004_start_x = max(0, page1004_black_edge - yellow_margin)
    page1004_end_x = left_w  # Include all the way to right edge (spine side)

    # For page 1003 (right page):
    # - Include from spine_line to (black_edge + yellow_margin)
    # - The spine_line aligns with spine's right thin line
    page1003_start_x = 0  # Include from left edge (spine side)
    page1003_end_x = min(right_w, page1003_black_edge + yellow_margin)

    # Extract content portions (vertical slice between top/bottom borders)
    left_content = left_img[left_top:left_top+content_h, page1004_start_x:page1004_end_x]
    right_content = right_img[right_top:right_top+content_h, page1003_start_x:page1003_end_x]

    left_content_h, left_content_w = left_content.shape[:2]
    right_content_h, right_content_w = right_content.shape[:2]

    print(f"  Content portions: left(1004)={left_content.shape}, right(1003)={right_content.shape}")

    # Calculate alignment offsets
    # Page 1004's thin line (relative to extracted portion) should align with spine's left line
    page1004_line_in_portion = page1004_spine_line_x - page1004_start_x
    # Page 1003's thin line (relative to extracted portion) should align with spine's right line
    page1003_line_in_portion = page1003_spine_line_x - page1003_start_x

    # Output layout:
    # - Page 1004 positioned so its spine line aligns with spine's left line
    # - Spine in the middle
    # - Page 1003 positioned so its spine line aligns with spine's right line

    # Calculate where spine starts in output (page 1004 content goes to the left of this)
    # Page 1004's right edge (spine side) aligns with spine's left edge
    # But we align by thin lines: page1004's thin line = spine's left thin line

    # Position in output where spine's left thin line is:
    # page1004 goes from x=0, its thin line is at x=page1004_line_in_portion
    # So spine's left line should be at x=page1004_line_in_portion
    # Spine starts at x = page1004_line_in_portion - spine_left_line_x

    spine_start_x = page1004_line_in_portion - spine_left_line_x

    # Page 1003 starts where its spine line aligns with spine's right line
    # Spine's right line is at spine_start_x + spine_right_line_x
    # Page 1003's spine line should be at this position
    # So page 1003 starts at (spine_start_x + spine_right_line_x) - page1003_line_in_portion
    page1003_start_in_output = (spine_start_x + spine_right_line_x) - page1003_line_in_portion

    # Total output width
    total_width = max(left_content_w, spine_start_x + spine_w, page1003_start_in_output + right_content_w)
    total_height = spine_h  # Spine defines the height

    print(f"  Alignment: spine_start_x={spine_start_x}, page1003_start={page1003_start_in_output}")
    print(f"  Output: {total_height} x {total_width}")

    # Create output canvas with white background
    output = np.ones((total_height, total_width, 3), dtype=np.uint8) * 255

    # Place spine FIRST (background layer)
    if spine_start_x >= 0 and spine_start_x + spine_w <= total_width:
        output[0:spine_h, spine_start_x:spine_start_x+spine_w] = spine
    else:
        # Handle edge cases with clipping
        src_start = max(0, -spine_start_x)
        src_end = min(spine_w, total_width - spine_start_x)
        dst_start = max(0, spine_start_x)
        dst_end = min(total_width, spine_start_x + spine_w)
        output[0:spine_h, dst_start:dst_end] = spine[:, src_start:src_end]

    # Place page 1004 (left page) ON TOP of spine
    # Composite: only copy non-white pixels (let spine show through white areas)
    left_h = min(total_height, left_content_h)
    left_dst_end = min(total_width, left_content_w)
    left_region = left_content[:left_h, :left_dst_end]
    left_brightness = np.mean(left_region, axis=2)
    left_mask = left_brightness < 245  # Slightly higher threshold
    output[:left_h, :left_dst_end][left_mask] = left_region[left_mask]

    # Place page 1003 (right page) ON TOP of spine
    right_h = min(total_height, right_content_h)
    right_dst_start = max(0, page1003_start_in_output)
    right_src_start = max(0, -page1003_start_in_output)
    right_dst_end = min(total_width, page1003_start_in_output + right_content_w)
    right_src_end = right_src_start + (right_dst_end - right_dst_start)

    right_region = right_content[:right_h, right_src_start:right_src_end]
    right_brightness = np.mean(right_region, axis=2)
    right_mask = right_brightness < 245
    output[:right_h, right_dst_start:right_dst_end][right_mask] = right_region[right_mask]

    if debug:
        cv2.imwrite('debug_spine_scaled.png', spine)
        cv2.imwrite('debug_left_content.png', left_content)
        cv2.imwrite('debug_right_content.png', right_content)

    # Save output
    cv2.imwrite(str(output_path), output)
    print(f"  Saved: {output_path}")

    return output

def main():
    base_dir = Path("sources_upscaled")
    output_dir = Path("spreads")
    output_dir.mkdir(exist_ok=True)

    spine_path = Path("spine_padded.png")

    # Test with pages 1003 (right) + 1004 (left)
    right_page = base_dir / "page1003_3.0x.png"
    left_page = base_dir / "page1004_3.0x.png"
    output = output_dir / "spread_1003_1004.png"

    stitch_with_spine(right_page, left_page, spine_path, output, debug=True)

if __name__ == "__main__":
    main()
