#!/usr/bin/env python3
"""
Test PaddleOCR on a restored genealogy image.
"""

import json
from paddleocr import PaddleOCR

# Initialize OCR - disable document preprocessing
ocr = PaddleOCR(
    lang='ch',
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)

# Test on one image
img_path = 'sources_upscaled/page1000_3.0x.png'

print(f"Processing: {img_path}")
print("=" * 60)

result = ocr.predict(img_path)

if result and len(result) > 0:
    ocr_result = result[0]

    texts = ocr_result.get('rec_texts', [])
    scores = ocr_result.get('rec_scores', [])
    polys = ocr_result.get('dt_polys', [])

    print(f"\nDetected {len(texts)} text regions")
    print("-" * 60)

    output = []
    for i, (text, score, poly) in enumerate(zip(texts, scores, polys)):
        # Get bounding box from polygon
        poly_list = poly.tolist() if hasattr(poly, 'tolist') else list(poly)
        xs = [p[0] for p in poly_list]
        ys = [p[1] for p in poly_list]
        bbox = {
            'x_min': min(xs),
            'y_min': min(ys),
            'x_max': max(xs),
            'y_max': max(ys)
        }

        # Estimate character positions (interpolate along text line)
        num_chars = len(text)
        char_positions = []
        if num_chars > 0:
            # Determine if vertical or horizontal based on aspect ratio
            width = bbox['x_max'] - bbox['x_min']
            height = bbox['y_max'] - bbox['y_min']

            for j, char in enumerate(text):
                if height > width:  # Vertical text
                    char_y = bbox['y_min'] + height * (j + 0.5) / num_chars
                    char_x = (bbox['x_min'] + bbox['x_max']) / 2
                else:  # Horizontal text
                    char_x = bbox['x_min'] + width * (j + 0.5) / num_chars
                    char_y = (bbox['y_min'] + bbox['y_max']) / 2

                char_positions.append({
                    'char': char,
                    'x': int(char_x),
                    'y': int(char_y)
                })

        print(f"\n[{i+1}] Text: {text}")
        print(f"     Score: {score:.3f}")
        print(f"     BBox: ({bbox['x_min']}, {bbox['y_min']}) - ({bbox['x_max']}, {bbox['y_max']})")
        print(f"     Orientation: {'vertical' if bbox['y_max'] - bbox['y_min'] > bbox['x_max'] - bbox['x_min'] else 'horizontal'}")
        if len(char_positions) <= 10:
            for cp in char_positions:
                print(f"       '{cp['char']}' at ({cp['x']}, {cp['y']})")
        else:
            print(f"       First 5 chars: {char_positions[:5]}")
            print(f"       Last 5 chars: {char_positions[-5:]}")

        output.append({
            'text': text,
            'score': float(score),
            'polygon': poly_list,
            'bbox': bbox,
            'char_positions': char_positions
        })

    # Save to JSON
    with open('ocr_result.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n\nResults saved to ocr_result.json")
else:
    print("No results returned")
