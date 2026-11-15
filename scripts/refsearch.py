#!/usr/bin/env python3
"""director skill — ไม่มี ref? หาให้: ค้น YouTube แล้วทำแผ่นตัวอย่างให้เลือกเป็นเบอร์ → เลือกแล้วอ่านละเอียดต่อ (refscan)

    python3 scripts/refsearch.py "<คำค้น อังกฤษ>" [--n 6] [--max 90] [--vertical]      ค้น + แผ่นตัวอย่าง
    python3 scripts/refsearch.py --pick 3 [refs/<ชื่อ>]                                เลือกเบอร์ 3 → refscan

คำค้นที่ได้ผล: แนว + ประเภท + "ad"/"motion graphics"/"promo" เช่น "saas product launch motion graphics ad",
"kinetic typography promo", "app ad 3d ui animation" · ภาษาอังกฤษเจอของดีกว่า · --vertical = เอาคลิปแนวตั้งก่อน (Shorts)
ผล: refs/_search/CANDIDATES.md (เบอร์ ชื่อ ความยาว ลิงก์) + refs/_search/candidates.jpg (แถวละคลิป 5 เฟรมจาก 20 วิแรก)
ใช้ ref เพื่อถอด "ไวยากรณ์" (จังหวะ กล้อง ตัวหนังสือ ทรานสิชัน เสียง) เท่านั้น — ห้ามเอาเนื้อหา โลโก้ ฟุตเทจของเขาไปใช้
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path.cwd() / "refs" / "_search"


def dur(v: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)],
                       capture_output=True, text=True).stdout.strip()
    return float(r or 0)


def size(v: Path) -> tuple[int, int]:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                        str(v)], capture_output=True, text=True).stdout.strip().split(",")
    return (int(r[0]), int(r[1])) if len(r) == 2 and r[0] else (0, 0)


def search(q: str, n: int, max_s: float, vertical: bool) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*"):
        if f.is_file():
            f.unlink()
    raw = subprocess.run(["yt-dlp", "--flat-playlist", "--print", "%(id)s\t%(duration)s\t%(title)s\t%(url)s",
                          f"ytsearch{n * 4}:{q}"], capture_output=True, text=True).stdout
    found = []
    for line in raw.splitlines():
        p = line.split("\t")
        if len(p) < 4 or p[1] in ("NA", "None", ""):
            continue
        d = float(p[1])
        if 8 <= d <= max_s:
            found.append({"id": p[0], "dur": d, "title": p[2], "url": p[3]})
    if not found:
        sys.exit(f"ไม่เจอคลิปยาว 8–{max_s:g} วิ สำหรับ '{q}' — ลองคำค้นอื่น หรือ --max ยาวขึ้น")
    rows = []
    for c in found:
        if len(rows) >= n:
            break
        clip = OUT / f"{c['id']}.mp4"
        subprocess.run(["yt-dlp", "-q", "--no-warnings", "-f", "bv*[height<=480][height>=240][ext=mp4]/bv*[height<=480]/wv*/w",
                        "--download-sections", "*0-20", "-o", str(clip), c["url"]], capture_output=True)
        if not clip.exists() or dur(clip) < 3:
            continue
        w, h = size(clip)
        c["vertical"] = h > w
        rows.append(c)
    if vertical:
        rows.sort(key=lambda c: not c["vertical"])
        if not any(c["vertical"] for c in rows):
            print("(ไม่เจอคลิปแนวตั้ง — ลองเติม 'shorts' หรือ 'reels' ในคำค้น · ref แนวนอนก็ถอดไวยากรณ์ได้ แค่ต้องจัดเฟรมใหม่เป็น 9:16)")
    strips = []
    for k, c in enumerate(rows, 1):
        clip = OUT / f"{c['id']}.mp4"
        d = dur(clip)
        ins = sum([["-ss", f"{d * (i + 0.5) / 5:.2f}", "-i", str(clip)] for i in range(5)], [])
        fil = "".join(f"[{i}:v]scale=-2:200,pad=ceil(iw/2)*2:200[v{i}];" for i in range(5)) + \
            "".join(f"[v{i}]" for i in range(5)) + "hstack=5[s]"
        strip = OUT / f"_{k:02d}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fil, "-map", "[s]", "-frames:v", "1", str(strip)],
                       capture_output=True)
        lab = OUT / f"_{k:02d}L.jpg"                                   # the number on the left, readable without drawtext
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(strip), "-vf",
                            f"pad=iw+70:ih:70:0:color=0x111111,drawtext=text='{k}':x=18:y=80:fontsize=44:fontcolor=white",
                            str(lab)], capture_output=True)
        if r.returncode != 0:                                          # no drawtext (Homebrew ffmpeg): Pillow, else order only
            try:
                from PIL import Image, ImageDraw
                im = Image.open(strip); big = Image.new("RGB", (im.width + 70, im.height), (17, 17, 17)); big.paste(im, (70, 0))
                d = ImageDraw.Draw(big); d.rectangle([10, 66, 60, 134], fill=(255, 255, 255))
                try:
                    from PIL import ImageFont
                    f = ImageFont.load_default(size=44)
                except Exception:                                   # older Pillow: small built-in font
                    f = None
                d.text((22, 74) if f else (30, 94), str(k), fill=(0, 0, 0), font=f)
                big.save(lab); r = subprocess.CompletedProcess([], 0)
            except ImportError:
                pass
        strips.append(lab if r.returncode == 0 else strip)
        c["n"] = k
    if strips:
        ins = sum([["-i", str(s)] for s in strips], [])
        fil = "".join(f"[{i}:v]scale=1400:-2,pad=1400:ih+8:0:0:color=0x202020[r{i}];" for i in range(len(strips))) + \
            "".join(f"[r{i}]" for i in range(len(strips))) + f"vstack={len(strips)}" if len(strips) > 1 else "[0:v]scale=1400:-2"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fil, "-frames:v", "1", str(OUT / "candidates.jpg")])
    for f in OUT.glob("_*.jpg"):
        f.unlink()
    md = [f"# ref ที่หาได้ — \"{q}\"", "", "แผ่นตัวอย่าง: `refs/_search/candidates.jpg` — แถวละคลิป **เรียงตามเบอร์จากบนลงล่าง** (แถวบนสุด = 1)", "",
          "| # | ชื่อ | ยาว | แนวตั้ง | ลิงก์ |", "|---|---|---|---|---|"]
    md += [f"| {c['n']} | {c['title'][:70].replace('|', '/')} | {c['dur']:.0f} วิ | {'✓' if c['vertical'] else ''} | {c['url']} |" for c in rows]
    md += ["", "เลือก: `python3 scripts/refsearch.py --pick <เบอร์>` → อ่านละเอียดด้วย refscan"]
    (OUT / "CANDIDATES.md").write_text("\n".join(md) + "\n")
    (OUT / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False))
    print("\n".join(md))


def pick(n: int, dest: Path | None) -> None:
    rows = json.loads((OUT / "candidates.json").read_text())
    c = next((r for r in rows if r["n"] == n), None)
    if not c:
        sys.exit(f"ไม่มีเบอร์ {n} — ดู refs/_search/CANDIDATES.md")
    dest = dest or Path.cwd() / "refs" / (re.sub(r"[^a-z0-9]+", "-", c["title"].lower()).strip("-")[:30] or c["id"])
    subprocess.run([sys.executable, str(HERE / "refscan.py"), c["url"], str(dest)], check=True)
    print(f"ref = เบอร์ {n}: {c['title']} → {dest} (จดใน PROGRESS.md ว่าเลือกเพราะอะไร)")


def main() -> None:
    a = sys.argv[1:]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d          # noqa: E731
    if "--pick" in a:
        rest = [x for i, x in enumerate(a) if not x.startswith("--") and a[i - 1] != "--pick"]
        pick(int(opt("--pick", "1")), Path(rest[0]) if rest else None)
        return
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--n", "--max"))]
    if not pos:
        sys.exit(__doc__)
    search(pos[0], int(opt("--n", "6")), float(opt("--max", "90")), "--vertical" in a)


if __name__ == "__main__":
    main()
