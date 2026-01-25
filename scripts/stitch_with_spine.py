#!/usr/bin/env python3
"""
Stitch pages with spine template fill-in.
Aligns based on thin spine border lines and fills missing spine content.
"""

import cv2
import numpy as np
from pathlib import Path

# Target dimensions for all spreads (height x width)
TARGET_HEIGHT = 1596
TARGET_WIDTH = 2333
YELLOW_MARGIN = 8  # Pixels of yellow paper margin around thick borders

# Spine template properties (unscaled)
SPINE_UNSCALED_HEIGHT = 587
SPINE_UNSCALED_WIDTH = 51
SPINE_LEFT_THIN_LINE = 4   # x position of left thin line in unscaled spine
SPINE_RIGHT_THIN_LINE = 47  # x position of right thin line in unscaled spine

def get_average_yellow_color(img):
    """Get the average yellow/paper color from the margin areas of an image.

    Samples from the margins between the image edge and the black border,
    filtering to only include pixels that are clearly yellowish paper.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Find approximate border positions to sample OUTSIDE the black borders
    # Sample from the outer edge strips where yellow paper should be
    # Use thin strips at very edge where yellow margin should be
    samples = []

    # Top edge strip (first 5 rows)
    samples.append(img[0:5, 20:w-20])
    # Bottom edge strip (last 5 rows)
    samples.append(img[h-5:h, 20:w-20])
    # Left edge strip (first 5 columns, middle vertically)
    samples.append(img[20:h-20, 0:5])
    # Right edge strip (last 5 columns, middle vertically)
    samples.append(img[20:h-20, w-5:w])

    all_samples = np.concatenate([s.reshape(-1, 3) for s in samples], axis=0)

    # Filter to keep only yellowish pixels:
    # - Not too dark (brightness > 180 to exclude black border pixels)
    # - Not pure white (brightness < 245)
    # - Yellowish hue: B channel < G channel (yellow paper has more green than blue)
    brightness = np.mean(all_samples, axis=1)
    b_channel = all_samples[:, 0]
    g_channel = all_samples[:, 1]

    # Brightness filter: exclude dark pixels (black borders) and pure white
    brightness_mask = (brightness > 180) & (brightness < 245)
    # Color filter: yellow paper has B < G (slightly warm tone)
    color_mask = b_channel < g_channel

    mask = brightness_mask & color_mask

    if np.sum(mask) > 0:
        yellow_pixels = all_samples[mask]
        return np.mean(yellow_pixels, axis=0).astype(np.uint8)

    # Fallback: just use brightness filter if color filter finds nothing
    if np.sum(brightness_mask) > 0:
        return np.mean(all_samples[brightness_mask], axis=0).astype(np.uint8)

    return np.array([180, 200, 210], dtype=np.uint8)  # Default yellowish BGR

def tint_spine_yellow(spine, yellow_color):
    """Tint the spine image with yellow color to match page paper."""
    # Calculate how much to darken: white (255) should become yellow_color
    # Multiply each channel by (yellow_color / 255)
    tint_factor = yellow_color.astype(np.float32) / 255.0

    # Apply tint - darken proportionally
    tinted = spine.astype(np.float32)
    for c in range(3):
        tinted[:, :, c] = tinted[:, :, c] * tint_factor[c]

    # Clip to valid range
    tinted = np.clip(tinted, 0, 255).astype(np.uint8)
    return tinted

def load_and_scale_spine(spine_path, yellow_color=None):
    """Load spine template, scale to TARGET_HEIGHT, and optionally tint yellow.

    Returns: (scaled_spine, scale_factor, left_thin_x, right_thin_x)
    where left_thin_x and right_thin_x are positions of thin lines in scaled spine.
    """
    spine = cv2.imread(str(spine_path))
    h, w = spine.shape[:2]

    # Scale to TARGET_HEIGHT + 2 pixels, then crop 1 pixel from top and bottom
    # This ensures exactly 8 pixels of margin after cropping
    scale = (TARGET_HEIGHT + 2) / h
    new_w = int(w * scale)
    scaled = cv2.resize(spine, (new_w, TARGET_HEIGHT + 2), interpolation=cv2.INTER_LANCZOS4)

    # Crop 1 pixel from top and bottom
    scaled = scaled[1:-1, :, :]

    # Tint with yellow color if provided
    if yellow_color is not None:
        scaled = tint_spine_yellow(scaled, yellow_color)

    # Calculate thin line positions in scaled spine
    left_thin_x = int(SPINE_LEFT_THIN_LINE * scale)
    right_thin_x = int(SPINE_RIGHT_THIN_LINE * scale)

    return scaled, scale, left_thin_x, right_thin_x

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
    """Find y-coordinate of top horizontal black border line.
    Returns the first row that is clearly part of the border (not yellow paper).

    The black border should have brightness < 130. We look for the first
    row that drops below this absolute threshold, skipping any gradient
    from deskewing.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Get mean brightness of each row
    row_brightness = np.mean(gray, axis=1)

    # Look for the black border (absolute brightness < 130)
    # The actual black border is very dark (typically 80-120)
    border_threshold = 130

    search_end = min(150, h)
    for y in range(search_end):
        if row_brightness[y] < border_threshold:
            return y

    # Fallback: use relative threshold from the darkest row
    min_brightness = np.min(row_brightness[:search_end])
    threshold = min_brightness + 20
    for y in range(search_end):
        if row_brightness[y] < threshold:
            return y

    return 0

def find_bottom_border(img):
    """Find y-coordinate of bottom horizontal black border line.
    Returns the last row that is clearly part of the border (not yellow paper).

    The black border should have brightness < 130.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Get mean brightness of each row
    row_brightness = np.mean(gray, axis=1)

    # Look for the black border (absolute brightness < 130)
    border_threshold = 130

    search_start = max(0, h - 150)
    for y in range(h - 1, search_start - 1, -1):
        if row_brightness[y] < border_threshold:
            return y

    # Fallback: use relative threshold
    min_brightness = np.min(row_brightness[search_start:])
    threshold = min_brightness + 20
    for y in range(h - 1, search_start - 1, -1):
        if row_brightness[y] < threshold:
            return y

    return h - 1

def find_black_border_edge(img, side, debug=False):
    """
    Find the x-position where the black border starts.
    Uses brightness profile to find the transition between yellow paper and border.
    Uses a tighter threshold to be more generous with yellow margin.

    Returns x position of the black border edge.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    # Get mean brightness of each column
    col_brightness = np.mean(gray, axis=0)

    if side == 'left':
        # Scan leftmost region, find the darkest column
        search_end = min(100, w)
        region = col_brightness[:search_end]
        min_brightness = np.min(region)
        # Tighter threshold (min + 20 instead of + 30) = more generous margin
        threshold = min_brightness + 20
        for x in range(search_end):
            if col_brightness[x] < threshold:
                if debug:
                    print(f"    Black border (left) at x={x}, brightness={col_brightness[x]:.0f}, threshold={threshold:.0f}")
                return x
        return 0
    else:
        # Scan rightmost region
        search_start = max(0, w - 100)
        region = col_brightness[search_start:]
        min_brightness = np.min(region)
        # Tighter threshold = more generous margin
        threshold = min_brightness + 20
        for x in range(w - 1, search_start - 1, -1):
            if col_brightness[x] < threshold:
                if debug:
                    print(f"    Black border (right) at x={x}, brightness={col_brightness[x]:.0f}, threshold={threshold:.0f}")
                return x
        return w - 1

def find_thin_spine_line(img_gray, side, search_start, search_end):
    """
    Find the x-position of the thin vertical spine border line.

    Strategy:
    1. Look for a clear thin line (very dark column < 145 brightness)
    2. If no clear thin line, find the transition from yellow to darker content

    Returns (x_position, darkness_value).
    """
    h, w = img_gray.shape

    start = max(0, search_start)
    end = min(w, search_end)
    col_means = np.mean(img_gray[:, start:end], axis=0)

    # First, look for a clear thin line (brightness < 145)
    # This should be surrounded by brighter pixels
    thin_line_threshold = 145
    candidates = []
    for i in range(5, len(col_means) - 5):
        if col_means[i] < thin_line_threshold:
            # Check if surrounded by brighter pixels
            left_bright = np.mean(col_means[max(0, i-5):i]) > 160
            right_bright = np.mean(col_means[i+1:min(len(col_means), i+6)]) > 160
            if left_bright or right_bright:
                candidates.append((i, col_means[i]))

    if candidates:
        # Use the darkest candidate
        candidates.sort(key=lambda x: x[1])
        best_idx, best_val = candidates[0]
        return start + best_idx, best_val

    # No clear thin line found - use the darkest column in the search region
    # but bias toward columns that are near transitions (not at the very edge)
    darkest_local = np.argmin(col_means)
    return start + darkest_local, col_means[darkest_local]

def stitch_with_spine(right_page_path, left_page_path, spine_path, output_path, debug=False):
    """
    Stitch two pages with the spine template filling in the center.

    Layout: [left page] | [spine template] | [right page]

    The spine is placed at a FIXED center position in the TARGET output.
    Each page is transformed (deskewed + scaled) to:
    - Align its thin border with the spine's thin border
    - Place its thick border at exactly YELLOW_MARGIN pixels from the edge
    """
    print(f"Stitching: {right_page_path.name} + {left_page_path.name}")

    # Load pages
    right_img = cv2.imread(str(right_page_path))
    left_img = cv2.imread(str(left_page_path))

    if right_img is None or left_img is None:
        print("Error loading images")
        return None

    # Get average yellow color from the page margins to tint the spine
    yellow_left = get_average_yellow_color(left_img)
    yellow_right = get_average_yellow_color(right_img)
    yellow_color = ((yellow_left.astype(np.int32) + yellow_right.astype(np.int32)) // 2).astype(np.uint8)
    print(f"  Yellow color (BGR): {yellow_color}")

    # Load spine scaled to TARGET_HEIGHT, get thin line positions
    spine, spine_scale, spine_left_thin, spine_right_thin = load_and_scale_spine(spine_path, yellow_color)
    spine_h, spine_w = spine.shape[:2]
    print(f"  Spine: {spine_h}x{spine_w}, thin lines at x={spine_left_thin},{spine_right_thin}")

    # Calculate fixed spine position (centered in output)
    spine_start_x = (TARGET_WIDTH - spine_w) // 2
    spine_left_thin_in_output = spine_start_x + spine_left_thin
    spine_right_thin_in_output = spine_start_x + spine_right_thin
    print(f"  Spine position: x={spine_start_x} to {spine_start_x + spine_w}")
    print(f"  Spine thin lines in output: left={spine_left_thin_in_output}, right={spine_right_thin_in_output}")

    # Create output canvas
    output = np.ones((TARGET_HEIGHT, TARGET_WIDTH, 3), dtype=np.uint8) * 255

    # Place spine in center (background layer)
    output[:spine_h, spine_start_x:spine_start_x+spine_w] = spine

    # Process each page
    for page_img, page_name, is_right_page in [
        (right_img, "right", True),
        (left_img, "left", False)
    ]:
        # Detect and correct tilt
        angle = detect_page_angle(page_img)
        page_img = deskew_image(page_img, angle)
        h, w = page_img.shape[:2]
        gray = cv2.cvtColor(page_img, cv2.COLOR_BGR2GRAY)

        # Find borders
        top_border = find_top_border(page_img)
        bottom_border = find_bottom_border(page_img)

        if is_right_page:
            # Right page: spine on LEFT, outer border on RIGHT
            thin_line_x, _ = find_thin_spine_line(gray, 'left', 0, 60)
            thick_border_x = find_black_border_edge(page_img, 'right', debug)
            target_thin_x = spine_right_thin_in_output
            target_thick_x = TARGET_WIDTH - YELLOW_MARGIN
        else:
            # Left page: spine on RIGHT, outer border on LEFT
            thin_line_x, _ = find_thin_spine_line(gray, 'right', w - 60, w)
            thick_border_x = find_black_border_edge(page_img, 'left', debug)
            target_thin_x = spine_left_thin_in_output
            target_thick_x = YELLOW_MARGIN

        print(f"  {page_name.capitalize()} page: angle={angle:.2f}°, thin_line={thin_line_x}, thick_border={thick_border_x}")
        print(f"    top/bottom borders: [{top_border}, {bottom_border}]")

        # Calculate vertical scale: fit content between margins
        page_content_h = bottom_border - top_border
        target_content_h = TARGET_HEIGHT - 2 * YELLOW_MARGIN
        scale_y = target_content_h / page_content_h

        # Calculate horizontal scale: align thin line AND place thick border at margin
        if is_right_page:
            # Distance from thin line to thick border in source
            src_span = thick_border_x - thin_line_x
            # Distance from target thin line to target thick border
            dst_span = target_thick_x - target_thin_x
        else:
            # Distance from thick border to thin line in source
            src_span = thin_line_x - thick_border_x
            # Distance from target thick border to target thin line
            dst_span = target_thin_x - target_thick_x

        scale_x = dst_span / src_span if src_span > 0 else 1.0

        print(f"    Scale: x={scale_x:.4f}, y={scale_y:.4f}")

        # Extract the content region (with margin for yellow paper)
        src_top = max(0, top_border - int(YELLOW_MARGIN / scale_y))
        src_bottom = min(h, bottom_border + int(YELLOW_MARGIN / scale_y))

        if is_right_page:
            # Include from left edge (thin line side) to thick border + margin
            src_left = 0
            src_right = min(w, thick_border_x + int(YELLOW_MARGIN / scale_x))
        else:
            # Include from thick border - margin to right edge (thin line side)
            src_left = max(0, thick_border_x - int(YELLOW_MARGIN / scale_x))
            src_right = w

        content = page_img[src_top:src_bottom, src_left:src_right]

        # Scale the content
        new_h = int(content.shape[0] * scale_y)
        new_w = int(content.shape[1] * scale_x)
        scaled = cv2.resize(content, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

        # Calculate placement in output
        # The thin line position after scaling
        if is_right_page:
            scaled_thin_x = int((thin_line_x - src_left) * scale_x)
            # Place so thin line aligns with target
            dst_x = target_thin_x - scaled_thin_x
        else:
            scaled_thin_x = int((thin_line_x - src_left) * scale_x)
            dst_x = target_thin_x - scaled_thin_x

        # Vertical: center the content
        scaled_top_border = int((top_border - src_top) * scale_y)
        dst_y = YELLOW_MARGIN - scaled_top_border

        print(f"    Scaled size: {new_h}x{new_w}, placement: ({dst_y}, {dst_x})")

        # Composite onto output (non-white pixels overlay)
        for sy in range(new_h):
            dy = dst_y + sy
            if dy < 0 or dy >= TARGET_HEIGHT:
                continue
            for sx in range(new_w):
                dx = dst_x + sx
                if dx < 0 or dx >= TARGET_WIDTH:
                    continue
                pixel = scaled[sy, sx]
                if np.mean(pixel) < 245:  # Not white
                    output[dy, dx] = pixel

    if debug:
        cv2.imwrite('debug_spine_scaled.png', spine)

    # Save output
    cv2.imwrite(str(output_path), output)
    print(f"  Saved: {output_path} ({TARGET_HEIGHT}x{TARGET_WIDTH})")

    return output

def main():
    base_dir = Path("sources_upscaled")
    output_dir = Path("spreads")
    output_dir.mkdir(exist_ok=True)

    spine_path = Path("spine_padded.png")

    # Process multiple page pairs
    # In Chinese right-to-left order: odd page (right) + even page (left)
    page_pairs = [
        (1003, 1004),
        (1005, 1006),
        (1007, 1008),
        (1009, 1010),
        (1011, 1012),
        (1013, 1014),
        (1015, 1016),
        (1017, 1018),
        (1019, 1020),
        (1021, 1022),
        (1023, 1024),
    ]

    for right_num, left_num in page_pairs:
        right_page = base_dir / f"page{right_num}_3.0x.png"
        left_page = base_dir / f"page{left_num}_3.0x.png"
        output = output_dir / f"spread_{right_num}_{left_num}.png"

        if not right_page.exists():
            print(f"Skipping: {right_page.name} not found")
            continue
        if not left_page.exists():
            print(f"Skipping: {left_page.name} not found")
            continue

        stitch_with_spine(right_page, left_page, spine_path, output, debug=False)
        print()

if __name__ == "__main__":
    main()
