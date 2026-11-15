#!/usr/bin/env python3
"""director skill — ประกอบทั้งคลิปจาก storyboard.json: การ์ดทุกใบต่อกัน + เสียงพากย์ + เพลง + SFX ตามแผนเสียง

    python3 scripts/assemble.py [--draft] [--only <บีต>] [--out out/final.mp4]

storyboard.json:
  {"vo": "audio/vo.mp3", "music": {"src": "audio/music/bed.mp3", "gain_db": -18, "duck_db": -8},
   "beats": [{"card": "cards/hook.html", "render": "renders/hook.mp4", "at": 0, "duration": 4,
              "sound": {"music": "เบา ปูทาง", "silence": [3.6, 4.0],
                        "sfx": [{"role": "whoosh", "at": 1.2}, {"src": "audio/sfx/x.mp3", "at": 2.5, "volume_db": -10}]}}]}
  - beats ต่อกันไม่มีช่องว่าง (at ของใบถัดไป = at + duration ของใบก่อน) · เวลาทั้งหมดเป็นวินาทีของคลิป
  - role = ชุดเสียงที่ติดมากับ skill (audio/sfx/kit/roles.json) · ความดังตั้งต้นของ role ใช้ได้เลย
  - music.silence ต่อบีต: เพลงเงียบช่วงนั้น (ความเงียบก่อนจุดกระแทกทำให้กระแทกหนักขึ้น)
  - เพลงลดลง duck_db ใต้เสียงพากย์อัตโนมัติ (sidechain) · music.offset = ตัดหัวเพลงกี่วิ (ให้ drop ลงภาพ — ค่าเดียวกับ beats.py --offset)
  - ไม่มีเสียงพากย์ ("vo": "") = โฆษณาเพลงล้วน: เพลงคือเสียงหลัก ตั้ง gain_db −4…−8 (ไม่ใช่ −18)
--draft ใช้ renders/<บีต>-draft.mp4 ถ้ามี (ดูทั้งคลิปเร็วๆ) · ตัวจริงใช้ render ของแต่ละบีต
--only <บีต> = ชิ้นทดสอบพร้อมเสียง (ขั้น 6): บีตเดียว (ลำดับเริ่ม 1 หรือชื่อการ์ด) ตัดเสียงพากย์/เพลง/SFX ให้ตรงช่วงของมัน → out/test.mp4
ขนาดภาพตาม "aspect" ของ storyboard: 9:16 = 1080×1920 · 16:9 = 1920×1080 · 1:1 = 1080×1080
ตัวจริง (ไม่มี --out) ไม่ทับเวอร์ชันเก่า: out/final.mp4 = ล่าสุดเสมอ + สำเนา out/final-vN.mp4
ไฟล์ที่ไม่มี = หยุด พร้อมบอกชื่อ (ไม่ข้ามเงียบๆ) · ความดังสุดท้าย −14 LUFS, peak ≤ −1.5 dBTP (สองรอบ)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PROJ = Path.cwd()
KIT = PROJ / "audio" / "sfx" / "kit"
SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}


def ff(*a: str, quiet: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-hide_banner", *(["-v", "error"] if quiet else []), *a], capture_output=True, text=True)


def sfx_list(sb: dict) -> list[dict]:
    lib = json.loads((KIT / "roles.json").read_text()) if (KIT / "roles.json").exists() else {}
    out = []
    for b in sb["beats"]:
        for s in (b.get("sound") or {}).get("sfx", []):
            if "role" in s:
                r = lib.get(s["role"])
                if not r:
                    sys.exit(f"ไม่มีเสียงหน้าที่ '{s['role']}' ในชุด — มี: {', '.join(sorted(lib))}")
                f = KIT / (s.get("alt") or r["file"])
                out.append({"file": f, "at": float(s["at"]), "db": float(s.get("volume_db", r["volume_db"]))})
            else:
                out.append({"file": PROJ / s["src"], "at": float(s["at"]), "db": float(s.get("volume_db", -10))})
    lost = [str(x["file"]) for x in out if not x["file"].exists()]
    if lost:
        sys.exit("ไฟล์เสียงหาไม่เจอ (จะไม่ข้ามให้เงียบๆ): " + ", ".join(lost[:5]))
    return out


def main() -> None:
    a = sys.argv[1:]
    draft = "--draft" in a
    only = a[a.index("--only") + 1] if "--only" in a else None
    out = PROJ / (a[a.index("--out") + 1] if "--out" in a else
                  ("out/test.mp4" if only else "out/preview.mp4" if draft else "out/final.mp4"))
    sb = json.loads((PROJ / "storyboard.json").read_text())
    beats = sorted(sb["beats"], key=lambda b: float(b["at"]))
    if not beats:
        sys.exit("storyboard.json ยังไม่มี beats")
    W, H = SIZES.get(sb.get("aspect", "9:16"), (1080, 1920))
    t0 = 0.0
    if only:      # one beat, its sound cut to its window, everything shifted to start at 0
        pick = [b for i, b in enumerate(beats, 1) if only == str(i) or only in str(b.get("card", ""))]
        if len(pick) != 1:
            sys.exit(f"--only {only}: เจอ {len(pick)} บีต — ใช้ลำดับ (1, 2, …) หรือชื่อการ์ดที่ไม่ซ้ำ")
        t0 = float(pick[0]["at"])
        beats = [{**pick[0], "at": 0.0}]
    t = 0.0
    vids = []
    for b in beats:
        if abs(float(b["at"]) - t) > 0.05:
            sys.exit(f"บีต {b.get('card')} เริ่มที่ {b['at']} แต่ใบก่อนจบที่ {t:.2f} — ต้องต่อกันพอดี")
        r = PROJ / b["render"]
        d = r.with_name(r.stem + "-draft.mp4")
        v = d if draft and d.exists() and (not r.exists() or d.stat().st_mtime > r.stat().st_mtime) else r   # never an older draft
        if not v.exists() and not b.get("card"):
            sys.exit(f"ยังไม่มี {b['render']} — บีตนี้เป็นวิดีโอสำเร็จ (ช็อต Blender/ฟุตเทจ): ทำไฟล์ก่อน (references/product-ad.md §3)")
        if not v.exists():
            sys.exit(f"ยังไม่ได้ render {v.relative_to(PROJ)} — python3 scripts/render_card.py {b['card']} {b['render']}")
        have = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)],
                                    capture_output=True, text=True).stdout or 0)
        if have < float(b["duration"]) - 0.1:
            sys.exit(f"{v.relative_to(PROJ)} ยาว {have:.2f} วิ แต่บีตนี้ {b['duration']} วิ — render ใหม่ทั้งการ์ด (ไฟล์อาจเป็นช่วงสั้น/ของเก่า)")
        vids.append((v, float(b["duration"])))
        t += float(b["duration"])
    total = t
    fx = [x for x in sfx_list(sb) if t0 - 0.01 <= x["at"] < t0 + total]
    for x in fx:
        x["at"] -= t0

    ins, chains = [], []
    for i, (v, dur) in enumerate(vids):
        ins += ["-i", str(v)]
        chains.append(f"[{i}:v]trim=duration={dur},setpts=PTS-STARTPTS,fps=30,scale={W}:{H},setsar=1[v{i}]")
    vcat = "".join(f"[v{i}]" for i in range(len(vids))) + f"concat=n={len(vids)}:v=1:a=0[v]"
    n = len(vids)
    amix = []
    vo = PROJ / sb["vo"] if sb.get("vo") else None
    if vo:
        if not vo.exists():
            sys.exit(f"ไม่เจอเสียงพากย์ {sb['vo']}")
        ins += ["-ss", f"{t0:.3f}", "-i", str(vo)]
        chains.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[vo][key]")
        amix.append("[vo]")
        n += 1
    m = sb.get("music") or {}
    if m.get("src"):
        mf = PROJ / m["src"]
        if not mf.exists():
            sys.exit(f"ไม่เจอเพลง {m['src']}")
        ins += ["-stream_loop", "-1", "-ss", f"{t0 + float(m.get('offset', 0)):.3f}", "-i", str(mf)]   # offset = ตัดหัวเพลง (beats.py --offset)
        quiet = [[x - t0 for x in s] for b in beats for s in [(b.get("sound") or {}).get("silence")] if s]
        if only:            # silences are clip times — in a test piece keep the ones inside this beat
            quiet = [q for q in quiet if q[1] > 0 and q[0] < total]
        mute = "".join(f",volume=enable='between(t,{x[0]},{x[1]})':volume=0" for x in quiet)
        chains.append(f"[{n}:a]atrim=duration={total},aresample=48000,aformat=channel_layouts=stereo,volume={m.get('gain_db', -18)}dB{mute}[bed0]")
        if vo:
            duck = 10 ** (float(m.get("duck_db", -8)) / -20)
            chains.append(f"[bed0][key]sidechaincompress=threshold=0.03:ratio={max(2.0, duck * 2):.1f}:attack=20:release=300[bed]")
        else:
            chains.append("[bed0]anull[bed]")
        amix.append("[bed]")
        n += 1
    elif vo:
        chains.append("[key]anullsink")
    for k, s in enumerate(fx):
        ins += ["-i", str(s["file"])]
        ms = int(round(s["at"] * 1000))
        chains.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,volume={s['db']}dB,adelay={ms}|{ms}[s{k}]")
        amix.append(f"[s{k}]")
        n += 1
    if amix:
        chains.append("".join(amix) + f"amix=inputs={len(amix)}:normalize=0:duration=longest,atrim=duration={total}[mix]")
    else:
        chains.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={total}[mix]")
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_suffix(".raw.mp4")
    res = ff(*ins, "-filter_complex", ";".join(chains + [vcat]), "-map", "[v]", "-map", "[mix]",
             "-c:v", "libx264", "-crf", "23" if draft else "17", "-preset", "veryfast" if draft else "medium",
             "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-t", f"{total}", "-y", str(raw.with_suffix(".mov")))
    if res.returncode != 0:
        sys.exit(f"ประกอบไม่สำเร็จ\n{res.stderr[-1500:]}")
    raw = raw.with_suffix(".mov")
    # two-pass loudness: measure, then apply linear normalisation to −14 LUFS / −1.5 dBTP
    meas = ff("-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-", quiet=False).stderr
    j = json.loads(re.findall(r"\{[^{}]*\}", meas)[-1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
          f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample=192000,alimiter=limit=0.71:level=false:attack=1:release=60,aresample=48000")   # เพลงล้วนหัวแหลม: loudnorm อย่างเดียวหลุด −1 dB · limiter ที่ 4× ให้จับ true peak
    res = ff("-i", str(raw), "-c:v", "copy", "-af", ln, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-y", str(out))
    if res.returncode != 0:
        sys.exit(f"ปรับความดังไม่สำเร็จ\n{res.stderr[-800:]}")
    raw.unlink(missing_ok=True)
    if out.name == "final.mp4" and "--out" not in a:     # keep every final: final-v1, v2 … (final.mp4 = the latest)
        n = 1
        while (out.parent / f"final-v{n}.mp4").exists():
            n += 1
        (out.parent / f"final-v{n}.mp4").write_bytes(out.read_bytes())
    got = ff("-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-", quiet=False).stderr
    i_ = re.findall(r"I:\s+(-?[\d.]+) LUFS", got)[-1]
    pk = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", got)[-1]
    print(f"{out}  ({total:.1f} วิ · {len(vids)} บีต · {len(fx)} เสียงประกอบ · {i_} LUFS · peak {pk} dBFS)")


if __name__ == "__main__":
    main()
