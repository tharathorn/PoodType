# Manual Smoke Checklist

รันแอป: `pythonw -m thai_voice_bridge tray` (หรือ `python -m thai_voice_bridge run`)

ก่อนเริ่ม: `list-devices`, `discover-cache` = READY, โฟกัสช่องพิมพ์จริง

## ร่วมทุกแอป

- [ ] กดค้าง F8 → ได้ยินเสียง start
- [ ] พูดสั้นๆ ภาษาไทย → ปล่อย → เสียง stop แล้ว success
- [ ] ข้อความปรากฏในช่องที่โฟกัส โดย**ไม่**กด Enter เอง
- [ ] Clipboard เดิมยังอยู่หลังวาง (คัดลอกอะไรไว้ก่อนทดสอบ)
- [ ] กด F8 ซ้ำระหว่างกำลัง transcribe → ได้เสียง busy ไม่ซ้อน record
- [ ] พูดเงียบ/สั้นเกิน → ไม่ paste + เสียง error
- [ ] Tray แสดงสถานะ (idle/recording/busy) และ Pause/Resume ใช้ได้

## Cursor

- [ ] โฟกัส chat/composer ใน Cursor
- [ ] พูด: «ช่วยแก้โค้ดใน Cursor ด้วย Codex»
- [ ] ได้คำว่า Cursor / Codex ตาม dictionary
- [ ] ไม่กระโดดไปโฟกัสแอปอื่น

## Code Coach

- [ ] โฟกัสช่องพิมพ์ Code Coach
- [ ] พูด: «เปิดงานใน Code Coach และ Dev Orchestrator»
- [ ] ข้อความวางใน Code Coach ไม่ใช่แอปอื่น

## Codex

- [ ] โฟกัสช่องพิมพ์ Codex (หรือ terminal ที่ใช้กับ Codex)
- [ ] พูด: «รันเทสต์ด้วย PowerShell แล้วเปิด GitHub»
- [ ] ได้ PowerShell / GitHub / test ตามที่คาด
- [ ] `auto_send` ยังเป็น false → ยังไม่ส่งอัตโนมัติ

## Optional send mode

- [ ] ตั้ง `auto_send: true` ใน user config แล้วรีสตาร์ท
- [ ] ทดสอบครั้งเดียวว่ากด Enter หลังวาง
- [ ] คืนค่า `auto_send: false`

## Privacy

- [ ] ตรวจ log ไม่มีข้อความเต็ม (ถ้า `log_full_text: false`)
- [ ] โฟลเดอร์ temp ไม่ค้างไฟล์ `tvb_*.wav` หลังใช้งาน
