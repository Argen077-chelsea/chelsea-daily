#!/usr/bin/env python3
"""director skill — อ่านเพลง: จังหวะ จุดกระแทก ช่วงเงียบ จุดจบจริง → audio/beats.json (ใช้แทน words.json เมื่อคลิปไม่มีเสียงพากย์)

    python3 scripts/beats.py audio/music/<เพลง>.mp3 [--offset 0.35]

  --offset S   ตัดหัวเพลงทิ้ง S วิ (ให้ drop ลงเฟรมที่ต้องการ) — ใส่ค่าเดียวกันใน storyboard "music": {"offset": S}

พิมพ์: เส้นความดังทีละ 0.25 วิ (ดูด้วยตาว่า build/drop/เงียบอยู่ตรงไหน) · BPM โดยประมาณ · จุดกระแทก (เสียงต่ำกระโดดขึ้น ≥ 6 dB) ·
ช่วงเงียบ · เพลงจบจริงวินาทีไหน — **เพลงจาก AI บางทีจบก่อนเวลาที่สั่ง หรือมีแต่เสียงกระแทกห่างๆ: เตือนให้สร้างใหม่**
ในการ์ด: hit(n) = วินาทีของการ์ดของจุดกระแทกที่ n (0 = อันแรกที่อยู่ในการ์ด) · beat(n) = จังหวะที่ n ในการ์ด
(render_card.py ใส่ให้เองเมื่อมี audio/beats.json — เหมือน at("คำ") ของเสียงพากย์)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 22050


def load(f: Path, offset: float = 0.0) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{offset:.3f}", "-i", str(f), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    if r.returncode != 0:
        sys.exit(f"อ่านไฟล์เสียงไม่ได้: {f}")
    return np.frombuffer(r.stdout, np.float32)


def analyse(f: Path, offset: float = 0.0) -> dict:
    x = load(f, offset)
    dur = len(x) / SR
    hop = int(SR * 0.02)                                           # 20 ms
    n = len(x) // hop
    fr = x[: n * hop].reshape(n, hop)
    rms = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    # เสียงต่ำ (kick/sub/impact): low-pass ง่ายๆ ด้วยค่าเฉลี่ยเคลื่อนที่ ~ 180 Hz
    k = int(SR / 180)
    lo = np.convolve(x, np.ones(k) / k, "same")[: n * hop].reshape(n, hop)
    low = 20 * np.log10(np.sqrt((lo ** 2).mean(1)) + 1e-9)
    on = np.maximum(0, np.diff(low, prepend=low[0]))              # พลังงานต่ำที่ "เพิ่มขึ้น" = จุดตี
    full_on = np.maximum(0, np.diff(rms, prepend=rms[0]))
    # จุดกระแทก: เสียงต่ำกระโดด ≥ 6 dB ภายใน 60 ms และดังเกิน −30 dBFS · ห่างกันอย่างน้อย 0.18 วิ
    jump = np.array([low[i] - low[max(0, i - 3)] for i in range(n)])
    hits, last = [], -1.0
    for i in np.argsort(-jump):
        t = i * 0.02
        if jump[i] < 6 or rms[i] < -30:
            break
        if all(abs(t - h) > 0.18 for h in hits):
            hits.append(round(float(t), 2))
    hits.sort()
    # BPM: autocorrelation ของ onset ในช่วง 70–180 bpm
    o = (on + 0.5 * full_on); o = o - o.mean()
    ac = np.correlate(o, o, "full")[len(o) - 1:]
    lags = np.arange(len(ac)) * 0.02
    band = (lags >= 60 / 180) & (lags <= 60 / 70)
    bpm, beats = None, []
    if band.any() and ac[band].max() > 0:
        period = float(lags[band][np.argmax(ac[band])])
        bpm = round(60 / period, 1)
        # วางกริดจังหวะให้ตรงกับ onset ที่แรงที่สุดในช่วงแรก
        phase = float(np.argmax(o[: int(period / 0.02) + 1]) * 0.02)
        beats = [round(phase + i * period, 3) for i in range(int((dur - phase) / period) + 1)]
    loud = rms > -45
    end = float(np.nonzero(loud)[0][-1] * 0.02 + 0.02) if loud.any() else 0.0
    quiet = []                                                     # ช่วงเงียบ ≥ 0.4 วิ (ไม่นับหางหลังเพลงจบ)
    i = 0
    while i < n:
        if not loud[i] and i * 0.02 < end:
            j = i
            while j < n and not loud[j]:
                j += 1
            if (j - i) * 0.02 >= 0.4:
                quiet.append([round(i * 0.02, 2), round(min(j * 0.02, end), 2)])
            i = j
        else:
            i += 1
    q = int(0.25 / 0.02)
    curve = [float(np.max(rms[a:a + q])) for a in range(0, n, q)]
    return {"file": str(f), "offset": offset, "duration": round(dur, 2), "end": round(end, 2), "bpm": bpm,
            "beats": beats, "hits": hits, "quiet": quiet, "curve_0.25s": [round(c, 1) for c in curve]}


def report(a: dict) -> list[str]:
    warn = []
    silent = sum(b - a_ for a_, b in a["quiet"]) + max(0.0, a["duration"] - a["end"])
    if a["end"] < a["duration"] - 1.0:
        warn.append(f"เพลงจบจริงที่ {a['end']:.1f} วิ (ไฟล์ยาว {a['duration']:.1f}) — หางเงียบ {a['duration'] - a['end']:.1f} วิ: "
                    "คลิปยาวกว่านี้ = สร้างใหม่ยาวขึ้น 3–4 วิ หรือจบภาพก่อนเพลงหมด")
    if silent > 0.25 * a["duration"]:
        warn.append(f"เงียบรวม {silent:.1f} วิ ({silent / a['duration']:.0%}) — ไม่ใช่เพลงปูพื้น (มักได้เสียงกระแทกห่างๆ): "
                    "สร้างใหม่ด้วย composition plan (references/product-ad.md §เพลง) หรือเปลี่ยน prompt ให้มีกลอง/เบสต่อเนื่อง")
    if not a["bpm"]:
        warn.append("หาจังหวะไม่เจอ — เพลงไม่มีกลองชัด ตัดภาพตาม hits แทน")
    return warn


def main() -> None:
    a = sys.argv[1:]
    if not a or a[0].startswith("--"):
        sys.exit(__doc__)
    off = float(a[a.index("--offset") + 1]) if "--offset" in a else 0.0
    res = analyse(Path(a[0]), off)
    out = Path.cwd() / "audio" / "beats.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    bars = " ▁▂▃▄▅▆▇█"
    line = "".join(bars[max(0, min(8, int((c + 48) / 6)))] for c in res["curve_0.25s"])
    print(f"{a[0]} · {res['duration']} วิ · จบจริง {res['end']} วิ · BPM ≈ {res['bpm']}" + (f" · ตัดหัว {off} วิ" if off else ""))
    for s in range(0, len(line), 40):
        print(f"  {s * 0.25:5.1f}s |{line[s:s + 40]}|")
    print("  จุดกระแทก:", ", ".join(f"{h:g}" for h in res["hits"][:24]) or "-")
    if res["quiet"]:
        print("  ช่วงเงียบ:", ", ".join(f"{q[0]:g}–{q[1]:g}" for q in res["quiet"]))
    for w in report(res):
        print("WARN", w)
    print(f"→ {out.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
