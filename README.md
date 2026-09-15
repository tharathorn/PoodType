# PoodType

> **Speak Thai. Type Anywhere.**  
> พูดภาษาไทย พิมพ์ได้ทุกแอป

แอป dictation ภาษาไทยแบบ system-wide สำหรับ Windows ใช้ **Faster Whisper รันในเครื่องเท่านั้น** แล้ววางข้อความลงหน้าต่างที่กำลังโฟกัสอยู่ (Cursor, Code Coach, Codex, เบราว์เซอร์ ฯลฯ) โดยไม่พึ่ง voice recognition ในตัวแอป

ไม่มี API key, ไม่มีค่าบริการรายเดือน และเสียงไม่ออกจากเครื่อง

## คุณสมบัติหลัก

- Local-only: ไม่เรียก cloud API (ยกเว้นดาวน์โหลดโมเดลเมื่อตั้ง `allow_model_download: true`)
- ภาษาบังคับ `th` + `task: transcribe` (ห้าม translate เป็นอังกฤษ)
- Toggle hotkey ค่าเริ่มต้น **F8** (กดเริ่ม / กดอีกครั้งหยุด) — `mode: hotkey`
- Hands-free wake-word mode (สลับจาก tray): พูด **เฮ้ พุดไทป์** เริ่มอัด → **ส่งได้ พุดไทป์** หยุดแล้ว paste
- วางข้อความด้วย Ctrl+V — **ไม่กด Enter** โดยค่าเริ่มต้น (`auto_send: false`; wake-word บังคับ paste-only)
- Restore clipboard เดิมหลังวาง
- ยกเลิก paste ถ้าหน้าต่าง foreground เปลี่ยนระหว่างถอดเสียง
- จำกัดการอัดค่าเริ่มต้น **300 วินาที (5 นาที)** ทั้ง F8 และ wake-word; เกินแล้วทิ้งเสียงและไม่ paste
- Tray icon: Pause/Resume, สลับ Mode Hotkey/Wake word, Settings, Exit + สถานะสี
- Single-instance lock
- Dictionary / per-app profile สำหรับศัพท์เทคนิค
- ไม่เก็บเสียงหรือ transcript เต็มโดยค่าเริ่มต้น

## ความต้องการระบบ

- Windows 10/11
- ไมโครโฟน
- RAM อย่างน้อย 8 GB (แนะนำ 16 GB)

## ดาวน์โหลดสำหรับผู้ใช้ทั่วไป

ดาวน์โหลดจาก [GitHub Releases](https://github.com/tharathorn/PoodType/releases):

- **Setup.exe** — ติดตั้งแบบปกติ พร้อม Start Menu shortcut
- **Portable.zip** — แตกไฟล์แล้วเปิด `PoodType.exe` ได้ทันที

ทั้งสองแบบรวม Faster Whisper `medium` และทำงาน offline ไม่มี API key
หรือค่าบริการรายเดือน รุ่น Portable เก็บ `config.yaml` ไว้ในโฟลเดอร์เดียวกับแอป

## ติดตั้งจาก source (นักพัฒนา)

```powershell
git clone https://github.com/tharathorn/PoodType.git
cd PoodType
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python -m thai_voice_bridge init-config
```

แก้ config ที่ `%LOCALAPPDATA%\PoodType\config.yaml`

ตั้งค่า Faster Whisper cache ที่มีอยู่แล้ว:

```yaml
hf_cache_dir: C:\path\to\huggingface-cache
allow_model_download: false
model: medium
device: cpu
compute_type: int8
```

## ใช้งาน

```powershell
# รายการไมโครโฟน
python -m thai_voice_bridge list-devices

# ตรวจว่ามี model ใน cache หรือยัง (ไม่ดาวน์โหลด)
python -m thai_voice_bridge discover-cache

# Tray (แนะนำ — ไม่กระพริบ console ถ้าใช้ pythonw)
pythonw -m thai_voice_bridge tray
# หรือ
python -m thai_voice_bridge tray

# Console mode
python -m thai_voice_bridge run
```

### Hotkey (ค่าเริ่มต้น)

1. โฟกัสช่องพิมพ์ในแอปที่ต้องการ
2. กด **F8** ครั้งหนึ่งเพื่อเริ่มอัด พูดภาษาไทย (ผสมศัพท์อังกฤษได้) แล้วกด **F8** อีกครั้งเพื่อหยุด
3. ปล่อยปุ่ม → ข้อความถูกวางลงหน้าต่างปัจจุบัน
4. กด Enter เองถ้าต้องการส่ง (หรือเปิด `auto_send: true`)

### Wake-word (hands-free)

1. คลิกขวา tray → เลือก **Mode: Wake word**
2. พูด **เฮ้ พุดไทป์** → ได้ยินเสียง start แล้วพูดเนื้อหา
3. พูด **ส่งได้ พุดไทป์** → ได้ยินเสียง stop → ถอดเสียงแล้ว paste (ไม่กด Enter; ตัดวลีเริ่ม/จบออก)
4. สลับกลับ **Mode: Hotkey (F8)** ได้จาก tray เดียวกัน

วลีเริ่ม/จบรองรับ phonetic alias และ homophone ที่ Faster Whisper มักถอดเพี้ยน
(เช่น `โอเค พูดท้าย`, `ภูทัย`, `เฮ้ พุทธไทย`, `ส่งได พุดไทป์`) พร้อม normalize ช่องว่าง/ตัวพิมพ์
และกัน start กับ end ชนกัน — ดู `src/thai_voice_bridge/phrases.py`

## Config สำคัญ

ดู `config.example.yaml`

| คีย์ | ค่าเริ่มต้น | หมายเหตุ |
|------|-------------|----------|
| `mode` | `hotkey` | `hotkey` หรือ `wake_word` |
| `hotkey` | `f8` | global PTT เมื่อ `mode: hotkey` |
| `wake_word.start_phrase` | `เฮ้ พุดไทป์` | เริ่มอัด |
| `wake_word.end_phrase` | `ส่งได้ พุดไทป์` | หยุดอัดแล้ว paste |
| `language` | `th` | บังคับ |
| `task` | `transcribe` | บังคับ |
| `model` | `medium` | |
| `device` | `cpu` | `cuda` เป็น optional |
| `auto_send` | `false` | |
| `min_confidence` | `0.35` | ต่ำกว่านี้ไม่ paste |
| `microphone` | `null` | index หรือชื่อย่อย |
| `max_recording_seconds` | `300` | hard limit ทั้งสองโหมด; เกินแล้วไม่สร้าง WAV/paste |
| `hf_cache_dir` | auto-detect | path ไปยัง HF cache |
| `allow_model_download` | `false` | |

User config อยู่นอก Git (`%LOCALAPPDATA%\PoodType\`) ยกเว้นรุ่น Portable

## ทดสอบ

```powershell
python -m pytest -q
python -m compileall -q src
```

## สร้าง Release

```powershell
# ต้องมี Inno Setup 6 และ Faster Whisper medium ใน cache
powershell -ExecutionPolicy Bypass -File .\scripts\build_release.ps1
```

สคริปต์สร้างทั้ง Portable ZIP และ Windows installer ใน `release\`
โดย copy model เป็นไฟล์จริงและสร้าง SHA-256 manifest ไม่ commit model ลง Git

## ความเป็นส่วนตัว / ความปลอดภัย

- ไม่ได้อ่านข้อความหรือ credential จาก foreground app
- ไม่ paste ถ้า transcript ว่างหรือ confidence ต่ำ
- Pause/Exit ยกเลิก recording และ invalidate transcription ที่ยังไม่ paste
- จับ HWND ตอนปล่อย F8 และ paste เฉพาะเมื่อยังเป็น foreground เดิม
- Log ถูก sanitize และไม่เก็บข้อความเต็มโดยค่าเริ่มต้น
- ไม่แก้ registry / ไม่สร้าง scheduled task เอง
- ไม่ focus ไปที่ exe ใดเป็นการเฉพาะ

## เอกสารเพิ่ม

- [HANDOFF.md](HANDOFF.md)
- [docs/MANUAL_SMOKE_CHECKLIST.md](docs/MANUAL_SMOKE_CHECKLIST.md)
