#!/usr/bin/env python3
"""director skill — render การ์ด HTML หนึ่งใบเป็น MP4 (รันในโฟลเดอร์งาน)

    python3 scripts/render_card.py cards/<บีต>.html renders/<บีต>.mp4 [--draft] [--from S] [--to S] [--blur N] [--check]

ก่อน render ตรวจหน้าเสมอ (scripts/card_check.mjs): error ในหน้า = หยุด (timeline พังจะได้การ์ดว่างเปล่าแบบเงียบๆ) ·
ฟอนต์โหลดไม่ขึ้น · สระ/วรรณยุกต์ไทยโดนตัด · ข้อความบนจอเกิน 8 คำ · ข้อความหลุดขอบ = คำเตือน (แก้ก่อน render ตัวจริง)

  --draft      ร่าง: 15 fps · ไม่มี motion blur · Chrome ตัวเดียว — ใช้ระหว่างแก้
  --from/--to  render เฉพาะช่วงนั้นของการ์ด (วินาทีของการ์ด) — แก้ท่า 3 วิ ไม่ต้อง render ทั้ง 15 วิ
  --blur N     motion blur: render N เฟรมต่อเฟรม แล้วเฉลี่ยครึ่งหนึ่ง (ช้าขึ้น N เท่า — ใช้ตอนตัวจริง, 4–6 กำลังดี)
  --check      ตรวจหน้าอย่างเดียว ไม่ render (ไม่กี่วินาที)

การ์ดใช้คำพูดเป็นเวลาได้: ใส่ data-at="<วินาทีที่การ์ดเริ่มในคลิป>" ที่ root แล้วเรียก at("คำ") ในสคริปต์ —
คืนวินาทีของการ์ดที่คำนั้นถูกพูด (จาก audio/words.json ของ scripts/words.py) · คำที่ไม่มีในเสียง = error ไม่เดา
ไม่มีเสียงพากย์ (โฆษณาเพลงล้วน): hit(n) / beat(n) = จุดกระแทก/จังหวะที่ n ของเพลงในการ์ด (จาก audio/beats.json ของ scripts/beats.py)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJ = Path.cwd()
HF = PROJ / "node_modules" / ".bin" / "hyperframes"


def arm_chrome() -> None:
    """Mac ชิป M: ใช้ Chrome รุ่น arm64 ถ้ามี (รุ่น x64 วิ่งผ่าน Rosetta ช้ากว่า ~2 เท่า)."""
    if os.environ.get("HYPERFRAMES_BROWSER_PATH"):
        return
    if subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True).stdout.strip() != "1":
        return
    hits = sorted((Path.home() / ".cache" / "hyperframes" / "chrome" / "chrome-headless-shell").glob(
        "mac_arm-*/chrome-headless-shell-mac-arm64/chrome-headless-shell"), reverse=True)
    if hits:
        os.environ["HYPERFRAMES_BROWSER_PATH"] = os.environ["PRODUCER_HEADLESS_SHELL_PATH"] = str(hits[0])


def native(cmd: list) -> list:
    arm = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True).stdout.strip() == "1"
    return ["arch", "-arm64", *cmd] if arm else cmd


def storyboard_at(src: Path) -> float | None:
    """The card's start in the clip from storyboard.json — the one place it is decided."""
    sb = PROJ / "storyboard.json"
    if not sb.exists():
        return None
    rel = str(src.relative_to(PROJ)) if src.is_relative_to(PROJ) else src.name
    hit = [b for b in json.loads(sb.read_text()).get("beats", []) if b.get("card") == rel]
    return float(hit[0]["at"]) if len(hit) == 1 else None


def words_for(html: str, sb_at: float | None = None) -> str:
    """window.__words in card time + at(): the words said while the card is on screen. The card's start comes from
    storyboard.json when the card is a beat there (data-at in the card is only a fallback — two places drift apart)."""
    m = re.search(r'data-at="([\d.]+)"', html)
    a = float(m.group(1)) if m else None
    if sb_at is not None:
        if a is not None and abs(a - sb_at) > 0.01:
            print(f"WARN data-at={a:g} ในการ์ด ≠ at={sb_at:g} ใน storyboard.json — ใช้ค่าใน storyboard", file=sys.stderr)
        a = sb_at
    wj = PROJ / "audio" / "words.json"
    words = []
    if a is not None and wj.exists():
        words = [{"w": w["text"], "t": round(w["start"] - a, 3)} for w in json.loads(wj.read_text()) if w["start"] >= a - 0.05]
    # no voice-over: the music's hits/beats (scripts/beats.py → audio/beats.json) in card time — hit(n), beat(n)
    bj = PROJ / "audio" / "beats.json"
    mus = ""
    if a is not None and bj.exists():
        b = json.loads(bj.read_text())
        hits = [round(h - a, 3) for h in b.get("hits", []) if h >= a - 0.05]
        beats = [round(h - a, 3) for h in b.get("beats", []) if h >= a - 0.05]
        mus = ("window.__hits = " + json.dumps(hits) + "; window.__beats = " + json.dumps(beats) + ";\n"
               "function hit(n = 0) { const v = window.__hits[n]; if (v === undefined) throw new Error(`hit(${n}): เพลงไม่มีจุดกระแทกที่ ${n} ในการ์ดนี้ — ดู audio/beats.json`); return v; }\n"
               "function beat(n = 0) { const v = window.__beats[n]; if (v === undefined) throw new Error(`beat(${n}): ไม่มีจังหวะที่ ${n} ในการ์ดนี้`); return v; }\n")
    # Scribe gives Thai as words OR one character per token: search the joined text, not token by token
    return ("<script>" + mus + "window.__words = " + json.dumps(words, ensure_ascii=False) + ";\n"
            "function at(w, after = 0) { const forms = (Array.isArray(w) ? w : [w]).map((f) => f.replace(/\\s+/g, ''));\n"
            "  let text = '', idx = []; for (const x of window.__words) { const s = x.w.replace(/\\s+/g, ''); for (const c of s) { text += c; idx.push(x.t); } }\n"
            "  const from = idx.findIndex((t) => t >= after - 1e-3); let best = -1;\n"
            "  if (from >= 0) for (const f of forms) { const i = text.indexOf(f, from); if (i >= 0 && (best < 0 || i < best)) best = i; }\n"
            "  if (best < 0) throw new Error(`at(): \"${forms.join('|')}\" ไม่มีในเสียงพากย์หลัง ${after} วิ — ดู audio/words.json`);\n"
            "  return idx[best]; }</script>")


def ranged(html: str, a: float, b: float | None) -> str:
    """render เฉพาะ a–b: root ยาว b−a และ timeline ที่การ์ดลงทะเบียนถูกแทนด้วยตัวที่ไล่จาก a ไป b (เฟรมแรก = ท่าที่ a)."""
    m = re.search(r"<[^>]*data-composition-id[^>]*>", html)
    dur = float(re.search(r'data-duration="([\d.]+)"', m.group(0)).group(1))
    b = dur if b is None else b
    if b <= a:
        sys.exit("--from ต้องน้อยกว่า --to")
    html = html.replace(m.group(0), re.sub(r'data-duration="[\d.]+"', f'data-duration="{b - a:g}"', m.group(0)), 1)
    trap = ("<script>(function () { const A = %s, B = %s;\n"
            "  const wrap = (tl) => { if (!tl || tl.__ranged || !tl.tweenFromTo) return tl; tl.pause();\n"
            "    const w = gsap.timeline({ paused: true }); let built = false;\n"
            "    const build = () => { if (built) return; built = true; tl.seek(A, false); w.add(tl.tweenFromTo(A, B, { ease: 'none', immediateRender: true }), 0); };\n"
            "    for (const k of ['seek', 'time', 'totalTime', 'progress', 'totalProgress', 'render']) { const f = w[k].bind(w); w[k] = (...x) => { build(); return f(...x); }; }\n"
            "    w.duration = (...x) => x.length ? w : B - A; w.totalDuration = (...x) => x.length ? w : B - A; w.__ranged = true; return w; };\n"
            "  const mk = () => new Proxy({}, { set(o, k, v) { o[k] = wrap(v); return true; } }); let store = mk();\n"
            "  Object.defineProperty(window, '__timelines', { configurable: true, get() { return store; },\n"
            "    set(v) { const p = mk(); for (const k in (v || {})) p[k] = v[k]; store = p; } }); })();</script>") % (a, b)
    return html.replace("<head>", "<head>\n" + trap, 1)


def check(chrome: str) -> dict:
    res = subprocess.run(native(["node", str(PROJ / "scripts" / "card_check.mjs"), str(PROJ / "index.html"), chrome]),
                         capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"ตรวจหน้าการ์ดไม่สำเร็จ\n{res.stderr[-1500:]}")
    got = json.loads(res.stdout)
    if got["errors"]:            # first: a thrown error is the cause, "no timeline" only its result
        sys.exit("การ์ดมี error ในหน้า (render ไปจะได้การ์ดว่าง):\n  " + "\n  ".join(got["errors"]))
    if got.get("fatal"):
        sys.exit(f"การ์ดผิดรูปแบบ: {got['fatal']}")
    for f in got["fonts"]:
        if f.endswith("(ไม่มีตัวไทย)"):
            print(f"WARN ฟอนต์ '{f[:-14].strip()}' ไม่มีตัวไทย — ข้อความไทยในฟอนต์นี้จะออกเป็นฟอนต์ระบบ (ใช้ฟอนต์ไทย หรือใช้ตัวนี้กับอังกฤษ/ตัวเลขเท่านั้น)", file=sys.stderr)
        else:
            print(f"WARN ฟอนต์ '{f}' โหลดไม่ขึ้น — จะได้ฟอนต์สำรองแทน (ดู @font-face / Google Fonts link)", file=sys.stderr)
    for c in got["clip"]:
        print(f"WARN ตัวไทยโดนตัดที่ {c['t']} วิ: '{c['text']}' — กล่องที่ overflow:hidden ต่ำไป (เพิ่ม line-height ≥ 1.4 / padding บน-ล่าง)", file=sys.stderr)
    for d in got["dense"]:
        print(f"WARN {d['n']} คำบนจอที่ {d['t']} วิ — โชว์คีย์เวิร์ด (≤ 8 คำ — ตัวตัดคำไทยนับละเอียด เกณฑ์ 10 หน่วย) ให้เสียงพูดที่เหลือ", file=sys.stderr)
    for q in got.get("pops", []):
        print(f"WARN '{q['text']}' โผล่ตั้งแต่เฟรมแรก หายที่ {q['t']} วิ แล้วค่อยเข้าที่ {q['back']} วิ — ซ่อนตั้งแต่สร้าง: gsap.set(el, {{opacity: 0}}) "
              "(fromTo ที่ immediateRender:false โชว์ท่าจบที่เฟรม 0)", file=sys.stderr)
    for o in got["out"]:
        print(f"WARN ข้อความหลุดขอบที่ {o['t']} วิ: '{o['text']}'", file=sys.stderr)
    return got


def main() -> None:
    a = sys.argv[1:]
    opt = {}
    for k in ("--from", "--to", "--blur"):
        if k in a:
            i = a.index(k); opt[k] = a[i + 1]; del a[i:i + 2]
    draft, only_check = "--draft" in a, "--check" in a
    a = [x for x in a if x not in ("--draft", "--check")]
    if len(a) != 2 or not HF.exists():
        sys.exit(__doc__ if len(a) != 2 else "ไม่เจอ Hyperframes — รันในโฟลเดอร์งาน แล้ว npm i")
    src, out = Path(a[0]).resolve(), Path(a[1]).resolve()
    if ("--from" in opt or "--to" in opt) and "-part" not in out.stem:   # a stretch never replaces the card's draft/final
        out = out.with_name(f"{out.stem}-part-{opt.get('--from', '0')}-{opt.get('--to', 'end')}{out.suffix}")
    arm_chrome()
    html = src.read_text()
    # ไฟล์สื่อที่การ์ดใช้ต้องมีจริง — ไม่งั้นได้การ์ดดำเงียบๆ (เคยเกิด: render การ์ดก่อนช็อต Blender เสร็จ)
    # path นับจากโฟลเดอร์งาน (index.html อยู่ที่นั่น) ไม่ใช่จาก cards/
    lost = [m for m in re.findall(r'<(?:video|img|audio|source)\b[^>]*?\bsrc="([^"]+)"', re.sub(r"<!--.*?-->", "", html, flags=re.S))
            if not re.match(r"(https?:|data:|blob:)", m) and not (PROJ / m).exists()]
    if lost:
        sys.exit("ไฟล์ที่การ์ดใช้หาไม่เจอ (นับจากโฟลเดอร์งาน ไม่ใช่ cards/): " + ", ".join(lost)
                 + "\n  ยังไม่ได้ทำ (เช่นช็อต Blender ยัง render ไม่เสร็จ) หรือ path ผิด")
    html = html.replace("</head>", words_for(html, storyboard_at(src)) + "\n</head>", 1)
    rng = "--from" in opt or "--to" in opt
    if rng:
        html = ranged(html, float(opt.get("--from", 0)), float(opt["--to"]) if "--to" in opt else None)
    (PROJ / "index.html").write_text(html)            # Hyperframes renders the project's index.html (scratch)
    chrome = subprocess.run(native([str(HF), "browser", "path"]), capture_output=True, text=True).stdout.strip().splitlines()[-1]
    got = check(chrome)
    if only_check:
        print(f"{src.name}: หน้าใช้ได้")
        return
    blur = 1 if draft else int(opt.get("--blur", 1))
    fps = 15 if draft else 30
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".hi.mp4") if blur > 1 else out
    cmd = [str(HF), "render", "--output", str(tmp), "--fps", str(fps * blur)]
    if draft:
        cmd += ["--quality", "draft"]
    if draft or rng:
        cmd += ["--workers", "1"]          # few frames: one Chrome (each extra one reloads the whole page)
    res = subprocess.run(native(cmd), capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"render ไม่สำเร็จ\n{res.stdout[-1500:]}\n{res.stderr[-1500:]}")
    if blur > 1:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-vf", f"tmix=frames={max(2, blur // 2)},fps={fps}",
                        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-an", str(out)], check=True)
        tmp.unlink(missing_ok=True)
    if got.get("cues") and not (draft or rng):
        out.with_suffix(".cues.json").write_text(json.dumps(got["cues"]))
    print(out)


if __name__ == "__main__":
    main()
