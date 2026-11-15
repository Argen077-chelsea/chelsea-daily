#!/usr/bin/env python3
"""director skill — ช่วงหนึ่งของวิดีโอในภาพเดียว: ทุกเฟรมที่ --fps เรียงเป็นตาราง มีเวลาใต้ทุกช่อง

    python3 scripts/sheet.py VIDEO FROM TO [OUT.jpg] [--fps 15] [--cols 10] [--width 120]

ภาพนิ่งไม่กี่ภาพบอกไม่ได้ว่าระหว่างนั้นเกิดอะไร (ของโผล่ทั้งก้อน หายเร็วไป นิ่งตาย) — ต้องเห็นทั้งการเคลื่อนไหว
"""
from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path


def sheet(video: Path, t0: float, t1: float, out: Path, fps: float = 15, cols: int = 10, width: int = 120) -> Path:
    n = max(1, round((t1 - t0) * fps))
    rows = math.ceil(n / cols)
    label = ("drawtext=text='%{pts\\:hms}':x=4:y=h-th-4:fontsize=" + str(max(10, width // 8)) +
             ":fontcolor=white:box=1:boxcolor=black@0.6,")
    vf = f"fps={fps},scale={width}:-2,setpts=PTS+{t0}/TB,{label}tile={cols}x{rows}:padding=3:margin=3:color=0x202020"
    res = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(video),
                          "-vf", vf, "-frames:v", "1", str(out)], capture_output=True, text=True)
    if res.returncode != 0:          # Homebrew's ffmpeg has no drawtext: same sheet, times drawn with Pillow if it is there
        vf = f"fps={fps},scale={width}:-2,tile={cols}x{rows}:padding=3:margin=3:color=0x202020"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(video),
                        "-vf", vf, "-frames:v", "1", str(out)], check=True)
        try:
            from PIL import Image, ImageDraw
            im = Image.open(out); dr = ImageDraw.Draw(im)
            try:
                from PIL import ImageFont
                fnt = ImageFont.load_default(size=max(11, width // 10))
            except Exception:
                fnt = None
            tw = (im.width - 6) / cols; th = (im.height - 6) / rows
            for i in range(n):
                x, y = 3 + (i % cols) * tw, 3 + (i // cols) * th
                lab = f"{t0 + i / fps:.2f}"
                fs = max(11, width // 10) if fnt else 10
                dr.rectangle([x + 2, y + th - fs - 8, x + 8 + int(fs * 0.62 * len(lab)), y + th - 3], fill=(0, 0, 0))
                dr.text((x + 5, y + th - fs - 6), lab, fill=(255, 255, 255), font=fnt)
            im.save(out)
        except ImportError:
            print(f"(ไม่มีเวลาใต้ช่อง — ช่องที่ i นับซ้าย→ขวา บน→ล่าง เริ่ม 0 = {t0:g} + i/{fps:g} วิ)", file=sys.stderr)
    return out


def main() -> None:
    a = sys.argv[1:]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d          # noqa: E731
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or not a[i - 1].startswith("--"))]
    if len(pos) < 3:
        sys.exit(__doc__)
    v, t0, t1 = Path(pos[0]), float(pos[1]), float(pos[2])
    out = Path(pos[3]) if len(pos) > 3 else v.with_name(f"{v.stem}-sheet-{t0:g}-{t1:g}.jpg")
    print(sheet(v, t0, t1, out, float(opt("--fps", "15")), int(opt("--cols", "10")), int(opt("--width", "120"))))


if __name__ == "__main__":
    main()
