# Automation Plan: Genealogical Document Reader Pipeline

This document describes a plan to automate the creation of interactive aligned transcriptions for traditional Chinese genealogical documents, building on the manual workflow documented in [PROCESS.md](PROCESS.md).

---

## Background: Lessons from Manual Process

Our manual workflow (PROCESS.md) revealed critical insights for automation:

1. **Alignment-as-verification**: When transcribed characters don't align visually with the original, the transcription is wrong. This is the key quality signal.

2. **Iterative refinement**: The cycle `Transcribe → Align → Spot errors → Correct → Re-align` produces better results than single-pass processing.

3. **Error types detected by alignment**:
   - Missing characters (subsequent characters shift up)
   - Incorrect characters (visual mismatch at that position)
   - Extra characters (subsequent characters shift down)
   - Reduplicated characters missed (e.g., 翼翼 transcribed as 翼)

4. **Multi-region complexity**: Documents contain different region types (main text, spine, credits, titles) with different fonts and layouts.

---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    INPUT: Document Scan                          │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1: PREPROCESSING                                          │
│  Deskew, denoise, contrast enhancement, resolution normalize     │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2: LAYOUT ANALYSIS                                        │
│  Detect regions → Classify types → Find columns → Reading order  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3: MULTI-PASS OCR                                         │
│  Gemini primary → Secondary validation → Consensus + confidence  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 4: ALIGNMENT VERIFICATION (Key Innovation)                │
│  Render overlay → Per-character similarity → Anomaly detection   │
│  → Iterative correction loop                                     │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 5: SCHOLARLY ANNOTATION                                   │
│  Character lookup → Phrase segmentation → Section classification │
│  → Historical RAG for accuracy                                   │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 6: APP GENERATION                                         │
│  Template rendering → Data embedding → Quality report            │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│           OUTPUT: Interactive Reader + Quality Report            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Preprocessing

### Purpose
Normalize image quality for optimal OCR and alignment.

### Operations
1. **Deskewing**: Correct rotation using Hough transform or learned models
2. **Binarization**: Adaptive thresholding (Sauvola method for aged documents)
3. **Denoising**: Remove artifacts while preserving stroke edges
4. **Resolution normalization**: Target 300-400 DPI for Chinese text

### Technology
- OpenCV for basic transforms
- DocTR or LayoutLMv3 for learned deskewing

---

## Stage 2: Layout Analysis

### Purpose
Identify text regions, classify them, detect columns, determine reading order.

### Region Types (from our document)
| Type | Example | Characteristics |
|------|---------|-----------------|
| `main_text` | Biographical columns | Size 16, spacing 1.14, vertical |
| `title` | 鮑公恆齋生壙志 | Bold, bordered, larger spacing |
| `spine` | 句俞鮑氏宗譜 卷六 | Large font (28px), left edge |
| `credits` | 同邑張美翊撰文 | Right side, attribution |

### Algorithm
```
1. Detect all text regions using deep learning
2. Classify each region by visual features
3. For main_text regions, detect individual columns:
   - Vertical projection profile analysis
   - Or learned column boundary detection
4. Determine reading order:
   - Right-to-left for columns
   - Top-to-bottom within columns
```

### Technology
- LayoutLMv3 or DiT (Document Image Transformer)
- PaddleOCR layout analysis module
- Custom vertical projection for column detection

### Training Data Needed
- 500+ annotated document images with bounding boxes, region types, column boundaries

---

## Stage 3: Multi-Pass OCR

### Purpose
Maximize character accuracy through consensus and provide confidence scores.

### Strategy: Triple-Pass with Consensus

```
Pass 1: Gemini 2.0 Flash (primary)
   - Best for classical Chinese
   - Prompt engineered for genealogical documents

Pass 2: GPT-4V or Claude (validation)
   - Cross-check controversial characters

Pass 3: Consensus Building
   - Agreement → high confidence
   - Disagreement → LLM arbitration based on context
```

### Prompt Engineering for Genealogical OCR

```
COLUMN_OCR_PROMPT = """
Transcribe this column from a traditional Chinese genealogical document (族譜).

Context:
- Era: Qing dynasty or Republican (1644-1949)
- Script: Classical Chinese (文言文), vertical top-to-bottom
- Content types: names, dates (reign years), places, honorifics

Common patterns:
- Honorifics: 公, 君, 翁 (suffixes)
- Clan markers: 氏
- Life events: 生, 卒, 歿
- Reign names: 同治, 光緒, 宣統, 民國
- Cyclical dates: 甲子, 乙丑, etc.

Output: Characters in exact sequence, top to bottom
- Mark uncertain: 字[?]
- Mark illegible: □
"""
```

### Confidence Scoring
For each character, compute:
- **OCR agreement** (40%): Do multiple passes agree?
- **Language model plausibility** (30%): Perplexity in context
- **Corpus frequency** (20%): Common in genealogies?
- **Visual clarity** (10%): OCR confidence score

---

## Stage 4: Alignment Verification

### Purpose
Use alignment quality to verify transcription accuracy—the key insight from manual process.

### Core Insight
> "When a character doesn't align properly despite correct surrounding characters, it indicates a missing character, incorrect character, or extra character."

### Algorithm

```python
def align_and_verify(column_image, transcription, layout_params):
    # 1. Optimize global positioning (x, y, size, spacing)
    params = optimize_params(column_image, transcription, layout_params)

    # 2. Render transcription as overlay
    overlay = render_overlay(transcription, params)

    # 3. Per-character similarity scoring
    char_scores = []
    for i, char in enumerate(transcription):
        orig_region = extract_char_region(column_image, i, params)
        rendered_region = extract_char_region(overlay, i, params)
        similarity = compute_similarity(orig_region, rendered_region)
        char_scores.append((char, similarity, i))

    # 4. Detect anomalies (local outliers)
    anomalies = detect_anomalies(char_scores)

    # 5. Attempt correction for each anomaly
    for anomaly in anomalies:
        correction = attempt_ocr_correction(column_image, anomaly)
        if correction improves similarity:
            apply_correction(transcription, correction)

    return transcription, params, char_scores, anomalies
```

### Similarity Metrics
Combine multiple metrics for robustness:
- **SSIM** (Structural Similarity Index): Overall structure match
- **Normalized Cross-Correlation**: Template matching
- **Stroke-aware comparison**: Custom metric for Chinese characters

### Anomaly Detection
```python
def detect_anomalies(char_scores):
    anomalies = []
    window = 5  # Local context

    for i, (char, score, pos) in enumerate(char_scores):
        # Get local neighborhood scores
        local = char_scores[max(0,i-window):min(len(char_scores),i+window+1)]
        local_scores = [s for c,s,p in local if p != pos]

        mean, std = np.mean(local_scores), np.std(local_scores)

        # Flag if significantly below local average
        if score < mean - 2*std:
            anomalies.append({
                'position': pos,
                'char': char,
                'score': score,
                'severity': (mean - score) / std
            })

    # Also detect systematic offset (missing/extra char signal)
    offset_anomalies = detect_offset_pattern(char_scores)
    anomalies.extend(offset_anomalies)

    return anomalies
```

### Iterative Refinement Loop
```
for iteration in range(max_iterations):
    result = align_and_verify(image, transcription)

    if result.avg_similarity > 0.85 and len(result.anomalies) == 0:
        break  # Quality threshold met

    for anomaly in result.anomalies:
        # Re-OCR just that region with multiple models
        alternatives = multi_ocr(extract_region(image, anomaly.position))

        # Test each alternative
        best = find_best_alternative(alternatives, image, transcription)
        if best improves score:
            transcription[anomaly.position] = best
```

---

## Stage 5: Scholarly Annotation

### Purpose
Generate the three-level annotation hierarchy: character → phrase → section.

### Character Annotation
```python
def annotate_character(char, context, section_type):
    # 1. Database lookup (authoritative source)
    db_entry = classical_chinese_db.lookup(char)

    # 2. LLM enrichment for context-specific meaning
    context_meaning = llm.complete(f"""
        Character: {char}
        Context: {context}
        Section: {section_type}

        Provide: pinyin, meaning in this context, genealogical significance
        Be concise.
    """)

    return {
        'pinyin': db_entry.pinyin,
        'meaning': context_meaning.meaning,
        'context': context_meaning.significance
    }
```

### Phrase Segmentation
```python
def segment_phrases(text, section_type):
    result = llm.complete(f"""
        Segment this classical Chinese genealogical text into meaningful phrases.

        Text: {text}
        Section: {section_type}

        Rules:
        - Keep names (人名) together
        - Keep dates as complete units
        - Don't split four-character idioms (成語)
        - Standard phrases (元配, 繼配, 先卒) are single units

        Output JSON: [{{"chars": "...", "translation": "...", "notes": "..."}}]
    """)
    return json.loads(result)
```

### Section Classification
Classify into standard genealogical sections:
- `title`: Document title
- `name_origins`: Name, courtesy name, surname, ancestral home
- `youth`: Early life, character
- `career`: Occupation, business
- `virtues`: Moral character, philanthropy
- `family`: Wives, children
- `death`: Death date, age
- `burial`: Tomb location, feng shui
- `credits`: Author attributions

### Historical Accuracy via RAG
```python
class HistoricalRAG:
    sources = [
        'chinese_historical_dictionary',
        'qing_reign_periods',
        'chinese_calendar_conversion',
        'genealogy_terminology',
        'regional_gazetteers'
    ]

    def enrich(self, text, query_type):
        relevant = self.retrieve(text, query_type)
        return self.llm.ground_response(text, relevant)
```

---

## Stage 6: App Generation

### Purpose
Generate self-contained HTML application from our existing template.

### Data Structures (matching index.html)

```javascript
// Column positioning
textLayout = [
    { type: 'text', section: 'name', chars: '公名哲泰字恆齋',
      x: 0, y: 8, size: 16, spacing: 1.14 },
    ...
]

// Phrase annotations
phrases = [
    { section: 'name', chars: '公名哲泰',
      translation: 'The gentleman\'s given name was Zhetai',
      notes: '...' },
    ...
]

// Section definitions
sections = {
    'name': { title: 'Name & Origins', chinese: '姓名籍貫', description: '...' },
    ...
}

// Character dictionary
characterData = {
    '公': { pinyin: 'gōng', meaning: 'Gentleman', context: '...' },
    ...
}
```

### Quality Report
Include confidence markers in output:
```javascript
qualityMarkers = [
    { position: [col, char], confidence: 0.65, message: 'Low OCR confidence' },
    ...
]
```

---

## Training Requirements

### Dataset 1: Layout Detection
- **Size**: 500-1000 annotated images
- **Annotations**: Region bounding boxes, types, column boundaries, reading order
- **Sources**: FamilySearch, 中國家譜總目, university collections

### Dataset 2: OCR Fine-tuning
- **Size**: 10,000+ character images with ground truth
- **Focus**: Classical variants, degraded characters, archaic forms
- **Format**: Character image + Unicode + alternatives

### Dataset 3: Alignment Verification
- **Size**: 5,000+ alignment examples
- **Annotations**: Correct/incorrect labels, correct character for errors
- **Use**: Train anomaly detection model

### Dataset 4: Phrase Segmentation
- **Size**: 500+ fully segmented texts
- **Annotations**: Phrase boundaries, types, translations
- **Sources**: Existing translated genealogies

---

## Quality Thresholds

### Per-Character
| Metric | Threshold | Action |
|--------|-----------|--------|
| OCR Consensus | < 2/3 | Flag for review |
| Alignment Similarity | < 0.70 | Re-OCR attempt |
| Combined Confidence | < 0.60 | Mark uncertain |

### Document-Level
| Avg Confidence | Rating |
|----------------|--------|
| > 0.90 | High quality - auto-publish |
| 0.80-0.90 | Good - spot check |
| 0.70-0.80 | Acceptable - review flagged items |
| < 0.70 | Requires human review |

---

## Implementation Phases

### Phase 1: Core Pipeline (4-6 weeks)
- Preprocessing module
- Layout analysis (pre-trained models)
- Multi-pass OCR integration
- Basic app generation

### Phase 2: Alignment Verification (3-4 weeks)
- Per-character similarity scoring
- Anomaly detection
- Iterative refinement loop
- Confidence system

### Phase 3: Scholarly Annotation (3-4 weeks)
- Character dictionary
- Phrase segmentation
- Section classification
- RAG integration

### Phase 4: Training & Tuning (4-6 weeks)
- Collect training data
- Fine-tune layout model
- Fine-tune OCR
- Train alignment verifier

### Phase 5: Polish (2-3 weeks)
- Quality reporting
- Batch processing
- Documentation

---

## Technology Stack

| Component | Choice | Notes |
|-----------|--------|-------|
| Preprocessing | OpenCV | Deskew, binarize, denoise |
| Layout | LayoutLMv3 | Fine-tune on genealogies |
| Primary OCR | Gemini 2.0 Flash | Best classical Chinese |
| Secondary OCR | Claude 3.5 Sonnet | Validation |
| Annotation LLM | Claude 3.5 Sonnet | Scholarly quality |
| Vector DB | Pinecone/Chroma | RAG for history |
| Template | Jinja2 | App generation |

---

## Success Criteria

Fully automated processing should achieve:
- **90%+ character accuracy** without human intervention
- **95%+ phrase segmentation** accuracy
- **< 5% of characters** flagged for review
- **Alignment within 3 pixels** of manual positioning
- **Scholarly annotations** pass expert review 80% of time

Documents meeting these criteria can be published directly. Others are flagged with specific issues highlighted for efficient human review.

---

## Future Extensions

1. **Batch processing**: Process entire genealogy volumes
2. **Cross-document linking**: Connect family members across documents
3. **Search index**: Full-text search across processed documents
4. **Collaborative correction**: Interface for experts to fix flagged issues
5. **Model improvement loop**: Use corrections to retrain models
