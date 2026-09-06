# HANDOFF — PoodType

## Offline Thai text normalization — 2026-09-06

Added standalone offline normalizer (no network / no model I/O):

- Module: `src/thai_voice_bridge/text_normalizer.py`
- Docs: `docs/TEXT_NORMALIZATION.md`
- Tests: extended `tests/test_phrases.py` (stutter, spoken numbers, บาท/สตางค์, punctuation, full `normalize_text` pipeline)
- Entry: `normalize_text()` — stutter → currency → numbers → punctuation
- Not yet wired into live paste path (`app.py` / `dictionary.py`); integrate when ready

Verify:

```powershell
python -m pytest -q
python -m compileall -q src
```

## Session closeout — 2026-07-26 ~08:12 Asia/Bangkok

### Done / owner-verified
- **F8 = toggle** (กดเริ่ม / กดอีกครั้งหยุด) — ไม่ต้องกดค้างแล้ว
  - Commit: `f8ac3bf feat: make F8 toggle start/stop instead of hold-to-talk`
  - Owner smoke: กดแล้วปล่อยใช้งานได้แล้ว ✅
- App currently left on `mode: hotkey` in `%LOCALAPPDATA%\PoodType\config.yaml`

### Next: เตรียมตัวพูดไทย (wake-word) — ยังไม่จบ

อย่า resume แบบ “เปิดโหมดแล้วจบ” — ปัญหาอยู่ที่ **Whisper ถอดวลีปลุกเพี้ยน** ไม่ใช่แค่ UI

ข้อค้นพบจาก mic จริงของเจ้าของ:
- พูด **「เฮ้ พุดไทป์」** แล้ว Faster Whisper มักได้ เช่น
  - `โอเค พูดท้าย`
  - `ภูทัย`
  - `เทพุทธ`
- เคยถอดถูก `เฮ้ พุดไทป์` ได้บ้าง แต่ไม่เสถียร
- เสียงรบกวนเบา (~RMS 0.003) เคยท่วมคิว ASR จนวลีจริงไม่ทันถูกถอด → ยก `speech_rms` เป็น `0.01` แล้ว
- Alias matching เพิ่มใน `phrases.py` แล้ว (รับ `โอเค พูดท้าย` / `ภูทัย` / …) แต่ **owner ยังไม่ยืนยันว่าไอคอนแดง/บีบตอน wake ใช้ได้**

งานต่อที่แนะนำ (ลำดับ):
1. Owner smoke โหมด Wake word อีกครั้งหลัง alias fix (`73cce98` / `4494829`)
   - Tray → Mode: Wake word → พูดชัด 「เฮ้ พุดไทป์」 → ต้องแดง+บีบ
2. ถ้ายังเพี้ยน: เก็บ `wake_listen_window text=...` จาก `%LOCALAPPDATA%\PoodType\poodtype.log` แล้วเติม alias
3. พิจารณาเปลี่ยนวลีปลุกเป็นคำที่ Whisper คุ้นกว่า (ถ้า alias ไม่พอ) — ต้องคุยเจ้าของก่อน
4. อย่าโหลดโมเดล medium สองตัว; wake window ใช้ `self.engine` + `initial_prompt=""` แล้ว

Commits ที่เกี่ยว wake (ยังไม่ release):
- `548ed8f` quiet ASR flood / shared engine
- `4494829` Whisper mishearing aliases
- `73cce98` กัน end phrase fuzzy เป็น start
- `f8ac3bf` F8 toggle (แยกจาก wake)

Automated: `pytest -q` **67 passed**

## Wake-word mode — 2026-07-26 (awaiting owner smoke)

Implemented on `master` (not released yet):

- Tray switch: **Mode: Hotkey (F8)** ↔ **Mode: Wake word**
- Start phrase `เฮ้ พุดไทป์` / end phrase `ส่งได้ พุดไทป์`
- VAD + short Whisper windows for phrase detect; full utterance then paste
- End path paste-only (`auto_send` forced false); strips start/end phrases
- Shared `max_recording_seconds` default **300**; over-limit discards, no paste
- Spec: `docs/superpowers/specs/2026-07-26-wake-word-mode-design.md`
- Plan: `docs/superpowers/plans/2026-07-26-wake-word-mode.md`

Owner action: run `docs/MANUAL_SMOKE_CHECKLIST.md` (รวมส่วน Wake-word) ก่อน push/release

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
3. จำกัด recording (ค่าเริ่มต้น 300 วินาที); เกินแล้วหยุด/ทิ้งและไม่สร้าง WAV
4. Clipboard read/restore fail-closed
5. Model preload ล้มเหลวแล้วไม่เปิด input listener
6. Disable hotkey ล้าง held-key state ป้องกัน stale release

งานต่อที่เป็น optional:

- Owner manual smoke สำหรับ wake-word แล้วค่อย release
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
mode=hotkey:
  Hotkey(F8 PTT) → Recorder(unique WAV) → WhisperEngine(th/transcribe)
    → Dictionary(+profile) → confidence gate → paste(Ctrl+V) + clipboard restore
    → optional Enter → delete WAV → feedback beeps

mode=wake_word:
  WakeWordListener(VAD + short Whisper) → start/end phrases
    → utterance WAV → strip phrases → same confidence/paste path (Enter forced off)
```

Tray / single-instance ครอบรอบแอปหลัก (สลับโหมดได้จากเมนู)

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
4. โฟกัสช่องพิมพ์ กด F8 ค้าง พูด แล้วปล่อย — หรือสลับ tray เป็น Wake word แล้วใช้วลีเริ่ม/จบ
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

- `src/thai_voice_bridge/app.py` — orchestration (hotkey + wake-word modes)
- `src/thai_voice_bridge/wake_listener.py` — VAD + phrase detect loop
- `src/thai_voice_bridge/phrases.py` — wake/end phrase match + strip
- `src/thai_voice_bridge/text_normalizer.py` — offline Thai number/currency/punctuation/stutter cleanup
- `docs/TEXT_NORMALIZATION.md` — normalizer API + examples
- `src/thai_voice_bridge/whisper_engine.py` — Faster Whisper + cache discovery
- `src/thai_voice_bridge/paste.py` — clipboard restore
- `src/thai_voice_bridge/tray.py` — system tray (mode switch)
- `config.example.yaml` — แม่แบบ config
- `scripts/install_startup.ps1` — **manual only**
