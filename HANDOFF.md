# HANDOFF — Thai Voice Bridge

## สิ่งที่ส่งมอบ

โปรเจกต์ใหม่ที่ `C:\Users\thaun\Documents\Playground\thai-voice-bridge`

- Python package: `src/thai_voice_bridge/`
- CLI: `list-devices`, `discover-cache`, `init-config`, `run`, `tray`
- Tray app + config example
- Unit tests, README (ไทย), packaging + startup scripts (ยังไม่รันติดตั้ง)
- Git local commits เท่านั้น — **ยังไม่ push**

## ต้นแบบที่อ้างอิง (read-only)

- `C:\Users\thaun\Documents\Playground\codex_voice_hotkey.py`
- `C:\Users\thaun\Documents\Playground\whisper_transcribe.py`
- Cache: `C:\Users\thaun\Documents\Playground\.hf-cache` (medium + small)
- Env ศึกษา: `C:\Users\thaun\Documents\Playground\.whisper-env`

**ไม่ได้แก้/ย้าย/ลบ/commit ไฟล์ใน Playground working tree**

## สถาปัตยกรรมสั้นๆ

```
Hotkey(F8 PTT) → Recorder(unique WAV) → WhisperEngine(th/transcribe)
  → Dictionary(+profile) → confidence gate → paste(Ctrl+V) + clipboard restore
  → optional Enter → delete WAV → feedback beeps
```

Tray / single-instance ครอบรอบแอปหลัก

## ความต่างจากต้นแบบ

| ต้นแบบ | Thai Voice Bridge |
|--------|-------------------|
| Focus `claude.exe` | Foreground window เท่านั้น |
| ไม่ restore clipboard | Restore หลัง paste |
| temp WAV ชื่อคงที่ | UUID + ลบหลังใช้ |
| ไม่มี tray / lock | มี |
| dictionary แคบ | profiles + คำศัพท์ที่กำหนด |
| language optional | บังคับ `th` + `transcribe` |

## ขั้นตอนเจ้าของหลังรับมอบ

1. สร้าง venv และ `pip install -e .`
2. `python -m thai_voice_bridge init-config`
3. ตั้ง `hf_cache_dir` ชี้ไป `.hf-cache` เดิม
4. `discover-cache` → ต้อง READY
5. `list-devices` → เลือกไมค์ใน config
6. รัน `pythonw -m thai_voice_bridge tray`
7. ทำ [docs/MANUAL_SMOKE_CHECKLIST.md](docs/MANUAL_SMOKE_CHECKLIST.md)
8. **อย่า**รัน `install_startup.ps1` จนกว่าจะอนุมัติเอง
9. **อย่า** push / deploy โดยไม่ได้รับอนุญาต

## คำสั่งตรวจสอบที่ทำแล้ว / ควรทำซ้ำ

```powershell
python -m pytest -q
python -m compileall -q src
python -m thai_voice_bridge list-devices
python -m thai_voice_bridge discover-cache
```

## ข้อจำกัดที่รู้

- CUDA เป็น optional — default CPU int8 อาจช้าบนเครื่องอ่อน
- `keyboard` / global hotkey มักต้องรัน elevated หรืออนุญาต accessibility ตามนโยบาย Windows
- Confidence จาก `avg_logprob` เป็นค่าประมาณ ไม่ใช่ calibration จริง
- Tray Settings เปิดไฟล์ YAML ด้วย editor เริ่มต้น — ยังไม่มี GUI settings
- `allow_model_download: false` + ไม่มี cache → แอปจะไม่โหลดโมเดล
- ไม่รองรับ macOS/Linux เป็นเป้าหมายหลัก (มี fallback บางส่วนสำหรับเทส)
- Per-app profile จับคู่จากชื่อ process/title เท่านั้น ไม่ได้อ่านเนื้อหาแอป

## ไฟล์สำคัญ

- `src/thai_voice_bridge/app.py` — orchestration
- `src/thai_voice_bridge/whisper_engine.py` — Faster Whisper + cache discovery
- `src/thai_voice_bridge/paste.py` — clipboard restore
- `src/thai_voice_bridge/tray.py` — system tray
- `config.example.yaml` — แม่แบบ config
- `scripts/install_startup.ps1` — **manual only**
