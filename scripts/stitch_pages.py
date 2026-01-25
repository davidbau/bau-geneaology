#!/usr/bin/env python3
"""
Deskewing and stitching genealogy page spreads.
Uses black border detection for rotation angle.
Aligns spine regions for seamless stitching.
"""

import cv2
import numpy as np
from pathlib import Path

def load_image(path):
    """Load image as BGR."""
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"Could not load {path}")
    return img

def detect_border_angle(img, debug=False):
    """
    Detect the rotation angle from black border lines.
    Returns angle in degrees (positive = clockwise rotation needed).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100,
                            minLineLength=100, maxLineGap=10)

    if lines is None:
        return 0.0

    vertical_angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        length = np.sqrt((x2-x1)**2 + (y2-y1)**2)

        if abs(x2 - x1) < 1:
            angle = 0
        else:
            angle = np.degrees(np.arctan2(x2 - x1, y2 - y1))

        if abs(angle) < 10 and length > 200:
            vertical_angles.append(angle)

    if not vertical_angles:
        return 0.0

    median_angle = np.median(vertical_angles)

    if debug:
        print(f"  Found {len(vertical_angles)} vertical lines, median angle: {median_angle:.2f}°")

    return median_angle

def deskew_image(img, angle):
    """Rotate image to correct skew."""
    if abs(angle) < 0.1:
        return img

    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)

    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2

    rotated = cv2.warpAffine(img, M, (new_w, new_h),
                              borderMode=cv2.BORDER_CONSTANT,
                              borderValue=(255, 255, 255))
    return rotated

def find_spine_edge(img, side='right', debug=False):
    """
    Find the spine edge of a page.
    side='right' means spine is on right edge (for right pages)
    side='left' means spine is on left edge (for left pages)

    Returns x-coordinate of spine edge.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Look for the spine region - it has vertical text and a distinctive pattern
    # The spine is typically at the very edge of the page

    if side == 'right':
        # Look at right 20% of image for the spine
        spine_region = gray[:, int(w * 0.8):]
        offset = int(w * 0.8)
    else:
        # Look at left 20% of image
        spine_region = gray[:, :int(w * 0.2)]
        offset = 0

    # Find dark vertical lines in spine region (the spine text)
    edges = cv2.Canny(spine_region, 50, 150)

    # Find the innermost edge of significant content
    col_sums = np.sum(edges, axis=0)

    # Find where content starts/ends
    threshold = np.max(col_sums) * 0.1

    if side == 'right':
        # Find rightmost significant content
        significant = np.where(col_sums > threshold)[0]
        if len(significant) > 0:
            spine_x = offset + significant[-1]
        else:
            spine_x = w
    else:
        # Find leftmost significant content
        significant = np.where(col_sums > threshold)[0]
        if len(significant) > 0:
            spine_x = offset + significant[0]
        else:
            spine_x = 0

    if debug:
        print(f"  Spine edge ({side}): x={spine_x}")

    return spine_x

def extract_spine_strip(img, side, width=80):
    """Extract the spine strip from the edge of the page."""
    h, w = img.shape[:2]

    if side == 'right':
        return img[:, w-width:w]
    else:
        return img[:, 0:width]

def align_spines_vertically(left_spine, right_spine, debug=False):
    """
    Find vertical offset to align spine strips.
    Returns y_offset to shift left_spine relative to right_spine.
    """
    # Convert to grayscale
    left_gray = cv2.cvtColor(left_spine, cv2.COLOR_BGR2GRAY)
    right_gray = cv2.cvtColor(right_spine, cv2.COLOR_BGR2GRAY)

    # Use template matching to find best vertical alignment
    # Pad right spine to allow for shifts
    h1, w1 = left_gray.shape
    h2, w2 = right_gray.shape

    # Take middle portion of each spine for matching
    margin = min(h1, h2) // 4
    left_template = left_gray[margin:-margin, :]
    right_search = right_gray

    # Match template
    result = cv2.matchTemplate(right_search, left_template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    # Calculate offset
    y_offset = margin - max_loc[1]

    if debug:
        print(f"  Spine alignment: y_offset={y_offset}, match_score={max_val:.3f}")

    return y_offset, max_val

def stitch_spread(left_page, right_page, spine_width=60, debug=False):
    """
    Stitch two pages into a spread with aligned spines.
    left_page goes on the left, right_page goes on the right.
    """
    h1, w1 = left_page.shape[:2]
    h2, w2 = right_page.shape[:2]

    # Extract spine strips for alignment
    left_spine = extract_spine_strip(left_page, 'left', spine_width)
    right_spine = extract_spine_strip(right_page, 'right', spine_width)

    # Find vertical alignment
    y_offset, match_score = align_spines_vertically(left_spine, right_spine, debug=debug)

    # Calculate output dimensions
    max_h = max(h1, h2) + abs(y_offset)

    # Create output canvas
    spread = np.ones((max_h, w1 + w2 - spine_width, 3), dtype=np.uint8) * 255

    # Calculate placement positions
    if y_offset >= 0:
        left_y = y_offset
        right_y = 0
    else:
        left_y = 0
        right_y = -y_offset

    # Place left page (excluding spine overlap region)
    spread[left_y:left_y+h1, 0:w1-spine_width//2] = left_page[:, 0:w1-spine_width//2]

    # Place right page (excluding spine overlap region)
    spread[right_y:right_y+h2, w1-spine_width//2:w1-spine_width//2+w2] = right_page

    # Blend the spine region
    blend_width = spine_width
    blend_start = w1 - spine_width
    blend_end = w1

    for x in range(blend_width):
        alpha = x / blend_width  # 0 to 1

        left_x = w1 - spine_width + x
        right_x = x

        if left_x < w1 and right_x < w2:
            left_col = left_page[max(0, -y_offset):min(h1, max_h-max(0,y_offset)), left_x:left_x+1]
            right_col = right_page[max(0, y_offset):min(h2, max_h-max(0,-y_offset)), right_x:right_x+1]

            # Resize if needed
            target_h = min(left_col.shape[0], right_col.shape[0])
            if target_h > 0:
                left_col = left_col[:target_h]
                right_col = right_col[:target_h]

                blended = cv2.addWeighted(left_col, 1-alpha, right_col, alpha, 0)

                out_y_start = max(left_y, right_y)
                spread[out_y_start:out_y_start+target_h, blend_start+x:blend_start+x+1] = blended

    return spread

def process_spread(right_page_path, left_page_path, output_path, debug=False):
    """
    Process a two-page spread:
    1. Load both pages
    2. Detect rotation from borders
    3. Deskew both
    4. Stitch together with spine alignment
    """
    print(f"Processing: {right_page_path.name} + {left_page_path.name}")

    # Load images
    right_img = load_image(right_page_path)
    left_img = load_image(left_page_path)

    if debug:
        print(f"  Sizes: right={right_img.shape}, left={left_img.shape}")

    # Detect and apply rotation
    right_angle = detect_border_angle(right_img, debug=debug)
    left_angle = detect_border_angle(left_img, debug=debug)

    right_deskewed = deskew_image(right_img, right_angle)
    left_deskewed = deskew_image(left_img, left_angle)

    # Stitch with spine alignment
    spread = stitch_spread(left_deskewed, right_deskewed, spine_width=80, debug=debug)

    if debug:
        print(f"  Output size: {spread.shape}")

    # Save
    cv2.imwrite(str(output_path), spread)
    print(f"  Saved: {output_path}")

    return spread

def main():
    base_dir = Path("sources_upscaled")
    output_dir = Path("spreads")
    output_dir.mkdir(exist_ok=True)

    # Test with pages 1003 (right) and 1004 (left)
    right_page = base_dir / "page1003_3.0x.png"
    left_page = base_dir / "page1004_3.0x.png"
    output = output_dir / "spread_1003_1004.png"

    process_spread(right_page, left_page, output, debug=True)

if __name__ == "__main__":
    main()
