#!/usr/bin/env bash
# director skill — เช็กเครื่องก่อนเริ่มงาน
#   bash preflight.sh [PROJECT_DIR]
# พิมพ์ตาราง เครื่องมือ | สถานะ | เวอร์ชัน | ต้องทำอะไร — ไม่ติดตั้งอะไรเอง (ถามผู้ใช้ก่อนทุกครั้ง)
# exit 0 = ของจำเป็นครบ · exit 1 = ขาดของจำเป็นอย่างน้อย 1 ตัว (ของ "แนะนำ" ขาดได้)
set -u
P="${1:-.}"
MISSING=0
rows=()
row() { rows+=("| $1 | $2 | $3 | $4 |"); }
need() { MISSING=1; }

ver() { "$@" 2>/dev/null | head -1 | tr -d '\r'; }

# --- ระบบ
OS="$(uname -s)"; ARCH="$(uname -m)"
if [ "$OS" = "Darwin" ]; then row "macOS" "✅" "$(sw_vers -productVersion 2>/dev/null) · $ARCH" "-"
else row "macOS" "⚠️" "$OS $ARCH" "v1 ทดสอบบน macOS เท่านั้น — ระบบอื่นอาจต้องปรับคำสั่งเอง"; fi

# --- จำเป็น
if command -v node >/dev/null; then
  NV="$(node -v)"; MAJ="${NV#v}"; MAJ="${MAJ%%.*}"
  if [ "$MAJ" -ge 18 ]; then row "Node.js ≥ 18" "✅" "$NV" "-"; else row "Node.js ≥ 18" "❌" "$NV" "อัปเดต: https://nodejs.org (LTS)"; need; fi
else row "Node.js ≥ 18" "❌" "-" "ติดตั้ง: https://nodejs.org (LTS) หรือ brew install node"; need; fi

if command -v python3 >/dev/null; then
  PV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
  if python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)'; then row "Python ≥ 3.10" "✅" "$PV" "-"
  else row "Python ≥ 3.10" "❌" "$PV" "brew install python@3.12"; need; fi
else row "Python ≥ 3.10" "❌" "-" "brew install python@3.12"; need; fi

if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then
  row "ffmpeg + ffprobe" "✅" "$(ffmpeg -version | head -1 | awk '{print $3}')" "-"
else row "ffmpeg + ffprobe" "❌" "-" "brew install ffmpeg"; need; fi

if [ -x "$P/node_modules/.bin/hyperframes" ]; then
  row "Hyperframes (render)" "✅" "$("$P/node_modules/.bin/hyperframes" --version 2>/dev/null | tail -1)" "-"
else row "Hyperframes (render)" "❌" "-" "ในโฟลเดอร์งาน: npm i hyperframes@0.6.45"; need; fi

CH=""
if [ -x "$P/node_modules/.bin/hyperframes" ]; then
  CH="$(cd "$P" && ./node_modules/.bin/hyperframes browser path 2>/dev/null | tail -1)"
fi
ARMCH="$(ls -d "$HOME"/.cache/hyperframes/chrome/chrome-headless-shell/mac_arm-*/chrome-headless-shell-mac-arm64/chrome-headless-shell 2>/dev/null | tail -1)"
if [ -n "$CH" ] && [ -x "$CH" ]; then
  if [ "$ARCH" = "arm64" ] && [[ "$CH" == *mac-x64* ]]; then
    if [ -n "$ARMCH" ]; then row "Chrome (headless)" "✅" "มีรุ่น arm64" "render_card.py เลือกรุ่น arm64 ให้เอง — ไม่ต้องทำอะไร"
    else row "Chrome (headless)" "⚠️" "x64 ผ่าน Rosetta" "ช้ากว่า ~2 เท่า — ดาวน์โหลดรุ่น arm64 แล้วตั้ง HYPERFRAMES_BROWSER_PATH"; fi
  else row "Chrome (headless)" "✅" "$(basename "$(dirname "$(dirname "$CH")")")" "-"; fi
else row "Chrome (headless)" "❌" "-" "npx hyperframes browser ensure — โหลด Chrome (~150 MB) ไปที่ ~/.cache/hyperframes (นอกโฟลเดอร์งาน: ขออนุญาตก่อน)"; need; fi

if python3 -c 'import numpy' 2>/dev/null; then row "numpy (วัดเสียง)" "✅" "$(python3 -c 'import numpy;print(numpy.__version__)')" "-"
else row "numpy (วัดเสียง)" "❌" "-" "python3 -m pip install --user numpy (review.py / beats.py ใช้)"; need; fi

# --- แนะนำ (ขาดได้ แต่จะทำบางอย่างไม่ได้)
BL="$(command -v blender 2>/dev/null || true)"
[ -z "$BL" ] && [ -x /Applications/Blender.app/Contents/MacOS/Blender ] && BL=/Applications/Blender.app/Contents/MacOS/Blender
if [ -n "$BL" ]; then row "Blender (ช็อตสินค้า 3D)" "✅" "$("$BL" --version 2>/dev/null | head -1 | awk '{print $2}') · $BL" "-"
else row "Blender (ช็อตสินค้า 3D)" "⚠️" "-" "เฉพาะโฆษณาสินค้า 3D พรีเมียม: brew install --cask blender (ฟรี ~400 MB — ขออนุญาตก่อน) · ไม่มีก็ใช้ Three.js ในการ์ด"; fi
if command -v yt-dlp >/dev/null; then row "yt-dlp (โหลดคลิป ref)" "✅" "$(yt-dlp --version)" "-"
else row "yt-dlp (โหลดคลิป ref)" "⚠️" "-" "brew install yt-dlp — ไม่มีก็ได้ ถ้าผู้ใช้ส่งไฟล์ ref มาเอง"; fi

ENV="$P/.env"
key() { [ -f "$ENV" ] && grep -Eq "^$1=.+" "$ENV"; }
if key ELEVENLABS_API_KEY; then row "ElevenLabs key" "✅" "ตั้งแล้ว" "-"
else row "ElevenLabs key" "⚠️" "-" "เสียงพากย์ไทย + ถอดคำไทย (Scribe): ใส่ ELEVENLABS_API_KEY ใน .env"; fi
if key FREESOUND_API_KEY; then row "FREESOUND_API_KEY" "✅" "ตั้งแล้ว" "-"; else row "FREESOUND_API_KEY" "⚠️" "-" "ค้นเสียงประกอบเพิ่ม — ไม่มีก็ได้ (มีชุดเสียง CC0 ติดมา)"; fi
if key PIXABAY_API_KEY; then row "PIXABAY_API_KEY" "✅" "ตั้งแล้ว" "-"; else row "PIXABAY_API_KEY" "⚠️" "-" "รูป/วิดีโอสต็อก — ไม่มีก็ได้ (ใช้รูปของผู้ใช้หรือวาดด้วยโค้ด)"; fi
if key UNSPLASH_ACCESS_KEY; then row "UNSPLASH_ACCESS_KEY" "✅" "ตั้งแล้ว" "-"; else row "UNSPLASH_ACCESS_KEY" "⚠️" "-" "รูปคุณภาพสูง — ไม่มีก็ได้"; fi

echo "| เครื่องมือ | สถานะ | เวอร์ชัน | ต้องทำอะไร |"
echo "|---|---|---|---|"
printf '%s\n' "${rows[@]}"
echo
if [ "$MISSING" = 1 ]; then echo "❌ ขาดของจำเป็น — ถามผู้ใช้ทีละข้อก่อนติดตั้ง แล้วรันใหม่"; exit 1; fi
echo "✅ ของจำเป็นครบ"
