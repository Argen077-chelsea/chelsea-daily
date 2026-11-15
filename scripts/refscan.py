#!/usr/bin/env python3
"""director skill — อ่าน reference ให้ละเอียด: มันพูดอะไร และทุกเฟรมโชว์อะไร ในคำสั่งเดียว

    python3 scripts/refscan.py ลิงก์หรือไฟล์ refs/<ชื่อ> [--fps 12] [--no-words]

refs/<ชื่อ>/
  ref.mp4        คลิป (yt-dlp; ไฟล์ในเครื่องก๊อปมา)
  caption.txt    ข้อความในโพสต์ — เจ้าของบอกเองว่าคลิปนี้คืออะไร
  words.txt      สิ่งที่พูด พร้อมเวลา: ซับของแพลตฟอร์ม ถ้าไม่มีใช้ ElevenLabs Scribe (คีย์จาก .env)
  scene-NN.jpg   ทุกฉากที่ --fps (ตั้งต้น 12) ฉากยาวแบ่งทุก 4 วิ
  REF.md         ฉาก เวลา ความยาว จังหวะตัด คำพูดใต้แต่ละฉาก และแผ่นภาพที่ต้องอ่าน
แล้ว: อ่าน REF.md และ**ทุกแผ่น** → เขียน refs/<ชื่อ>.md (ไวยากรณ์: กล้อง ตัวหนังสือ ทรานสิชัน เสียง — ห้ามเอาเนื้อหา โลโก้ หรือไฟล์ของเขา)
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sheet import sheet  # noqa: E402

FFMPEG, FFPROBE = "ffmpeg", "ffprobe"
ENV = Path.cwd() / ".env"
CUT = 0.30          # scene score for a cut
CHUNK = 4.0         # s per sheet inside a long scene


def dur(v: Path) -> float:
    return float(subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)],
                                capture_output=True, text=True).stdout)


def fetch(src: str, out: Path) -> Path:
    ref = out / "ref.mp4"
    if Path(src).exists():
        shutil.copy(src, ref)
        return ref
    # picture + sound always: YouTube serves them as separate files (a bare "mp4" pick is often video-only)
    # YouTube sometimes answers one format with HTTP 500 — fall back to a smaller one rather than stop
    for fmt in ("bv*[height<=1080]+ba/b", "bv*[height<=720]+ba/b[height<=720]", "18/b"):
        for p in out.glob("ref.*"):
            p.unlink()
        r = subprocess.run(["yt-dlp", "-q", "--no-warnings", "-f", fmt, "--merge-output-format", "mp4", "-o", str(ref), src],
                           capture_output=True, text=True)
        if r.returncode == 0 and ref.exists():
            break
        print(f"yt-dlp ({fmt}) ไม่สำเร็จ — ลองรูปแบบเล็กลง: {r.stderr.strip().splitlines()[-1:] or ''}", file=sys.stderr)
    else:
        sys.exit(f"โหลดคลิปไม่ได้: {src} — ให้ผู้ใช้ส่งไฟล์มา แล้ว refscan.py <ไฟล์> {out}")
    meta = subprocess.run(["yt-dlp", "-q", "--skip-download", "--print", "%(title)s\n---\n%(description)s", src],
                          capture_output=True, text=True).stdout.strip()
    (out / "caption.txt").write_text(meta + "\n")
    subs = subprocess.run(["yt-dlp", "-q", "--skip-download", "--write-subs", "--write-auto-subs", "--sub-format", "vtt",
                           "--sub-langs", "th.*,en.*", "-o", str(out / "subs"), src], capture_output=True, text=True)
    return ref


def vtt_words(out: Path) -> list[tuple[float, str]]:
    vt = sorted(out.glob("subs*.vtt"))
    if not vt:
        return []
    rows, seen = [], set()
    for block in vt[0].read_text(errors="ignore").split("\n\n"):
        m = re.search(r"(\d+):(\d+):([\d.]+) -->", block)
        if not m:
            continue
        t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        text = re.sub(r"<[^>]+>", "", " ".join(l for l in block.splitlines() if "-->" not in l and l.strip())).strip()
        if text and text not in seen:
            seen.add(text)
            rows.append((t, text))
    return rows


def scribe(ref: Path, out: Path) -> list[tuple[float, str]]:
    key = next((l.split("=", 1)[1].strip() for l in ENV.read_text().splitlines() if l.startswith("ELEVENLABS_API_KEY=")), "") \
        if ENV.exists() else ""
    if not key:
        return []
    audio = out / "audio.mp3"
    r = subprocess.run([str(FFMPEG), "-v", "error", "-y", "-i", str(ref), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(audio)],
                       capture_output=True)
    if r.returncode != 0 or not audio.exists() or audio.stat().st_size < 2000:      # a clip with no sound: frames only
        return []
    bound = "----refscan"
    body = (f"--{bound}\r\nContent-Disposition: form-data; name=\"model_id\"\r\n\r\nscribe_v1\r\n"
            f"--{bound}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.mp3\"\r\nContent-Type: audio/mpeg\r\n\r\n").encode() \
        + audio.read_bytes() + f"\r\n--{bound}--\r\n".encode()
    req = urllib.request.Request("https://api.elevenlabs.io/v1/speech-to-text", data=body, method="POST",
                                 headers={"xi-api-key": key, "Content-Type": f"multipart/form-data; boundary={bound}"})
    try:
        got = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except Exception as e:                                   # noqa: BLE001 — words are a bonus, the frames still come
        print(f"refscan: Scribe ไม่สำเร็จ ({e}) — ได้แค่ภาพ", file=sys.stderr)
        return []
    rows, line, t0 = [], "", None
    for w in got.get("words", []):
        if w.get("type") == "spacing":
            line += w.get("text", "")
            continue
        if w.get("type") != "word":
            continue
        if t0 is None:
            t0 = float(w["start"])
        line += w["text"]
        if len(line) > 40 or w["text"].endswith((".", "?", "!")):
            rows.append((t0, line.strip()))
            line, t0 = "", None
    if line.strip():
        rows.append((t0 or 0.0, line.strip()))
    return rows


def cuts(ref: Path) -> list[float]:
    err = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(ref), "-vf",
                          f"scale=270:-2,select='gt(scene\\,{CUT})',metadata=print:file=-", "-an", "-f", "null", "-"],
                         capture_output=True, text=True).stdout
    ts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", err)]
    out: list[float] = []
    for t in ts:                       # one cut per 0.2 s
        if not out or t - out[-1] > 0.2:
            out.append(t)
    return out


def main() -> None:
    a = sys.argv[1:]
    fps = float(a[a.index("--fps") + 1]) if "--fps" in a else 12.0
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] != "--fps")]
    if len(pos) != 2:
        sys.exit(__doc__)
    out = Path(pos[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("scene-*.jpg"):
        f.unlink()
    ref = fetch(pos[0], out)
    total = dur(ref)
    words = [] if "--no-words" in a else (vtt_words(out) or scribe(ref, out))
    src = "ไม่มี" if not words else ("ซับของแพลตฟอร์ม" if list(out.glob("subs*.vtt")) else "ElevenLabs Scribe")
    (out / "words.txt").write_text("\n".join(f"{t:6.2f}  {w}" for t, w in words) + "\n")

    bounds = [0.0] + cuts(ref) + [total]
    scenes, sheets = [], []
    for s, e in zip(bounds, bounds[1:]):
        if e - s < 0.05:
            continue
        scenes.append((s, e))
        t = s
        while t < e - 0.02:
            t1 = min(e, t + CHUNK)
            p = out / f"scene-{len(sheets) + 1:02d}.jpg"
            sheet(ref, t, t1, p, fps, 8, 135)
            sheets.append((len(scenes), t, t1, p))
            t = t1
    lens = sorted(e - s for s, e in scenes)
    med = lens[len(lens) // 2] if lens else 0
    md = [f"# refscan — {pos[0]}", "", f"{total:.1f} วิ · {len(scenes)} ฉาก · ช็อตกลาง {med:.2f} วิ · "
          f"{len(scenes) / max(total, 0.1) * 10:.1f} ตัด/10 วิ · คำพูดจาก: {src} · ภาพ {fps:g} fps", ""]
    cap = (out / "caption.txt").read_text().strip() if (out / "caption.txt").exists() else ""
    if cap:
        md += ["## โพสต์เขียนว่า", "", "```", cap[:1500], "```", ""]
    md += ["## ฉาก", "", "| # | จาก | ถึง | ยาว | พูดว่า | แผ่นภาพ |", "|---|---|---|---|---|---|"]
    for n, (s, e) in enumerate(scenes, 1):
        said = " ".join(w for t, w in words if s - 0.2 <= t < e)[:120]
        sh = ", ".join(p.name for k, _, _, p in sheets if k == n)
        md.append(f"| {n} | {s:.2f} | {e:.2f} | {e - s:.2f} | {said} | {sh} |")
    md += ["", f"อ่านทุกแผ่น ({len(sheets)}) แล้วเขียนไวยากรณ์ (กล้อง · ตัวหนังสือ · ทรานสิชัน · เสียง) — ไม่เอาเนื้อหา", ""]
    (out / "REF.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:6]))
    print(out / "REF.md")


if __name__ == "__main__":
    main()
