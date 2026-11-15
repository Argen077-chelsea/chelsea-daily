#!/usr/bin/env python3
"""director skill — ตรวจทั้งคลิปรอบเดียว → ลิสต์แก้ลิสต์เดียว (แล้วค่อย render ตัวจริงครั้งเดียว)

    python3 scripts/review.py [out/preview.mp4] [--fps 15] [--only <บีต>]     (--only = ตรวจชิ้นทดสอบ out/test.mp4 ของ assemble --only)

วัด (ไม่ใช้ความเห็น):
  ความดัง          −14 LUFS ± 2 · peak ≤ −1 dBFS
  เสียงประกอบ      ทุกเสียงในแผน (storyboard.json) ต้อง "เจอ" ในไฟล์ที่เวลาของมัน — จับคู่รูปคลื่น ถ้าไม่เจอ = จมหรือหาย ไปฟัง
  ภาพกระตุก        ทุกเฟรม: ภาพที่เปลี่ยนแรงแต่ไม่ใช่จุดต่อบีต / cuts_ok = ของโผล่ทั้งก้อน กล้องกระโดด เด้ง
  จอว่าง           ช่วงดำ ≥ 0.5 วิ ที่ไม่มีอะไรบนจอเลย
ดู:
  review/sheet-NN.jpg  ทุกเฟรมที่ 15 fps แผ่นละ 4 วิ — อ่านทุกแผ่น เทียบกับ ref ขนาดเต็ม
เขียน review/REVIEW.md: ผลวัด + รายการแผ่นภาพ + "ลิสต์แก้" ให้เติม → แก้ทั้งหมดทีเดียว → render ตัวจริง → รันอีกรอบ (วัดอย่างเดียว)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sheet import sheet  # noqa: E402

PROJ = Path.cwd()
SR = 8000
SPIKE = 0.10       # scene score above this = a visible jump (smooth motion stays under ~0.08)
MATCH = 0.10       # a sound's waveform found in the mix above this


def dur(v: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)],
                                capture_output=True, text=True).stdout)


def pcm(f: Path, start: float = 0.0, length: float | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}"] + (["-t", f"{length:.3f}"] if length else []) + \
          ["-i", str(f), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.float32)


_MIX: dict = {}


def mix_pcm(final: Path) -> np.ndarray:
    """The whole mix decoded once (review used to call ffmpeg ~600 times: 67 s for a 14 s clip)."""
    if final not in _MIX:
        _MIX[final] = pcm(final)
    return _MIX[final]


def heard(final: Path, sfx: Path, at: float) -> float:
    """Normalised cross-correlation of the sound's attack with the mix around its time (0 … 1).
    Only the first 0.25 s after the onset: a snap is a 5 ms hit plus a 3 s room tail — the tail sinks under any mix."""
    x = pcm(sfx)
    x = x[np.argmax(np.abs(x) > 0.05 * (np.abs(x).max() + 1e-9)):] if len(x) else x
    x = x[: int(0.25 * SR)]
    if len(x) < 200:
        return 1.0
    m = mix_pcm(final)
    a0 = int(max(0.0, at - 0.15) * SR)
    y = m[a0: a0 + len(x) + int(0.3 * SR)]
    if len(y) < len(x):
        return 0.0
    L = len(x) + len(y)
    cc = np.fft.irfft(np.fft.rfft(y, L) * np.conj(np.fft.rfft(x, L)), L)[: len(y) - len(x) + 1]
    win = np.sqrt(np.convolve(y ** 2, np.ones(len(x)), "valid"))[: len(cc)]
    return float(np.max(np.abs(cc) / (np.linalg.norm(x) * win + 1e-9)))


def rise(final: Path, at: float) -> float:
    """dB the mix jumps at the sound's time over the 0.4 s just before it (a hit you hear is a jump you can measure)."""
    m = mix_pcm(final)
    a0 = int(max(0.0, at - 0.45) * SR)
    y = m[a0: a0 + int(0.6 * SR)]
    if len(y) < int(0.5 * SR):
        return 0.0
    pre, post = y[: int(0.4 * SR)], y[int(0.43 * SR): int(0.6 * SR)]
    db = lambda v: 20 * np.log10(np.sqrt(np.mean(v ** 2)) + 1e-9)          # noqa: E731
    return float(db(post) - db(pre))


def planned(sb: dict) -> list[tuple[str, Path, float]]:
    kit = PROJ / "audio" / "sfx" / "kit"
    lib = json.loads((kit / "roles.json").read_text()) if (kit / "roles.json").exists() else {}
    out = []
    for b in sb.get("beats", []):
        for s in (b.get("sound") or {}).get("sfx", []):
            if "role" in s and s["role"] in lib:
                out.append((s["role"], kit / (s.get("alt") or lib[s["role"]]["file"]), float(s["at"])))
            elif "src" in s:
                out.append((Path(s["src"]).name, PROJ / s["src"], float(s["at"])))
    return out


def fps_of(video: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0",
                        str(video)], capture_output=True, text=True).stdout.strip() or "30/1"
    a, b = (r.split("/") + ["1"])[:2]
    return float(a) / float(b or 1)


def jumps(video: Path, ok: list[float]) -> list[tuple[float, float]]:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
                          "scale=270:480,select='gte(scene\\,0)',metadata=print:file=-", "-an", "-f", "null", "-"],
                         capture_output=True, text=True).stdout
    ts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", out)]
    sc = [float(x) for x in re.findall(r"scene_score=([\d.]+)", out)]
    bar = SPIKE if fps_of(video) >= 24 else 0.2      # a draft (15 fps): one frame of a fast move is twice as far — judge cuts on the final
    rows: list[tuple[float, float]] = []
    for t, s in zip(ts, sc):
        if s < bar or t < 0.05 or min((abs(t - c) for c in ok), default=9) <= 0.15:
            continue
        if rows and t - rows[-1][0] <= 0.12:
            if s > rows[-1][1]:
                rows[-1] = (t, s)
            continue
        rows.append((t, s))
    return rows


def main() -> None:
    a = sys.argv[1:]
    fps = float(a[a.index("--fps") + 1]) if "--fps" in a else 15.0
    only = a[a.index("--only") + 1] if "--only" in a else None
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--fps", "--only"))]
    video = Path(pos[0]) if pos else PROJ / "out" / ("test.mp4" if only else "preview.mp4")
    if not video.exists():
        sys.exit(f"ไม่เจอ {video} — ประกอบก่อน: python3 scripts/assemble.py --draft")
    sb = json.loads((PROJ / "storyboard.json").read_text()) if (PROJ / "storyboard.json").exists() else {}
    if only:          # a test piece: only that beat, its times shifted to start at 0 (same rule as assemble --only)
        bs = sorted(sb.get("beats", []), key=lambda b: float(b["at"]))
        pick = [b for i, b in enumerate(bs, 1) if only == str(i) or only in str(b.get("card", ""))]
        if len(pick) != 1:
            sys.exit(f"--only {only}: เจอ {len(pick)} บีต")
        t0, d = float(pick[0]["at"]), float(pick[0]["duration"])
        b = json.loads(json.dumps(pick[0]))
        snd = b.get("sound") or {}
        snd["sfx"] = [{**x, "at": float(x["at"]) - t0} for x in snd.get("sfx", []) if t0 - 0.01 <= float(x["at"]) < t0 + d]
        b["sound"], b["at"] = snd, 0.0
        sb = {**sb, "beats": [b], "cuts_ok": [c - t0 for c in sb.get("cuts_ok", []) if t0 <= c < t0 + d]}
    out = PROJ / "review" / ("test" if only else "")     # a test piece keeps its own sheets and fix list
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("sheet-*.jpg"):
        f.unlink()
    total = dur(video)
    rows = []

    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    if "I:" in err:
        lufs = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1]); pk = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)[-1])
        rows.append(("ความดัง", "", "ผ่าน" if -16 <= lufs <= -12 and pk <= -0.5 else "ดู", f"{lufs:.1f} LUFS · peak {pk:.1f} dBFS (เป้า −14)"))
    else:
        rows.append(("ความดัง", "", "ดู", "ไม่มีเสียงในไฟล์"))

    for name, f, at in planned(sb):
        if not f.exists():
            rows.append((f"เสียง {name}", f"{at:g}", "แก้", f"ไม่มีไฟล์ {f}"))
            continue
        m = heard(video, f, at)
        # the same sound "matched" at other times of the clip = how much any busy mix resembles it by chance
        mine = [t_ for n_, f_, t_ in planned(sb) if f_ == f]       # the same file placed again elsewhere is not "chance"
        others = [x for x in np.arange(0.2, max(0.3, total - 0.3), 0.25) if all(abs(x - y) > 0.3 for y in mine)]
        base = float(np.median([heard(video, f, x) for x in others])) if others else 0.0
        up = rise(video, at)
        if m < max(MATCH, 1.4 * base) and up < 6:      # neither its shape nor a clear jump in loudness
            rows.append((f"เสียง {name}", f"{at:g}", "ดู", f"ไม่เจอชัดๆ (รูปคลื่น {m:.2f} เทียบพื้น {base:.2f} · ดังขึ้น {up:+.0f} dB) — จมใต้เพลง/เสียงพูด หรือไม่ได้ใส่ ไปฟัง"))
    n_fx = len(planned(sb))

    bounds = [float(b["at"]) for b in sb.get("beats", [])] + [float(x) for x in sb.get("cuts_ok", [])]
    js = jumps(video, bounds)
    for t, s in js:
        rows.append(("ภาพกระโดด", f"{t:.2f}", "ดู", f"scene score {s:.2f} — ของโผล่ทั้งก้อน/กล้องกระโดด/เด้ง? ตั้งใจ = ใส่ {t:.2f} ใน cuts_ok"))

    bd = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", "blackdetect=d=0.5:pix_th=0.06", "-an", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    for s0, s1 in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", bd):
        mid = (float(s0) + float(s1)) / 2
        st = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{mid:.2f}", "-i", str(video), "-frames:v", "1", "-vf",
                             "signalstats,metadata=print:key=lavfi.signalstats.YMAX:file=-", "-f", "null", "-"],
                            capture_output=True, text=True).stdout
        if float((re.findall(r"YMAX=([\d.]+)", st) or ["0"])[0]) <= 100:     # dark card with type is fine; empty is not
            rows.append(("จอว่าง", f"{float(s0):.1f}–{float(s1):.1f}", "แก้", "ไม่มีอะไรบนจอเลย"))

    # empty = nothing on the frame: under 0.3 % of pixels differ from the frame's own ground (its median) by > 24 levels,
    # for ≥ 0.25 s — a 230 px keyword on a plain black ground is ~2 %, a truly empty ground ~0 % (a luma-spread test
    # flagged every plain-ground clip as empty)
    W_, H_ = 54, 96
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps=12,scale={W_}:{H_},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, H_, W_) if raw else np.zeros((0, H_, W_), np.uint8)
    run0 = None
    for k in range(len(fr) + 1):
        t_ = k / 12
        empty = k < len(fr) and (np.abs(fr[k].astype(int) - int(np.median(fr[k]))) > 10).mean() < 0.003   # thin grey lines on white count
        if empty and run0 is None:
            run0 = t_
        elif not empty and run0 is not None:
            if t_ - run0 >= 0.25 and not any(r[0] == "จอว่าง" and float(r[1].split("–")[0]) <= t_ and float(r[1].split("–")[1]) >= run0 for r in rows):
                rows.append(("จอว่าง", f"{run0:.2f}–{t_:.2f}", "ดู", "ไม่มีอะไรบนจอ — ตั้งใจ (ช่วงหายใจ) หรือของมาช้า/ไปเร็ว?"))
            run0 = None

    sheets, t = [], 0.0
    while t < total - 0.05:
        p = out / f"sheet-{len(sheets) + 1:02d}.jpg"
        sheet(video, t, min(total, t + 4.0), p, fps, 10, 120)
        sheets.append((t, p)); t += 4.0

    md = [f"# review — {sb.get('title', PROJ.name)}", "", f"`{video.relative_to(PROJ) if video.is_relative_to(PROJ) else video}` · {total:.1f} วิ · "
          f"เสียงประกอบในแผน {n_fx} · ภาพกระโดดที่ไม่ใช่จุดต่อ {len(js)}", "", "## วัดได้", "", "| อะไร | วินาที | สถานะ | รายละเอียด |", "|---|---|---|---|"]
    md += [f"| {a_} | {b_} | {c_} | {d_} |" for a_, b_, c_, d_ in rows]
    if len(rows) == 1:
        md.append("| ทุกเสียงในแผน · ภาพทุกเฟรม · จอ | | ผ่าน | |")
    md += ["", "> **'ดู' ที่เสียง** — คนใช้: ฟังวินาทีนั้น · agent (ฟังไม่ได้): เพิ่ม 4–6 dB แล้วรัน review ซ้ำ ถ้ายังไม่เจอ ย้ายเสียงไปช่วงที่เพลง/เสียงพูดเบากว่า"]
    md += ["", f"## ดู (ทุกเฟรมที่ {fps:g} fps — อ่านทุกแผ่น เทียบกับ ref ขนาดเต็ม: จังหวะ ตัวหนังสืออ่านทัน ไทยไม่โดนตัด ของที่ควรขยับไม่นิ่งตาย)", ""]
    md += [f"- {t0:.0f}–{min(total, t0 + 4):.0f} วิ: `{p.relative_to(PROJ)}`" for t0, p in sheets]
    head = "## ลิสต์แก้ (แก้ทั้งหมดทีเดียว แล้ว render ตัวจริงครั้งเดียว)"
    old = (out / "REVIEW.md").read_text() if (out / "REVIEW.md").exists() else ""
    kept = old[old.index(head) + len(head):].strip("\n") if head in old else ""   # a re-run keeps the fix list written so far
    md += ["", head, "", kept or "- [ ] ", ""]
    (out / "REVIEW.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:md.index("## ลิสต์แก้ (แก้ทั้งหมดทีเดียว แล้ว render ตัวจริงครั้งเดียว)")]))


if __name__ == "__main__":
    main()
