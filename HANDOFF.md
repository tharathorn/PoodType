# HANDOFF — Thai Voice Bridge

## Latest review — 2026-07-25

Portfolio TPM ตรวจ repository, tests, Git และ security แล้ว:

- `pytest -q`: **41 passed** (เดิม 29; เพิ่ม safety + branded-icon coverage)
- `compileall -q src`: **OK**
- Security review: ไม่มี medium/high/critical finding หลัง hardening
- Git: branch `master`; commits เดิม `5167e08`, `e260684`, `d86d6fa`
- Safety hardening ยังเป็น **local-only** — ยังไม่ push
- Registered in Dev Orchestrator:
  `proj_9fa2a153931f4e62b5aada9f94478014` (`thai-voice-bridge`, enabled,
  tests `pytest_all` + `compile_check`; push/deploy/integration/cleanup=`never`)
- Desktop shortcut created: `C:\Users\thaun\Desktop\Thai Voice Bridge.lnk`
  with packaged branded ICO; tray uses the matching PNG plus state indicator
- ยังไม่ติดตั้ง Windows Startup, ไม่ deploy และยังไม่ push

Manual smoke บน Cursor ผ่านเมื่อ **2026-07-25 ~19:44 Asia/Bangkok**:

- F8 push-to-talk → Thai transcription → paste สำเร็จ
- `auto_send: false` — เจ้าของกด Enter เอง
- Pause ระหว่างถือ F8 → ไม่ paste; Resume แล้วใช้งานต่อได้
- สลับ foreground ระหว่าง transcribe → ไม่ paste ผิดหน้าต่าง
- Clipboard เดิมถูก restore
- Exit ระหว่าง transcribe → ไม่มี paste ตามหลัง

ยังไม่ได้ยืนยันแยกบน Code Coach/Codex และยังไม่ได้ติดตั้ง Startup

Hardening ที่เพิ่ม:

1. Pause/Exit ยกเลิก recording และ invalidate transcription ที่กำลังรัน
2. จับ foreground HWND ตอนปล่อย F8; ถ้าหน้าต่างเปลี่ยนจะไม่ paste
3. จำกัด recording 60 วินาที; เกินแล้วหยุด/ทิ้งและไม่สร้าง WAV
4. Clipboard read/restore fail-closed
5. Model preload ล้มเหลวแล้วไม่เปิด global hotkey
6. Disable hotkey ล้าง held-key state ป้องกัน stale release

สิ่งที่เจ้าของยังต้องทำก่อนเปิดใช้ถาวร:

- ทดสอบเสริมบน Code Coach/Codex เมื่อต้องใช้งานจริง
- ทดสอบ limit 3 วินาทีตาม checklist หากต้องการยืนยัน hard limit ด้วยตนเอง
- อนุมัติ commit/push/install/startup แยกทีละขั้น
- การ register Dev Orchestrator ดู `docs/DEV_ORCHESTRATOR_REGISTRATION.md`

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
- Foreground safety ตรวจระดับ top-level HWND; การย้าย focus ระหว่าง control
  ภายในหน้าต่างเดียวกันตรวจไม่พบ
- Clipboard รองรับข้อความผ่าน `pyperclip`; ถ้าอ่าน clipboard เดิมไม่ได้
  ระบบจะไม่ paste เพื่อป้องกันข้อมูลเดิมสูญหาย

## ไฟล์สำคัญ

- `src/thai_voice_bridge/app.py` — orchestration
- `src/thai_voice_bridge/whisper_engine.py` — Faster Whisper + cache discovery
- `src/thai_voice_bridge/paste.py` — clipboard restore
- `src/thai_voice_bridge/tray.py` — system tray
- `config.example.yaml` — แม่แบบ config
- `scripts/install_startup.ps1` — **manual only**
