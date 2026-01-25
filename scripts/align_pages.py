#!/usr/bin/env python3
"""
Phase 1: Deskew pages based on black border detection.
Saves deskewed pages for later spine consensus and stitching.
"""

import cv2
import numpy as np
from pathlib import Path
from tqdm import tqdm

def detect_border_angle(img):
    """
    Detect rotation angle from black border lines.
    Returns angle in degrees needed to make borders vertical.
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

        # Near-vertical lines (within 15 degrees)
        if abs(angle) < 15 and length > 200:
            vertical_angles.append(angle)

    if not vertical_angles:
        return 0.0

    return np.median(vertical_angles)

def deskew_image(img, angle):
    """Rotate image to correct skew, expanding canvas to avoid cropping."""
    if abs(angle) < 0.05:
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

    # Use white background for rotation
    rotated = cv2.warpAffine(img, M, (new_w, new_h),
                              borderMode=cv2.BORDER_CONSTANT,
                              borderValue=(255, 255, 255))
    return rotated

def find_content_bounds(img):
    """
    Find the bounding box of actual content (inside white margins).
    Returns (x, y, w, h) or None.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Threshold to find non-white pixels
    _, thresh = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    # Get bounding box of all content
    all_points = np.vstack(contours)
    x, y, w, h = cv2.boundingRect(all_points)

    return (x, y, w, h)

def process_page(input_path, output_path, debug=False):
    """
    Deskew a single page and save it.
    Returns the detected angle.
    """
    img = cv2.imread(str(input_path))
    if img is None:
        print(f"  Error: Could not load {input_path}")
        return None

    # Detect angle
    angle = detect_border_angle(img)

    if debug and abs(angle) > 0.1:
        print(f"  {input_path.name}: angle={angle:.2f}°")

    # Deskew
    deskewed = deskew_image(img, angle)

    # Optionally crop to content bounds (remove excess white space)
    # bounds = find_content_bounds(deskewed)
    # if bounds:
    #     x, y, w, h = bounds
    #     margin = 10
    #     deskewed = deskewed[max(0,y-margin):y+h+margin, max(0,x-margin):x+w+margin]

    # Save
    cv2.imwrite(str(output_path), deskewed)

    return angle

def main():
    input_dir = Path("sources_upscaled")
    output_dir = Path("sources_deskewed")
    output_dir.mkdir(exist_ok=True)

    # Find all pages
    pages = sorted(input_dir.glob("page*_3.0x.png"))
    print(f"Found {len(pages)} pages to process")

    # Process each page
    angles = []
    for page_path in tqdm(pages, desc="Deskewing"):
        output_path = output_dir / page_path.name.replace("_3.0x", "_deskewed")
        angle = process_page(page_path, output_path)
        if angle is not None:
            angles.append(angle)

    # Statistics
    angles = np.array(angles)
    print(f"\nAngle statistics:")
    print(f"  Mean: {np.mean(angles):.2f}°")
    print(f"  Std:  {np.std(angles):.2f}°")
    print(f"  Min:  {np.min(angles):.2f}°")
    print(f"  Max:  {np.max(angles):.2f}°")

    print(f"\nDeskewed pages saved to {output_dir}/")

if __name__ == "__main__":
    main()
