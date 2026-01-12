# Layout Position Notes

## Current Column X Positions (as of commit 4cb5a88)

These positions have been manually tuned to align precisely with the scanned image.

### Reading Order vs Display Order

The container uses `flex-direction: row-reverse`, so columns in the array appear right-to-left. Array index 0 appears rightmost.

### Current Array Order and X Offsets

| Index | Type | Section | First Chars | x | y | Notes |
|-------|------|---------|-------------|---|---|-------|
| 0 | title | title | 鮑公恆齋生壙志 | -20 | 9 | |
| 1 | text | ancestry | 公名哲泰字恆齋姓鮑氏 | -79 | 9 | |
| 2 | text | ancestry | 世篤鄞南鄞塘鄉鮑家埭人 | -54 | 200 | partial column |
| 3 | text | family_background | 曾祖廷揚祖光華父 | -27 | 412 | partial column |
| 4 | text | family_background | 明昌母侯氏兄弟二人公其長也 | -30 | 9 | |
| 5 | text | youth | 自幼勤奮樸實循規蹈矩先喪母後喪父 | -4 | 258 | partial column |
| 6 | text | occupation | 年十三即棄書而賈... | -7 | 9 | |
| 7 | text | occupation | 駕釣船捕魚江浙海中... | -10 | 9 | |
| 8 | text | virtues | 業候時殖貨歲有奇贏... | -14 | 9 | |
| 9 | text | virtues | 不倦在滬如寧波同鄉會... | -18 | 9 | |
| 10 | text | virtues | 興辦學校修葺宗祠... | -22 | 9 | |
| 11 | text | family | 無愧焉元配陳氏前卒... | -26 | 9 | |
| 12 | text | family | 崔出女四人適余頌威... | -29 | 9 | |
| 13 | text | death | 於前清同治四年乙丑... | -34 | 9 | |
| 14 | credit | credit | 同邑張美翊撰文 | 324 | 357 | |
| 15 | credit | credit | 書丹 | 321 | 451 | |
| 16 | spine | spine | 句俞鮑氏宗譜 | 14 | 5 | size: 28 |
| 17 | spine | spine | 卷六 | 51 | 167 | size: 28 |
| 18 | spine | spine | 生壙志 | 95 | 245 | size: 13 |
| 19 | spine | spine | 正始堂 | 112 | 499 | size: 27 |
| 20 | text | burial | 鳳山麓墓向坐 | 104 | 9 | feng shui |
| 21 | text | burial | 向 | 130 | 142 | single char |
| 22 | text | burial | 兼 | 158 | 180 | single char |
| 23 | text | burial | 山環水抱當蔭其嗣人 | 182 | 237 | partial |
| 24 | text | burial | 天鳳之山形勢飛翔... | 179 | 9 | |
| 25 | text | burial | 歸其藏 | 176 | 9 | |

### X Offset Patterns

- **Main body text (indices 1-13)**: x ranges from -79 to -4, trending from -79 (rightmost) to -34 (leftmost of main body)
  - The drift is approximately 3-4px per column leftward
  - Average spacing between columns: ~3.6px adjustment per column

- **Credits (indices 14-15)**: x ≈ +321 to +324 (far right of image)

- **Spine (indices 16-19)**: x ranges +14 to +112 (left edge of document)

- **Feng shui/burial (indices 20-25)**: x ranges +104 to +182 (left side, between spine and main body)

### Optimization Opportunity

The large x offsets (especially +324 for credits, and the -79 to +182 range overall) exist because the array order doesn't match the visual left-to-right position on the page.

**Suggested reordering** to minimize offsets:

1. **Credits** (currently need +324 to push far right → would naturally be rightmost)
2. **Title** (bordered, right of main body)
3. **Main body text** (13 columns, flowing left)
4. **Feng shui/burial** (6 columns, left of main body)
5. **Spine** (leftmost edge)

With this order, plus appropriate margin/gap settings in CSS, all x offsets could potentially be reduced to small adjustments (< 20px) rather than the current range of -79 to +324.

### Implementation Notes

To preserve exact current positions while reordering:
1. Calculate the "natural" position each column would have in new order
2. Compute the required x offset to maintain current visual position
3. May need to adjust container padding or column margins
4. The goal is smaller offsets, not zero—some fine-tuning will always be needed

### Font and Spacing Reference

| Type | Size | Spacing | Notes |
|------|------|---------|-------|
| Main text | 16 | 1.14 | Standard body |
| Title | 16 | 1.14 | Bold, bordered |
| Credits | 16 | 1.14 | |
| Spine (large) | 27-28 | 0.80-0.85 | |
| Spine (small) | 13 | 1.18 | |
