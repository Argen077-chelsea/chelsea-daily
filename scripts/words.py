#!/usr/bin/env python3
"""director skill — ถอดเสียงพากย์เป็นคำพร้อมเวลา (ElevenLabs Scribe) → audio/words.json

    python3 scripts/words.py [audio/vo.mp3 | assets/video/<คลิปคนพูด>.mp4] [--lang th]

คลิปคนพูด: ถอดจากไฟล์วิดีโอได้เลย แล้วต่อด้วย scripts/talk_cut.py (ตัดช่วงเงียบ/เทคเสีย + เลื่อนเวลาคำตาม)

audio/words.json = [{"text": "หาย", "start": 1.23, "end": 1.41}, …] — การ์ดใช้ผ่าน at("คำ") (render_card.py)
Scribe ส่งภาษาไทยมาเป็นคำ หรือบางครั้งทีละตัวอักษร — at() ค้นจากข้อความที่ต่อกันแล้ว จึงใช้ได้ทั้งสองแบบ
คีย์: ELEVENLABS_API_KEY ใน .env (ไม่พิมพ์ค่าออกมา)
พิมพ์: ข้อความที่ถอดได้ ตัดบรรทัดตามช่วงหยุดจริงในเสียง · ช่วงเงียบ ≥ 0.25 วิ (วัดจากเสียง ไม่ใช่ช่องว่างระหว่างคำ —
Scribe มักยืดคำคลุมช่วงเงียบ) → audio/pauses.json · ถ้า script.md ล็อกแล้ว: เทียบบทกับเสียงจริง บอกส่วนที่หาย/เกิน
ถ้าคำสำคัญสะกดต่าง ใช้ at(["แบบที่1", "แบบที่2"])
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJ = Path.cwd()


def key() -> str:
    env = PROJ / ".env"
    for line in (env.read_text().splitlines() if env.exists() else []):
        if line.startswith("ELEVENLABS_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


def scribe(audio: Path, lang: str) -> dict:
    k = key()
    if not k:
        sys.exit("ไม่มี ELEVENLABS_API_KEY ใน .env — ใส่คีย์ก่อน (SKILL.md §0.3)")
    small = PROJ / "audio" / ".scribe.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(audio), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(small)],
                   check=True)
    b = "----director"
    fields = {"model_id": "scribe_v1", "language_code": lang, "timestamps_granularity": "word"}
    body = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n".encode() for n, v in fields.items())
    body += (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"vo.mp3\"\r\nContent-Type: audio/mpeg\r\n\r\n").encode()
    body += small.read_bytes() + f"\r\n--{b}--\r\n".encode()
    small.unlink(missing_ok=True)
    req = urllib.request.Request("https://api.elevenlabs.io/v1/speech-to-text", data=body, method="POST",
                                 headers={"xi-api-key": k, "Content-Type": f"multipart/form-data; boundary={b}"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=600).read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Scribe ตอบ {e.code}: {e.read()[:300]!r}")


def pauses(audio: Path, min_s: float = 0.25) -> list[tuple[float, float]]:
    """Silences from the audio itself: 50 ms RMS, threshold halfway (in dB) between the room and the voice."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    import array, math
    x = array.array("h", raw)
    hop = 800
    db = [20 * math.log10(math.sqrt(sum(v * v for v in x[i:i + hop]) / hop) + 1e-9) for i in range(0, len(x) - hop, hop)]
    if not db:
        return []
    srt = sorted(db)
    room, voice = srt[int(len(srt) * 0.10)], srt[int(len(srt) * 0.90)]
    thr = (room + voice) / 2
    out, start = [], None
    for k, v in enumerate(db + [voice]):
        t = k * hop / 16000
        if v < thr and start is None:
            start = t
        elif v >= thr and start is not None:
            if t - start >= min_s:
                out.append((round(start, 2), round(t, 2)))
            start = None
    return out


def script_text() -> str:
    """script.md's spoken lines once it is LOCKED ('' otherwise): drop headers, notes, [tags] and markup."""
    f = PROJ / "script.md"
    if not f.exists() or "LOCKED" not in f.read_text():
        return ""
    keep = []
    for line in f.read_text().splitlines():
        if line.startswith(("#", "(", ">", "|", "---", "เสียง:", "ตั้งค่า:", "On-screen", "คีย์เวิร์ด")) or "LOCKED" in line:
            continue
        keep.append(re.sub(r"\[[^\]]*\]|[*_`]", "", line))
    return "".join(keep)


def main() -> None:
    a = sys.argv[1:]
    if "-h" in a or "--help" in a:
        sys.exit(__doc__)
    lang = a[a.index("--lang") + 1] if "--lang" in a else "th"
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] != "--lang")]
    audio = Path(pos[0]) if pos else PROJ / "audio" / "vo.mp3"
    if not audio.exists():
        sys.exit(f"ไม่เจอไฟล์เสียง {audio}")
    got = scribe(audio, lang)
    words = [{"text": w["text"], "start": round(float(w["start"]), 3), "end": round(float(w["end"]), 3)}
             for w in got.get("words", []) if w.get("type") == "word" and w["text"].strip()]
    out = PROJ / "audio" / "words.json"
    out.write_text(json.dumps(words, ensure_ascii=False, indent=0))
    gaps = pauses(audio)
    (PROJ / "audio" / "pauses.json").write_text(json.dumps(gaps))
    # one printed line per stretch of speech between real pauses (Scribe may give Thai one character per token)
    line, t0, gi = "", None, 0
    LEAD = "เแโใไ"                                 # Thai leading vowels: never end a printed line on one ("นะใ / ห้" → "นะ / ให้")
    for w in words:
        while gi < len(gaps) and gaps[gi][1] <= w["start"] + 0.01:
            if line:
                carry = ""
                while line and line[-1] in LEAD:
                    carry, line = line[-1] + carry, line[:-1]
                if line:
                    print(f"{t0:6.2f}  {line}")
                line, t0 = carry, (w["start"] if carry else None)
            print(f"        ··· เงียบ {gaps[gi][0]:.2f}–{gaps[gi][1]:.2f}")
            gi += 1
        t0 = w["start"] if t0 is None else t0
        line += w["text"]
    if line:
        print(f"{t0:6.2f}  {line}")
    spoken = "".join(w["text"] for w in words).replace(" ", "")
    plan = script_text().replace(" ", "")
    if plan:
        sm = difflib.SequenceMatcher(None, plan, spoken, autojunk=False)
        diff = [(op, plan[a:b], spoken[c:d]) for op, a, b, c, d in sm.get_opcodes() if op != "equal"]
        print(f"เทียบกับบทที่ล็อก: ตรง {sm.ratio():.0%}" + ("" if not diff else " — ต่างกัน:"))
        for op, p_, s_ in diff[:15]:
            print(f"   บท: '{p_}'  →  เสียง: '{s_}'")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)],
                               capture_output=True, text=True).stdout or 0)
    # the clipped-tail warning is about generated voice-overs (eleven_v3); a recording or a video ending mid-word is normal
    if words and dur - words[-1]["end"] < 0.15 and audio.suffix.lower() in (".mp3", ".wav", ".m4a") and "vo" in audio.stem.lower():
        print(f"⚠️ คำสุดท้ายจบที่ {words[-1]['end']:.2f} วิ ไฟล์จบ {dur:.2f} วิ — เสียงพากย์อาจโดนตัดท้าย (eleven_v3 ทำบ่อย) · "
              f"ฟังท้ายไฟล์ ถ้าคำยังครบ เติมหาง: ffmpeg -i {audio} -af \"afade=t=out:st={max(0, dur - 0.04):.2f}:d=0.04,apad=pad_dur=0.6\" audio/vo_padded.mp3")
    print(f"{len(words)} คำ → {out}")


if __name__ == "__main__":
    main()
