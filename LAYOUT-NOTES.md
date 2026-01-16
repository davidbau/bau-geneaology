# Layout Position Notes

## Column Organization

The textLayout array is organized in visual order (right to left), which matches the flex `row-reverse` display:

1. **Title** (1 column, rightmost)
2. **Credits** (2 columns)
3. **Main Body** (10 logical columns, 13 segments)
4. **Spine** (1 logical column, 4 segments)
5. **Feng Shui** (3 logical columns, 6 segments)

---

## Current X Offsets (after reordering)

### Title
| Chars | x | y | Notes |
|-------|---|---|-------|
| 鮑公恆齋生壙志 | -20 | 9 | Bordered title |

### Credits
| Chars | x | y | Notes |
|-------|---|---|-------|
| 同邑張美翊撰文 | 116 | 357 | Author attribution |
| 書丹 | 113 | 451 | Calligrapher credit |

### Main Body (10 columns, 13 segments)

| Col | Chars | x | y | Notes |
|-----|-------|---|---|-------|
| 1 | 公名哲泰字恆齋姓鮑氏 | -47 | 9 | Top of col 1 |
| 1 | 世篤鄞南鄞塘鄉鮑家埭人 | -22 | 200 | Middle of col 1 |
| 1 | 曾祖廷揚祖光華父 | 5 | 412 | Bottom of col 1 |
| 2 | 明昌母侯氏兄弟二人公其長也 | 2 | 9 | Top of col 2 |
| 2 | 自幼勤奮樸實循規蹈矩先喪母後喪父 | 28 | 258 | Bottom of col 2 |
| 3 | 年十三即棄書而賈... | 25 | 9 | Full column |
| 4 | 駕釣船捕魚江浙海中... | 22 | 9 | Full column |
| 5 | 業候時殖貨歲有奇贏... | 18 | 9 | Full column |
| 6 | 不倦在滬如寧波同鄉會... | 14 | 9 | Full column |
| 7 | 興辦學校修葺宗祠... | 10 | 9 | Full column |
| 8 | 無愧焉元配陳氏前卒... | 6 | 9 | Full column |
| 9 | 崔出女四人適余頌威... | 3 | 9 | Full column |
| 10 | 於前清同治四年乙丑... | -2 | 9 | Full column |

**Main body x offset pattern**: ranges from -47 to +28, mostly small adjustments

### Spine (1 column, 4 segments)
| Chars | x | y | Size | Notes |
|-------|---|---|------|-------|
| 句俞鮑氏宗譜 | 14 | 5 | 28 | Book title |
| 卷六 | 51 | 167 | 28 | Volume number |
| 生壙志 | 95 | 245 | 13 | Document type |
| 正始堂 | 112 | 499 | 27 | Hall name |

### Feng Shui (3 columns, 6 segments)
| Col | Chars | x | y | Notes |
|-----|-------|---|---|-------|
| 1 | 鳳山麓墓向坐 | 104 | 9 | Top fragment |
| 1 | 向 | 130 | 142 | Single char |
| 1 | 兼 | 158 | 180 | Single char |
| 1 | 山環水抱當蔭其嗣人 | 182 | 237 | Bottom fragment |
| 2 | 天鳳之山形勢飛翔... | 179 | 9 | Full column (30 chars) |
| 3 | 歸其藏 | 176 | 9 | Short column (3 chars) |

---

## X Offset Calculation

When reordering from old to new array positions:
- **Credits**: moved from indices 14-15 to 1-2, adjustment = -208
- **Main body**: moved from indices 1-13 to 3-15, adjustment = +32
- **Spine & Feng Shui**: unchanged (same relative indices 16-25)

Formula: `new_x = old_x + (new_cumulative_width - old_cumulative_width)`

---

## Future Optimization: Combining Segments

### Main Body Columns 1-2
Could potentially combine segments with ideographic spaces (U+3000) if gaps align to character grid:
- Column 1: Check if gaps between segments match ~1 or 2 char heights
- Column 2: Check if gap matches character grid

### Feng Shui Column 1
The 4 fragments could be combined with ideographic spaces if the x positions can be unified:
- Current x values vary: 104, 130, 158, 182 (78px range)
- Would need to verify these are the same visual column in the original

---

## Font Reference

| Type | Size | Spacing | Line Height |
|------|------|---------|-------------|
| Main text | 16 | 1.14 | 18.24px |
| Title | 16 | 1.14 | 18.24px |
| Credits | 16 | 1.14 | 18.24px |
| Spine (large) | 27-28 | 0.80-0.85 | ~22-24px |
| Spine (small) | 13 | 1.18 | 15.34px |
