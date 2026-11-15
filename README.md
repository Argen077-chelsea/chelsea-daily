# chelsea-daily
ชุดเครื่องมือทำคลิปข่าวเชลซีประจำวัน (Short 9:16 + คลิปยาว 16:9) — อ่าน WORKFLOW.md ก่อน

- `WORKFLOW.md` ขั้นตอนประจำวันที่ผู้ใช้กำหนด
- `tools/` ตัวสร้างการ์ดคลิปยาว (bounds.py หาเวลาฉากจากช่วงหยุดของเสียง · make_cards.py สร้างการ์ด HTML)
- `short/` การ์ดและ storyboard ของ Short วันที่ 2026-11-15 (ตัวอย่างโครงสร้าง)
- `scripts/` สคริปต์ render/assemble/review (จากสกิล director)
- `audio/sfx/kit/` เสียงประกอบ CC0
- ติดตั้ง: `npm i` (GSAP ต้องมาจาก npm — CDN ถูกบล็อกในเครื่องคลาวด์)
- ไฟล์เสียงพากย์/วิดีโอไม่เก็บใน repo
