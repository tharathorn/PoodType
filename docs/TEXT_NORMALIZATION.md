# Thai text normalization (offline)

`thai_voice_bridge.text_normalizer` cleans Faster Whisper Thai transcripts **entirely offline** — no network, no model download, no external tokenizer.

## Entry point

```python
from thai_voice_bridge.text_normalizer import normalize_text

normalize_text("ไป ไป ตลาด จุด ราคาสองร้อยบาทห้าสิบสตางค์")
# → "ไป ตลาด. ราคา200.50 บาท"
```

Pipeline order:

1. Collapse whitespace
2. Remove repetitive ASR stutter tokens
3. Normalize currency (`บาท` / `สตางค์`)
4. Convert remaining Thai spoken numbers to digits
5. Map spoken punctuation tokens to symbols

## Helpers

| Function | Role |
|----------|------|
| `remove_stutter_tokens` | Collapse consecutive identical whitespace-separated tokens (`ไป ไป ไป` → `ไป`) |
| `normalize_spoken_numbers` | Thai number words → Arabic digits (`ยี่สิบสาม` → `23`) |
| `normalize_currency` | Amounts with `บาท`/`สตางค์` → `N บาท` or `N.SS บาท` |
| `normalize_spoken_punctuation` | Spoken marks → `. , / - : ; ? ! ( ) %` |
| `spoken_number_to_int` | Parse one spoken-number phrase to `int` |

## Spoken numbers

Supported digit words: `ศูนย์`–`เก้า`, `เอ็ด`, `ยี่`  
Units: `สิบ`, `ร้อย`, `พัน`, `หมื่น`, `แสน`, `ล้าน`  
Spaces between number words are allowed (`ห้า สิบ` → `50`).

## Currency

- `หนึ่งร้อยบาท` → `100 บาท`
- `ห้าสิบบาทห้าสิบสตางค์` → `50.50 บาท`
- `เจ็ดสิบห้าสตางค์` → `0.75 บาท`
- Already-digit amounts (`50 บาท`) are accepted the same way

## Spoken punctuation

| Token | Symbol |
|-------|--------|
| `จุด` / `มหัพภาค` | `.` |
| `จุลภาค` / `คอมมา` | `,` |
| `ทับ` | `/` |
| `ขีด` / `ขีดกลาง` / `แดช` | `-` |
| `สองจุด` / `โคลอน` | `:` |
| `อัฒภาค` / `เซมิโคลอน` | `;` |
| `เครื่องหมายคำถาม` | `?` |
| `อัศเจรีย์` | `!` |
| `เปิดวงเล็บ` / `ปิดวงเล็บ` | `(` / `)` |
| `เปอร์เซ็นต์` | `%` |

Spaces around punctuation are tightened after replacement (`จบ จุด` → `จบ.`).

## Tests

Offline unit coverage lives in `tests/test_phrases.py` (phrase matching + normalizer). Run:

```powershell
python -m pytest tests/test_phrases.py -q
```

## Scope note

This module is standalone. Wiring into the live paste path (`dictionary.normalize_transcript` / `app.py`) is intentionally out of scope for the normalizer task; call `normalize_text` from the orchestration layer when integrating.
