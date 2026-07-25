# HANDOFF — PoodType

## Public release — 2026-07-25

- Public repository: <https://github.com/tharathorn/PoodType>
- Release: <https://github.com/tharathorn/PoodType/releases/tag/v0.1.0>
- Git branch `master`; release commit `7cc7cbc`
- `pytest -q`: **48 passed**
- `compileall -q src scripts`: **OK**
- Portable ZIP: 1,517,660,653 bytes; extraction/config smoke passed
- Installer: 1,451,250,773 bytes; install/run/uninstall smoke passed
- Packaged Faster Whisper `medium` preload passed
- Both packages are offline after download: no API key, account, subscription,
  analytics, or telemetry
- SHA-256 checksums are published as `SHA256SUMS.txt`
- Installer is not code-signed; Windows may show an Unknown publisher warning
- Dev Orchestrator registration remains under the internal project name
  `thai-voice-bridge`; push/deploy/integration/cleanup policies remain `never`
- Windows Startup was not enabled automatically

Manual smoke บน Cursor ผ่านเมื่อ **2026-07-25 ~19:44 Asia/Bangkok**:

- F8 push-to-talk → Thai transcription → paste สำเร็จ
- `auto_send: false` — เจ้าของกด Enter เอง
- Pause ระหว่างถือ F8 → ไม่ paste; Resume แล้วใช้งานต่อได้
- สลับ foreground ระหว่าง transcribe → ไม่ paste ผิดหน้าต่าง
- Clipboard เดิมถูก restore
- Exit ระหว่าง transcribe → ไม่มี paste ตามหลัง

เจ้าของยืนยัน manual checklist ผ่านแล้ว; ไม่ได้เปิด Windows Startup อัตโนมัติ

Hardening ที่เพิ่ม:

1. Pause/Exit ยกเลิก recording และ invalidate transcription ที่กำลังรัน
2. จับ foreground HWND ตอนปล่อย F8; ถ้าหน้าต่างเปลี่ยนจะไม่ paste
3. จำกัด recording 60 วินาที; เกินแล้วหยุด/ทิ้งและไม่สร้าง WAV
4. Clipboard read/restore fail-closed
5. Model preload ล้มเหลวแล้วไม่เปิด global hotkey
6. Disable hotkey ล้าง held-key state ป้องกัน stale release

งานต่อที่เป็น optional:

- จัดหา code-signing certificate เพื่อลด SmartScreen warning
- เพิ่ม screenshot/demo ใน GitHub README
- เปิด Windows Startup เฉพาะเมื่อเจ้าของต้องการ

## สิ่งที่ส่งมอบ

- Python package: `src/thai_voice_bridge/`
- CLI: `list-devices`, `discover-cache`, `init-config`, `run`, `tray`
- Tray app + config example + branded icon
- Portable ZIP + current-user Windows installer พร้อม model `medium`
- Public source, privacy/security docs, third-party license notice และ checksums

## ต้นแบบที่อ้างอิงตอนเริ่มโครงการ (read-only)

- local voice-hotkey prototype
- local Whisper transcription prototype
- existing Hugging Face model cache (`medium` + `small`)

ต้นแบบไม่ได้ถูกแก้ ย้าย ลบ หรือ commit เข้า PoodType

## สถาปัตยกรรมสั้นๆ

```
Hotkey(F8 PTT) → Recorder(unique WAV) → WhisperEngine(th/transcribe)
  → Dictionary(+profile) → confidence gate → paste(Ctrl+V) + clipboard restore
  → optional Enter → delete WAV → feedback beeps
```

Tray / single-instance ครอบรอบแอปหลัก

## ความต่างจากต้นแบบ

| ต้นแบบ | PoodType |
|--------|-------------------|
| Focus `claude.exe` | Foreground window เท่านั้น |
| ไม่ restore clipboard | Restore หลัง paste |
| temp WAV ชื่อคงที่ | UUID + ลบหลังใช้ |
| ไม่มี tray / lock | มี |
| dictionary แคบ | profiles + คำศัพท์ที่กำหนด |
| language optional | บังคับ `th` + `transcribe` |

## ขั้นตอนผู้ใช้

1. ดาวน์โหลด Setup หรือ Portable จาก GitHub Release
2. ตรวจ SHA-256 กับ `SHA256SUMS.txt`
3. ติดตั้งหรือแตก ZIP แล้วเปิด `PoodType.exe`
4. โฟกัสช่องพิมพ์ กด F8 ค้าง พูด แล้วปล่อย
5. กด Enter เองเมื่อต้องการส่ง (`auto_send: false`)

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
