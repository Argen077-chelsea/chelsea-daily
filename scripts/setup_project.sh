#!/usr/bin/env bash
# director skill — สร้างโฟลเดอร์งานใหม่ (หรือเติมของที่ขาดในโฟลเดอร์เดิม — ไม่ทับไฟล์ที่มีอยู่)
#   bash setup_project.sh PROJECT_DIR ["ชื่อคลิป"]
set -eu
P="${1:?ใส่โฟลเดอร์งาน}"; TITLE="${2:-คลิปใหม่}"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$P"/{refs,audio/sfx,audio/music,assets/img,assets/fonts,assets/video,cards,renders,review,out,scripts}
cd "$P"
new() { [ -e "$1" ] || { printf '%s\n' "$2" > "$1"; echo "  + $1"; }; }

new .env "# คีย์ของคุณ — ห้ามแชร์ไฟล์นี้ ห้าม commit
ELEVENLABS_API_KEY=
FREESOUND_API_KEY=
PIXABAY_API_KEY=
UNSPLASH_ACCESS_KEY="
chmod 600 .env
new .gitignore ".env
index.html
node_modules/
renders/
review/
out/
refs/*/ref.mp4"
new .npmrc "cache=./cache/npm"
new package.json '{ "name": "director-project", "private": true, "type": "module", "dependencies": { "hyperframes": "0.6.45" } }'
new PROGRESS.md "# $TITLE — PROGRESS
อ่านไฟล์นี้ก่อนทุกครั้งที่กลับมาทำต่อ · เขียนทับส่วน \"ตอนนี้\" เสมอ

## brief
- เป้าหมาย:
- ใครดู / ดูที่ไหน: (9:16 Reels/TikTok?)
- ความยาว:
- วันส่ง:
- v1 ขั้นต่ำ:
- ไม่ทำ:

## ตอนนี้
- ขั้น: 0 เริ่มงาน
- งานถัดไป:

## ผู้ใช้อนุมัติแล้ว
- (บท · ref · ชิ้นทดสอบ · คลิป — พร้อมวันที่)"
new LOG.md "# LOG — ทุกการตัดสินใจ ใหม่ล่างสุด
- $(date +%F) สร้างโปรเจกต์"
new script.md "# บทพากย์ — $TITLE
(ยังไม่ล็อก — เมื่อผู้ใช้ตกลง ใส่บรรทัด **LOCKED YYYY-MM-DD** แล้วห้ามแก้โดยไม่บอกว่าต้องทำอะไรใหม่บ้าง)"
new storyboard.json '{
 "title": "",
 "aspect": "9:16",
 "vo": "audio/vo.mp3",
 "music": { "src": "", "gain_db": -18, "duck_db": -8 },
 "cuts_ok": [],
 "beats": [
  { "card": "cards/hook.html", "render": "renders/hook.mp4", "at": 0, "duration": 4,
    "why": "ฮุก: เดิมพัน/คำถาม ภาพแรกมีของให้ดู",
    "text": "คีย์เวิร์ดบนจอ (ไม่ใช่ประโยคที่พูด)",
    "sound": { "music": "เพลงเบา ปูทาง", "silence": [], "sfx": [ { "role": "whoosh", "at": 0.6 } ] } }
 ]
}'
new assets/CREDITS.md "| file | source | author | licence |
|---|---|---|---|"
new audio/sfx/CREDITS.md "| file | source | author | licence |
|---|---|---|---|"
for f in "$HERE"/*.sh "$HERE"/*.py "$HERE"/*.mjs; do [ -e "$f" ] && [ ! -e "scripts/$(basename "$f")" ] && cp "$f" scripts/ && echo "  + scripts/$(basename "$f")"; done
if [ -d "$HERE/../sfx" ] && [ ! -e audio/sfx/kit ]; then mkdir -p audio/sfx/kit && cp "$HERE"/../sfx/* audio/sfx/kit/ && echo "  + audio/sfx/kit/ (ชุดเสียงตั้งต้น CC0)"; fi
for c in "$HERE"/../cards/_example*.html; do [ -e "$c" ] && [ ! -e "cards/$(basename "$c")" ] && cp "$c" cards/ && echo "  + cards/$(basename "$c")"; done
echo "โฟลเดอร์งานพร้อม: $(pwd)"
echo "ต่อไป: npm i  (ติดตั้ง Hyperframes) · npx hyperframes browser ensure · bash scripts/preflight.sh ."
