#!/usr/bin/env python3
"""director skill — ตัดคลิปคนพูด: ตัดช่วงเงียบ + เทคที่ไม่ใช้ แล้ว "เลื่อนเวลาคำตาม" ให้การ์ดยังลงตรงคำพูด (รันในโฟลเดอร์งาน)

    python3 scripts/words.py assets/video/<ไฟล์ดิบ>.mp4          # ถอดคำ + หาช่วงเงียบจากไฟล์ดิบก่อน
    python3 scripts/talk_cut.py assets/video/<ไฟล์ดิบ>.mp4 [--pause 0.4] [--pad 0.08] [--drop 0-2.1,14.2-17.8] [--fit crop|pad]

  --pause S   ตัดช่วงเงียบที่ยาว ≥ S วิ (ค่าเริ่ม 0.4 — คนพูดเร็วใช้ 0.3, อยากให้หายใจได้ใช้ 0.6)
  --pad S     เหลือเงียบไว้หัว-ท้ายรอยตัดข้างละ S วิ (ค่าเริ่ม 0.08 — คำไม่โดนกิน)
  --drop A-B  ช่วงที่ไม่เอา (วินาทีของไฟล์ดิบ, คั่นด้วย ,) — เทคพูดผิด/พูดซ้ำ/มือบังกล้อง/ลุกนั่ง
              หาจากบทที่ words.py พิมพ์ (มีเวลาทุกบรรทัด): ประโยคเดียวกันพูด 2 รอบ = เก็บรอบหลัง (ปกติดีกว่า) ถามผู้ใช้ถ้าไม่แน่ใจ
  --fit       ไฟล์ดิบไม่ใช่ 9:16: crop = ตัดกลางภาพให้เต็มจอ (ค่าเริ่ม) · pad = ย่อทั้งภาพ เติมขอบดำ

ได้:
  renders/talk-cut.mp4      วิดีโอที่ตัดแล้ว 1080×1920 30 fps (ใช้ในการ์ด: <video src="renders/talk-cut.mp4">)
  audio/vo.mp3              เสียงของคลิปที่ตัดแล้ว (storyboard "vo" ชี้ไฟล์นี้ — assemble ใช้เป็นเสียงหลัก)
  audio/words.json          คำ + เวลา ในเวลาของคลิปที่ตัดแล้ว (ของเดิมเก็บไว้ที่ audio/words-raw.json) — at("คำ") ใช้ได้ต่อทันที
  audio/pauses.json         ช่วงเงียบของคลิปที่ตัดแล้ว
  audio/cuts.json           วินาทีที่มีรอยตัด → ใส่ใน storyboard "cuts_ok" (review จะไม่ฟ้องว่าภาพกระโดดตรงนั้น)
รันซ้ำได้: อ่านจาก words-raw.json เสมอ (ไม่ตัดซ้ำบนของที่ตัดแล้ว)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJ = Path.cwd()
sys.path.insert(0, str(Path(__file__).resolve().parent))


def dur(f: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                capture_output=True, text=True).stdout or 0)


def ranges(arg: str) -> list[tuple[float, float]]:
    out = []
    for part in filter(None, arg.split(",")):
        a, b = part.split("-")
        out.append((float(a), float(b)))
    return out


def subtract(keep: list[tuple[float, float]], cut: tuple[float, float]) -> list[tuple[float, float]]:
    a, b = cut
    out = []
    for s, e in keep:
        if b <= s or a >= e:
            out.append((s, e))
            continue
        if a > s:
            out.append((s, a))
        if b < e:
            out.append((b, e))
    return out


def main() -> None:
    av = sys.argv[1:]
    if not av or "-h" in av or "--help" in av:
        sys.exit(__doc__)
    opt = lambda f, d: av[av.index(f) + 1] if f in av else d  # noqa: E731
    src = Path(av[0])
    if not src.exists():
        sys.exit(f"ไม่เจอไฟล์ {src}")
    raw_words = PROJ / "audio" / "words-raw.json"
    words_f, pauses_f = PROJ / "audio" / "words.json", PROJ / "audio" / "pauses.json"
    if not raw_words.exists():
        if not words_f.exists():
            sys.exit("ยังไม่มี audio/words.json — รัน python3 scripts/words.py " + str(src) + " ก่อน (ถอดคำ + หาช่วงเงียบจากไฟล์ดิบ)")
        raw_words.write_text(words_f.read_text())
        (PROJ / "audio" / "pauses-raw.json").write_text(pauses_f.read_text() if pauses_f.exists() else "[]")
    words = json.loads(raw_words.read_text())
    pauses = json.loads((PROJ / "audio" / "pauses-raw.json").read_text())
    D = dur(src)
    min_pause, pad = float(opt("--pause", "0.4")), float(opt("--pad", "0.08"))

    keep = [(0.0, D)]
    for a, b in pauses:                       # silences (from the audio itself) → cut, leaving a little air each side
        if b - a >= min_pause:
            keep = subtract(keep, (a + (pad if a > 0.01 else 0), b - (pad if b < D - 0.01 else 0)))
    for a, b in ranges(opt("--drop", "")):    # takes the user doesn't want
        keep = subtract(keep, (max(0, a), min(D, b)))
    keep = [(round(s, 3), round(e, 3)) for s, e in keep if e - s >= 0.12]   # a sliver < 0.12 s is a flash, not speech
    if not keep:
        sys.exit("ตัดแล้วไม่เหลืออะไร — ลด --pause หรือเช็ก --drop")

    # one ffmpeg pass: trim each kept piece (picture + sound, 10 ms fades so no clicks), join, fit to 1080×1920 30 fps
    fit = ("scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" if opt("--fit", "crop") == "crop"
           else "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2")
    f, cat = [], ""
    for i, (s, e) in enumerate(keep):
        f.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS,fps=30,{fit},setsar=1[v{i}]")
        f.append(f"[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d=0.01,afade=t=out:st={max(0, e - s - 0.01):.3f}:d=0.01[a{i}]")
        cat += f"[v{i}][a{i}]"
    f.append(f"{cat}concat=n={len(keep)}:v=1:a=1[v][a]")
    out = PROJ / "renders" / "talk-cut.mp4"
    out.parent.mkdir(exist_ok=True)
    script = PROJ / "cache" / "talk_cut.filter"
    script.parent.mkdir(exist_ok=True)
    script.write_text(";\n".join(f))
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-filter_complex_script", str(script), "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(out)], capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg ตัดไม่ผ่าน:\n" + r.stderr[-800:])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vn", "-c:a", "libmp3lame", "-b:a", "192k",
                    str(PROJ / "audio" / "vo.mp3")], check=True)

    # retime every word into the cut clip's time; a word that lost its place in a cut is dropped
    def new_t(t: float) -> float | None:
        o = 0.0
        for s, e in keep:
            if s - 0.02 <= t <= e + 0.02:
                return round(o + min(max(t, s), e) - s, 3)
            o += e - s
        return None
    moved, lost_drop, lost_cut = [], [], []
    drops = ranges(opt("--drop", ""))
    for w in words:
        a, b = new_t(w["start"]), new_t(w["end"])
        if a is not None and b is not None and b >= a:
            moved.append({**w, "start": a, "end": b})
        elif any(s - 0.05 <= w["start"] <= e + 0.05 for s, e in drops):
            lost_drop.append(w["text"])
        else:
            lost_cut.append(w["text"])
    words_f.write_text(json.dumps(moved, ensure_ascii=False, indent=0))
    import words as W                          # silences of the cut clip (for the next beats)
    pauses_f.write_text(json.dumps(W.pauses(out)))
    cuts, o = [], 0.0
    for s, e in keep[:-1]:
        o += e - s
        cuts.append(round(o, 2))
    (PROJ / "audio" / "cuts.json").write_text(json.dumps(cuts))

    total = sum(e - s for s, e in keep)
    print(f"{D:.1f} วิ → {total:.1f} วิ · {len(keep)} ช่วง · ตัดออก {D - total:.1f} วิ · คำ {len(words)} → {len(moved)}")
    print(f"  {out}  ·  audio/vo.mp3  ·  audio/words.json (เวลาใหม่)  ·  audio/cuts.json")
    print(f'  storyboard: "vo": "audio/vo.mp3", "cuts_ok": {json.dumps(cuts)}')
    if lost_drop:
        print(f"  ตัดทิ้งตาม --drop (ตั้งใจ): {''.join(lost_drop)[:80]}")
    if lost_cut:
        print(f"  ⚠️ คำที่หายไปกับรอยตัดช่วงเงียบ: {''.join(lost_cut)[:80]} — ถ้าเป็นคำสำคัญ ลด --pause หรือเพิ่ม --pad")
    print("  ดูก่อนทำการ์ด: เปิด renders/talk-cut.mp4 ฟังรอยตัดทุกจุด (สะดุดตรงไหน ขยับ --drop ตรงนั้น)")


if __name__ == "__main__":
    main()
