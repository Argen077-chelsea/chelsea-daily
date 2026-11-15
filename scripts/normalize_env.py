#!/usr/bin/env python3
"""director skill — แปลงไฟล์คีย์ที่ผู้ใช้มีอยู่แล้ว (ชื่อแปลกๆ) เป็น .env ที่ถูกรูปแบบ โดยไม่พิมพ์ค่าออกมา

    python3 scripts/normalize_env.py <ไฟล์คีย์ของผู้ใช้> [.env]

รับบรรทัดแบบ `pixabay-api=…`, `freesound client_secret: …`, `ElevenLabs key = …` → ชื่อมาตรฐาน · เก็บค่าที่มีอยู่แล้วใน .env
พิมพ์แค่ "✅ NAME ตั้งแล้ว" · เพิ่ม .env ใน .gitignore
"""
import re
import sys
from pathlib import Path

MAP = [  # (pattern on the lower-cased name, standard name)
    (r"eleven", "ELEVENLABS_API_KEY"), (r"firecrawl", "FIRECRAWL_API_KEY"),
    (r"pixabay", "PIXABAY_API_KEY"), (r"freesound.*(client.?id|id$)", "FREESOUND_CLIENT_ID"), (r"freesound", "FREESOUND_API_KEY"),
    (r"unsplash.*(secret)", "UNSPLASH_SECRET_KEY"), (r"unsplash.*(app.*id|application)", "UNSPLASH_APPLICATION_ID"), (r"unsplash", "UNSPLASH_ACCESS_KEY"),
]


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2] if len(sys.argv) > 2 else ".env")
    have = {}
    if dst.exists():
        for line in dst.read_text().splitlines():
            m = re.match(r"^([A-Z_]+)=(.*)$", line.strip())
            if m:
                have[m.group(1)] = m.group(2)
    for line in src.read_text().splitlines():
        m = re.match(r"^\s*([^=:#]+?)\s*[=:]\s*(.+?)\s*$", line)
        if not m:
            continue
        name, val = m.group(1).lower(), m.group(2).strip().strip('"').strip("'")
        std = next((n for pat, n in MAP if re.search(pat, name)), None)
        if std and val:
            have[std] = val
            print(f"✅ {std} ตั้งแล้ว")
    dst.write_text("".join(f"{k}={v}\n" for k, v in have.items()))
    dst.chmod(0o600)
    gi = dst.parent / ".gitignore"
    if ".env" not in (gi.read_text() if gi.exists() else ""):
        with gi.open("a") as f:
            f.write(".env\n")


if __name__ == "__main__":
    main()
