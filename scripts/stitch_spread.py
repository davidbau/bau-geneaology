#!/usr/bin/env python3
"""
Stitch two pages into a spread.
Right page (e.g., 1003) goes on right, left page (e.g., 1004) goes on left.
The spine from the right page's right edge becomes the center.
"""

import cv2
import numpy as np
from pathlib import Path

def detect_border_angle(img):
    """Detect rotation angle from black border lines."""
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
        if abs(angle) < 15 and length > 200:
            vertical_angles.append(angle)

    return np.median(vertical_angles) if vertical_angles else 0.0

def deskew_image(img, angle):
    """Rotate image to correct skew."""
    if abs(angle) < 0.05:
        return img
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos, sin = np.abs(M[0, 0]), np.abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2
    return cv2.warpAffine(img, M, (new_w, new_h),
                          borderMode=cv2.BORDER_CONSTANT,
                          borderValue=(255, 255, 255))

def find_spine_boundary(img, side='right', threshold=200):
    """
    Find where the spine/content boundary is.
    For right page: find where spine starts on right edge
    For left page: find where content starts on left edge
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Look at edge region
    if side == 'right':
        # Scan from right edge inward to find dark vertical line (border)
        for x in range(w - 1, w - 200, -1):
            col = gray[:, x]
            if np.mean(col < threshold) > 0.3:  # Found dark column
                return x
        return w - 100  # Default
    else:
        # Scan from left edge inward
        for x in range(0, 200):
            col = gray[:, x]
            if np.mean(col < threshold) > 0.3:
                return x
        return 100  # Default

def stitch_pages(right_page, left_page, overlap=40):
    """
    Stitch two pages into a spread.
    Layout: [left_page] | [spine/overlap] | [right_page]

    The right page's right edge (spine) becomes the center.
    """
    h1, w1 = left_page.shape[:2]
    h2, w2 = right_page.shape[:2]

    # Find spine boundaries
    # Right page: spine is on the right edge
    right_spine_x = find_spine_boundary(right_page, 'right')
    # Left page: find where to trim on left
    left_trim_x = find_spine_boundary(left_page, 'left')

    print(f"  Right page spine boundary: x={right_spine_x} (width={w2})")
    print(f"  Left page trim boundary: x={left_trim_x}")

    # For now, simple concatenation with small overlap
    # Trim a bit from each edge for clean join
    trim = 20

    # Trim left page's right edge and right page's left edge
    left_trimmed = left_page[:, :w1-trim]
    right_trimmed = right_page[:, trim:]

    # Match heights
    max_h = max(h1, h2)
    if left_trimmed.shape[0] < max_h:
        pad = max_h - left_trimmed.shape[0]
        left_trimmed = cv2.copyMakeBorder(left_trimmed, 0, pad, 0, 0,
                                           cv2.BORDER_CONSTANT, value=(255,255,255))
    if right_trimmed.shape[0] < max_h:
        pad = max_h - right_trimmed.shape[0]
        right_trimmed = cv2.copyMakeBorder(right_trimmed, 0, pad, 0, 0,
                                            cv2.BORDER_CONSTANT, value=(255,255,255))

    # Concatenate
    spread = np.concatenate([left_trimmed, right_trimmed], axis=1)

    return spread

def process_spread(right_path, left_path, output_path):
    """Process a single spread."""
    print(f"Processing: {right_path.name} (right) + {left_path.name} (left)")

    # Load
    right_img = cv2.imread(str(right_path))
    left_img = cv2.imread(str(left_path))

    if right_img is None or left_img is None:
        print(f"  Error loading images")
        return None

    print(f"  Sizes: right={right_img.shape}, left={left_img.shape}")

    # Deskew
    right_angle = detect_border_angle(right_img)
    left_angle = detect_border_angle(left_img)
    print(f"  Angles: right={right_angle:.2f}°, left={left_angle:.2f}°")

    right_deskewed = deskew_image(right_img, right_angle)
    left_deskewed = deskew_image(left_img, left_angle)

    # Stitch
    spread = stitch_pages(right_deskewed, left_deskewed)
    print(f"  Output size: {spread.shape}")

    # Save
    cv2.imwrite(str(output_path), spread)
    print(f"  Saved: {output_path}")

    return spread

def main():
    base_dir = Path("sources_upscaled")
    output_dir = Path("spreads")
    output_dir.mkdir(exist_ok=True)

    # Test with 1003 (right) + 1004 (left)
    right_page = base_dir / "page1003_3.0x.png"
    left_page = base_dir / "page1004_3.0x.png"
    output = output_dir / "spread_1003_1004.png"

    process_spread(right_page, left_page, output)

if __name__ == "__main__":
    main()
