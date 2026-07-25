# Thai Voice Bridge

แอป dictation ภาษาไทยแบบ system-wide สำหรับ Windows ใช้ **Faster Whisper รันในเครื่องเท่านั้น** แล้ววางข้อความลงหน้าต่างที่กำลังโฟกัสอยู่ (Cursor, Code Coach, Codex, เบราว์เซอร์ ฯลฯ) โดยไม่พึ่ง voice recognition ในตัวแอป

## คุณสมบัติหลัก

- Local-only: ไม่เรียก cloud API (ยกเว้นดาวน์โหลดโมเดลเมื่อตั้ง `allow_model_download: true`)
- ภาษาบังคับ `th` + `task: transcribe` (ห้าม translate เป็นอังกฤษ)
- Push-to-talk ค่าเริ่มต้น **F8** (กดค้าง / ปล่อย)
- วางข้อความด้วย Ctrl+V — **ไม่กด Enter** โดยค่าเริ่มต้น (`auto_send: false`)
- Restore clipboard เดิมหลังวาง
- ยกเลิก paste ถ้าหน้าต่าง foreground เปลี่ยนระหว่างถอดเสียง
- จำกัดการอัดค่าเริ่มต้น 60 วินาที; เกินแล้วทิ้งเสียงและไม่ paste
- Tray icon: Pause/Resume, Settings, Exit + สถานะสี
- Single-instance lock
- Dictionary / per-app profile สำหรับศัพท์เทคนิค
- ไม่เก็บเสียงหรือ transcript เต็มโดยค่าเริ่มต้น

## ความต้องการระบบ

- Windows 10/11
- Python 3.10+
- ไมโครโฟน
- (แนะนำ) cache โมเดล Faster Whisper ที่มีอยู่แล้ว เช่น `C:\Users\thaun\Documents\Playground\.hf-cache`

## ติดตั้ง

```powershell
cd C:\Users\thaun\Documents\Playground\thai-voice-bridge
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python -m thai_voice_bridge init-config
```

แก้ config ที่ `%LOCALAPPDATA%\thai-voice-bridge\config.yaml`

ตั้งค่า cache เดิม (อ่านอย่างเดียว — ห้ามลบ/แก้ cache):

```yaml
hf_cache_dir: C:\Users\thaun\Documents\Playground\.hf-cache
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

1. โฟกัสช่องพิมพ์ในแอปที่ต้องการ
2. กดค้าง **F8** พูดภาษาไทย (ผสมศัพท์อังกฤษได้)
3. ปล่อยปุ่ม → ข้อความถูกวางลงหน้าต่างปัจจุบัน
4. กด Enter เองถ้าต้องการส่ง (หรือเปิด `auto_send: true`)

## Config สำคัญ

ดู `config.example.yaml`

| คีย์ | ค่าเริ่มต้น | หมายเหตุ |
|------|-------------|----------|
| `hotkey` | `f8` | global PTT |
| `language` | `th` | บังคับ |
| `task` | `transcribe` | บังคับ |
| `model` | `medium` | |
| `device` | `cpu` | `cuda` เป็น optional |
| `auto_send` | `false` | |
| `min_confidence` | `0.35` | ต่ำกว่านี้ไม่ paste |
| `microphone` | `null` | index หรือชื่อย่อย |
| `max_recording_seconds` | `60` | hard limit; เกินแล้วไม่สร้าง WAV/paste |
| `hf_cache_dir` | auto-detect | path ไปยัง HF cache |
| `allow_model_download` | `false` | |

User config อยู่นอก Git (`%LOCALAPPDATA%\thai-voice-bridge\`)

## ทดสอบ

```powershell
python -m pytest -q
python -m compileall -q src
```

## Packaging / Startup (ทำเองเมื่อพร้อม)

```powershell
# สร้าง exe (ไม่ติดตั้ง)
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1

# ติดตั้ง Startup shortcut ของ user ปัจจุบันเท่านั้น — ต้องอนุมัติก่อนรัน
powershell -ExecutionPolicy Bypass -File .\scripts\install_startup.ps1
```

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
