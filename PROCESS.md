# Process: Creating an Interactive Aligned Transcription

This document describes the workflow used to create an interactive, aligned transcription of the Chinese genealogical document 鮑公恆齋生壙志 (Burial Record of Mr. Bao Hengzhai).

## Overview

The goal was to create a scholarly interactive reader that:
1. Overlays transcribed text precisely on the original document image
2. Provides contextual translations at three levels: character, phrase, and section
3. Allows users to blend between the original image and the transcription overlay
4. Preserves the visual relationship between transcription and source

## Workflow

### Step 1: Initial Segmentation by Hand

The human operator visually identified columns of text in the original image. Traditional Chinese documents are read top-to-bottom, right-to-left, but the layout of this document includes:

- **Main biographical text**: 10+ columns in the center-right
- **Book spine**: Large characters on the left edge
- **Attribution block**: Author/calligrapher credits on the right
- **Feng shui poetry**: Additional columns describing the burial site

Each visual column was identified and its approximate position noted.

### Step 2: OCR with Gemini

For each identified column segment, the image region was fed to Google's Gemini model, which has superior OCR capabilities for classical Chinese text. The process was iterative:

1. Provide Gemini with the image segment
2. Request transcription of the characters
3. Gemini returns the character sequence with pinyin and initial translation
4. Human reviews for obvious errors

**Key advantage of Gemini**: It can read degraded, stylized, or partially obscured classical Chinese characters that other OCR systems struggle with.

### Step 3: Initial Placement in Code

Each transcribed column was added to the `textLayout` array with initial position estimates:

```javascript
{ chars: '鮑公恆齋生壙志', x: 0, y: 0, size: 16, spacing: 1.14, type: 'title' }
```

The parameters are:
- `chars`: The transcribed character sequence
- `x`, `y`: Pixel offset for positioning
- `size`: Font size in pixels
- `spacing`: Line-height multiplier for vertical character spacing

### Step 4: Visual Alignment with Sliders

A set of alignment controls was temporarily added to the interface:

```javascript
// Alignment Controls - targets specific column index
const ALIGN_COL_INDEX = 0; // Change this to align different segments

// Sliders for: X position, Y position, Font size, Line spacing
```

The human operator would:
1. Set `ALIGN_COL_INDEX` to the column being aligned
2. Use sliders to adjust x, y, size, and spacing in real-time
3. Visually match the overlay to the original characters
4. Record the final values

### Step 5: Error Detection During Alignment

**Critical insight**: The alignment process reveals transcription errors.

When a character doesn't align properly despite correct surrounding characters, it indicates:
- A missing character in the transcription
- An incorrect character
- A character that doesn't exist in the original

**Example corrections made**:
- Removed 酉 which didn't appear in the original feng shui text
- Split 向兼 into separate positioned elements (they were visually separated)
- Added missing character 蔭 between 當 and 其
- Corrected 翼和鳴鏘 to 翼翼和鳴鏘鏘 (reduplicated characters)

### Step 6: Iterative Refinement

The workflow cycled between:
```
Transcribe → Align → Spot errors → Correct → Re-align
```

Gemini was re-consulted when alignment revealed problems, providing updated transcriptions based on closer examination.

### Step 7: Scholarly Annotation

Once alignment was complete, the transcription was organized into:

1. **Sections**: Major document divisions with scholarly explanations
2. **Phrases**: Meaningful units with translations and historical notes
3. **Characters**: Individual characters with pinyin, meaning, and context

This hierarchical structure enables the three-level hover display in the final interface.

### Step 8: Final Interface

The alignment controls were removed and replaced with:
- Single opacity slider (0 = original only, 100 = transcription only)
- Three-level information panel (section → phrase → character)
- Click-to-lock functionality for detailed examination
- Color-coded outline highlighting

## Technical Details

### Positioning System

Characters are positioned using CSS transforms:
```css
.column {
    transform: translate(${x}px, ${y}px);
}
```

The `flex-direction: row-reverse` layout means columns are added left-to-right in the array but displayed right-to-left (matching traditional Chinese reading order).

### Opacity Blending

The single slider controls both:
- Original image opacity: `1 - value`
- Text overlay opacity: `value`

At 50%, both are visible and blended. At 0%, only the original shows. At 100%, only the transcription shows.

### Character Data Structure

```javascript
const characterData = {
    '鮑': {
        pinyin: 'bào',
        meaning: 'Surname Bao; salted fish',
        context: 'The family surname. The Bao clan was prominent in the Ningbo region.'
    },
    // ...
};
```

## Lessons Learned

1. **Human-AI collaboration is essential**: Gemini provides excellent OCR, but human visual alignment catches errors that pure text comparison misses.

2. **Alignment reveals truth**: When characters don't fit, the transcription is wrong. This is a powerful verification method.

3. **Iterative refinement works**: Multiple passes, each improving accuracy, produce better results than attempting perfection in one pass.

4. **Position data is precious**: Once alignment is achieved, the x/y/size/spacing values should be preserved carefully.

## Future Automation Possibilities

This workflow could potentially be automated:

1. **Automatic column detection**: Computer vision to identify text columns
2. **Batch OCR**: Send all columns to Gemini in one request
3. **Automatic initial placement**: Estimate positions from column detection
4. **Assisted alignment**: ML model to suggest fine adjustments
5. **Error detection**: Flag characters where alignment confidence is low

The key challenge is the alignment verification step, which currently requires human visual judgment. A future system might use image comparison metrics to score alignment quality and flag problem areas for human review.

## Credits

- **Document**: 鮑公恆齋生壙志 from 句俞鮑氏宗譜 (Bao Clan Genealogy of Gouyu), Volume 6
- **Original Author**: Zhang Meiyi (張美翊, 1856-1924)
- **OCR Assistance**: Google Gemini
- **Alignment and Annotation**: Human-AI collaboration using Claude
- **Interactive Interface**: HTML/CSS/JavaScript
