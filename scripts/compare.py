#!/usr/bin/env python3
"""director skill — เฟรมของ ref คู่กับเฟรมของเรา ขนาดเต็ม (ต่างสัดส่วนได้ — สูงเท่ากัน วางข้างกัน)

    python3 scripts/compare.py REF_VIDEO T_REF OUR_VIDEO T_OURS [OUT.jpg] [--h 1280]

ความต่างระหว่าง "ใกล้" กับ "ใช่" มองไม่เห็นในภาพย่อ — เทียบเต็มขนาดทุกครั้งก่อนเสนอลุคและก่อนส่ง
OUT ตั้งต้น: review/compare/ref-<T_REF>_ours-<T_OURS>.jpg
"""
import subprocess
import sys
from pathlib import Path


def main() -> None:
    a = sys.argv[1:]
    h = int(a[a.index("--h") + 1]) if "--h" in a else 1280
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] != "--h")]
    if len(pos) < 4:
        sys.exit(__doc__)
    ref, tr, ours, to = pos[0], float(pos[1]), pos[2], float(pos[3])
    out = Path(pos[4]) if len(pos) > 4 else Path("review/compare") / f"ref-{tr:g}_ours-{to:g}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)                      # an old file would read as success
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{tr}", "-i", ref, "-ss", f"{to}", "-i", ours, "-filter_complex",
                    f"[0:v]scale=-2:{h}[a];[1:v]scale=-2:{h}[b];[a]pad=iw+24:ih:0:0:color=0x202020[a2];[a2][b]hstack,format=yuvj420p",
                    "-frames:v", "1", "-q:v", "3", "-strict", "unofficial", str(out)], check=True)
    if not out.exists():
        sys.exit(f"ไม่ได้ภาพ — เวลา {tr:g} / {to:g} วิ เกินความยาวคลิปหรือเปล่า")
    print(out)


if __name__ == "__main__":
    main()
