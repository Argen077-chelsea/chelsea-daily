#!/usr/bin/env python3
"""director skill — หาและโหลดของฟรี พร้อมจดไลเซนส์: เสียง (Freesound), รูป (Pixabay, Unsplash), วิดีโอ (Pixabay)

    python3 scripts/assets.py sfx   "<คำค้น อังกฤษ>" audio/sfx  [--n 6] [--max 3] [--any]   CC0 อย่างเดียว · --any = CC0 + CC BY (ไม่มี NC เด็ดขาด)
    python3 scripts/assets.py photo "<คำค้น>" assets/img [--n 6] [--portrait]
    python3 scripts/assets.py video "<คำค้น>" assets/img [--n 4]
    python3 scripts/assets.py sfx --gen "<คำบรรยายเสียง อังกฤษ>" audio/sfx [--s 1.2]   (ElevenLabs sound effects — สร้างเอง)
    python3 scripts/assets.py music "<prompt อังกฤษ: แนว อารมณ์ จังหวะ จุด drop>" audio/music --s 17    (ElevenLabs Music)
    python3 scripts/assets.py music audio/music/plan.json audio/music     (composition plan: ท่อน + ความยาวแต่ละท่อน — references/product-ad.md §เพลง)
    python3 scripts/assets.py music --free "<แนว อังกฤษ เช่น lofi chill, upbeat electronic>" audio/music [--n 4]
        (ฟรี: เพลง/ลูป CC0 จาก Freesound 20 วิ–4 นาที ใช้เชิงพาณิชย์ได้ ไม่ต้องใส่เครดิต · ต้องมี FREESOUND_API_KEY ฟรี)

คีย์จาก .env ของโฟลเดอร์งาน (ไม่พิมพ์ค่า) · ไม่มีคีย์ = ข้ามแหล่งนั้น · ทุกไฟล์ถูกจดใน <โฟลเดอร์>/CREDITS.md:
ไฟล์ · หน้าต้นทาง · คนทำ · ไลเซนส์เต็ม (CC0 1.0 / CC BY 4.0 — ไม่ใช่แค่เลขเวอร์ชัน) · Unsplash ต้องใส่ชื่อช่างภาพในเครดิต
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote_plus

UA = {"User-Agent": "director-skill/1.0"}


def keys() -> dict[str, str]:
    env = Path.cwd() / ".env"
    out = {}
    for line in (env.read_text().splitlines() if env.exists() else []):
        m = re.match(r"^([A-Z_]+)=(.+)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"')
    return out


def get(url: str, headers: dict | None = None) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=40).read()


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "asset"


def credit(out: Path, rows: list[tuple[str, str, str, str]]) -> None:
    f = out / "CREDITS.md"
    head = "" if f.exists() else "| file | source | author | licence |\n|---|---|---|---|\n"
    with f.open("a") as fh:
        fh.write(head + "".join(f"| {a} | {b} | {c} | {d} |\n" for a, b, c, d in rows))


def licence(url: str) -> str:
    """'https://creativecommons.org/licenses/by-nc/4.0/' → 'CC BY-NC 4.0' (the type, not only the version)."""
    m = re.search(r"(publicdomain/zero|licenses/([a-z-]+))/([\d.]+)", url)
    if not m:
        return url
    return f"CC0 {m.group(3)}" if m.group(1) == "publicdomain/zero" else f"CC {m.group(2).upper()} {m.group(3)}"


def sfx(q: str, out: Path, n: int, k: dict, any_licence: bool, max_s: float) -> list:
    if not k.get("FREESOUND_API_KEY"):
        print("freesound: ไม่มี FREESOUND_API_KEY ใน .env — ข้าม"); return []
    # never NonCommercial: our clips sell things (promo v5 shipped a BY-NC till sound because only "4.0" was recorded)
    filt = quote_plus(f'duration:[0 TO {max_s}]' + (' license:("Attribution" OR "Creative Commons 0")' if any_licence
                                                   else ' license:"Creative Commons 0"'))
    r = json.loads(get(f"https://freesound.org/apiv2/search/text/?query={quote_plus(q)}&filter={filt}"
                       f"&fields=id,name,username,license,duration,previews,url&page_size={n}&sort=score&token={k['FREESOUND_API_KEY']}"))
    rows = []
    for s in r.get("results", [])[:n]:
        name = f"fs-{slug(q)}-{s['id']}.mp3"
        (out / name).write_bytes(get(s["previews"]["preview-hq-mp3"]))
        rows.append((name, s["url"], s["username"], licence(s["license"])))
        print(f"  {name}  {s['duration']:.1f}s  {s['name'][:50]}")
    return rows


def photo(q: str, out: Path, n: int, k: dict, portrait: bool) -> list:
    rows = []
    if k.get("PIXABAY_API_KEY"):
        r = json.loads(get(f"https://pixabay.com/api/?key={k['PIXABAY_API_KEY']}&q={quote_plus(q)}&image_type=photo"
                           f"&orientation={'vertical' if portrait else 'all'}&per_page={max(3, n)}&safesearch=true"))
        for h in r.get("hits", [])[:n]:
            name = f"px-{slug(q)}-{h['id']}.jpg"; (out / name).write_bytes(get(h["largeImageURL"]))
            rows.append((name, h["pageURL"], h.get("user", ""), "Pixabay Content License")); print(f"  {name}")
    else:
        print("pixabay: ไม่มี PIXABAY_API_KEY ใน .env — ข้าม")
    if k.get("UNSPLASH_ACCESS_KEY"):
        hdr = {"Authorization": f"Client-ID {k['UNSPLASH_ACCESS_KEY']}"}
        r = json.loads(get(f"https://api.unsplash.com/search/photos?query={quote_plus(q)}&per_page={n}"
                           + ("&orientation=portrait" if portrait else ""), hdr))
        for h in r.get("results", [])[:n]:
            name = f"us-{slug(q)}-{h['id']}.jpg"; (out / name).write_bytes(get(h["urls"]["full"]))
            get(h["links"]["download_location"], hdr)              # Unsplash API rule: report the download
            rows.append((name, h["links"]["html"], h["user"]["name"], "Unsplash License — credit the photographer")); print(f"  {name}")
    else:
        print("unsplash: ไม่มี UNSPLASH_ACCESS_KEY ใน .env — ข้าม")
    return rows


def video(q: str, out: Path, n: int, k: dict) -> list:
    if not k.get("PIXABAY_API_KEY"):
        print("pixabay: ไม่มี PIXABAY_API_KEY ใน .env — ข้าม"); return []
    # Pixabay ค้นด้วยแท็ก: คำค้นยาว (5 คำ) มักได้ของไม่เกี่ยว (เคยได้เมล็ดกาแฟจาก "boxing close up face dark gym")
    # → เก็บเฉพาะคลิปที่แท็กมีคำค้นคำแรก · ไม่พอ → ตัดคำท้ายทิ้งทีละคำแล้วค้นใหม่
    words, hits, seen = q.split(), [], set()
    head = words[0].lower() if words else ""
    for m in range(len(words), 0, -1):
        qq = " ".join(words[:m])
        r = json.loads(get(f"https://pixabay.com/api/videos/?key={k['PIXABAY_API_KEY']}&q={quote_plus(qq)}&per_page={max(10, n * 3)}&safesearch=true"))
        for h in r.get("hits", []):
            if h["id"] not in seen and head[:5] in (h.get("tags", "").lower()):
                seen.add(h["id"]); hits.append(h)
        if len(hits) >= n:
            break
    if not hits:
        print(f"pixabay: ไม่เจอวิดีโอที่แท็กมี '{head}' — ลองคำค้น 1–2 คำ (เช่น 'boxer', 'boxing gloves')")
    rows = []
    for h in hits[:n]:
        v = h["videos"].get("large") or h["videos"]["medium"]
        if not v.get("url"):
            continue
        name = f"pxv-{slug(q)}-{h['id']}.mp4"; (out / name).write_bytes(get(v["url"]))
        rows.append((name, h["pageURL"], h.get("user", ""), "Pixabay Content License"))
        print(f"  {name}  {h['duration']}s · {v.get('width')}×{v.get('height')} · แท็ก: {h.get('tags', '')[:60]}")
    return rows


def gen_sfx(prompt: str, out: Path, k: dict, secs: float) -> list:
    """ElevenLabs sound effects, one request at a time; on 429 (too many at once / rate limit) wait and retry."""
    import time
    if not k.get("ELEVENLABS_API_KEY"):
        print("elevenlabs: ไม่มี ELEVENLABS_API_KEY ใน .env — ข้าม"); return []
    body = json.dumps({"text": prompt, "duration_seconds": secs}).encode()
    name = f"el-{slug(prompt)}.mp3"
    for attempt in range(5):
        try:
            req = urllib.request.Request("https://api.elevenlabs.io/v1/sound-generation", data=body, method="POST",
                                         headers={**UA, "xi-api-key": k["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
            (out / name).write_bytes(urllib.request.urlopen(req, timeout=120).read())
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            time.sleep(4 * (attempt + 1))
    print(f"  {name}  {secs:g}s")
    return [(name, "ElevenLabs sound effects — prompt: " + prompt.replace("|", "/")[:120], "generated",
             "ElevenLabs — ตามเงื่อนไขแพ็กเกจของผู้ใช้ (เช็กว่าแพ็กเกจอนุญาตเชิงพาณิชย์)")]


def free_music(q: str, out: Path, n: int, k: dict) -> list:
    """Free music beds: Freesound CC0, 20 s – 4 min, music-tagged. No paid key needed (Freesound's key is free)."""
    if not k.get("FREESOUND_API_KEY"):
        print("freesound: ไม่มี FREESOUND_API_KEY ใน .env — สมัครฟรีที่ freesound.org/apiv2/apply แล้วใส่ใน .env"); return []
    filt = quote_plus('duration:[20 TO 240] license:"Creative Commons 0" tag:music')
    r = json.loads(get(f"https://freesound.org/apiv2/search/text/?query={quote_plus(q)}&filter={filt}"
                       f"&fields=id,name,username,license,duration,previews,url&page_size={n}&sort=rating_desc&token={k['FREESOUND_API_KEY']}"))
    rows = []
    for m in r.get("results", [])[:n]:
        name = f"fs-music-{slug(q)}-{m['id']}.mp3"
        (out / name).write_bytes(get(m["previews"]["preview-hq-mp3"]))
        rows.append((name, m["url"], m["username"], licence(m["license"])))
        print(f"  {name}  {m['duration']:.0f}s  {m['name'][:50]}")
    if not rows:
        print("  ไม่เจอ — ลองคำค้นกว้างขึ้น (เช่น 'ambient', 'electronic', 'piano') หรือใช้ ElevenLabs music (เสียเงิน)")
    return rows


def music(prompt: str, out: Path, k: dict, secs: float) -> list:
    """ElevenLabs Music → <out>/el-<slug>.mp3 · no brand/artist names in the prompt (refused) · it does not follow section
    timing — find the real drop in the file before cutting."""
    if not k.get("ELEVENLABS_API_KEY"):
        print("elevenlabs: ไม่มี ELEVENLABS_API_KEY ใน .env — ข้าม"); return []
    plan = Path(prompt)
    if plan.suffix == ".json" and plan.exists():     # composition plan: ท่อนละ prompt + ความยาว — ตรงภาพกว่า prompt เดียวมาก
        p = json.loads(plan.read_text())
        p = p.get("composition_plan", p)
        body = json.dumps({"composition_plan": p, "model_id": "music_v1"}).encode()
        name = f"el-{slug(plan.stem)}.mp3"
        prompt = "composition plan " + plan.name + ": " + " / ".join(s.get("section_name", "") for s in p.get("sections", []))
    else:
        body = json.dumps({"prompt": prompt, "music_length_ms": int(secs * 1000)}).encode()
        name = f"el-{slug(prompt)}.mp3"
    req = urllib.request.Request("https://api.elevenlabs.io/v1/music", data=body, method="POST",
                                 headers={**UA, "xi-api-key": k["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
    import time
    for attempt in range(5):                      # 429 = another request still running (TTS, sfx): wait, retry
        try:
            (out / name).write_bytes(urllib.request.urlopen(req, timeout=300).read())
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                sys.exit(f"ElevenLabs music ตอบ {e.code}: {e.read()[:200]!r}")
            time.sleep(6 * (attempt + 1))
            req = urllib.request.Request(req.full_url, data=body, method="POST", headers=dict(req.header_items()))
    print(f"  {name}")
    try:                                          # ตรวจทันที: เพลง AI บางทีได้แค่เสียงกระแทกห่างๆ หรือจบก่อนเวลา
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import beats
        for w in beats.report(beats.analyse(out / name)):
            print("  WARN", w)
    except Exception as e:                       # noqa: BLE001 — การตรวจพังไม่ทำให้ไฟล์เพลงหาย
        print(f"  (ตรวจเพลงไม่ได้: {e} — รัน scripts/beats.py เอง)")
    return [(name, "ElevenLabs Music API — prompt: " + prompt.replace("|", "/")[:120], "generated",
             "ElevenLabs — ตามเงื่อนไขแพ็กเกจของผู้ใช้ (เช็กว่าแพ็กเกจอนุญาตเชิงพาณิชย์)")]


def main() -> None:
    a = sys.argv[1:]
    if len(a) < 3 or a[0] not in ("sfx", "photo", "video", "music"):
        sys.exit(__doc__)
    opt = lambda f, d: a[a.index(f) + 1] if f in a else d  # noqa: E731
    kind, q, out = a[0], a[1], Path(a[2]); out.mkdir(parents=True, exist_ok=True)
    k, n = keys(), int(opt("--n", "6" if kind != "video" else "4"))
    if kind == "sfx" and "--gen" in a:     # assets.py sfx --gen "<prompt>" OUT [--s 1.2]
        g = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and a[i - 1] not in ("--s", "--n", "--max")]
        q, out = g[0], Path(g[1]); out.mkdir(parents=True, exist_ok=True)
    if kind == "music" and "--free" in a:  # assets.py music --free "<query>" OUT
        g = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and a[i - 1] not in ("--n",)]
        q, out = g[0], Path(g[1]); out.mkdir(parents=True, exist_ok=True)
    rows = (free_music(q, out, int(opt("--n", "4")), k) if kind == "music" and "--free" in a else
            music(q, out, k, float(opt("--s", "17"))) if kind == "music" else
            gen_sfx(q, out, k, float(opt("--s", "1.2"))) if kind == "sfx" and "--gen" in a else
            sfx(q, out, n, k, "--any" in a, float(opt("--max", "3"))) if kind == "sfx" else
            photo(q, out, n, k, "--portrait" in a) if kind == "photo" else video(q, out, n, k))
    if rows:
        credit(out, rows)
    print(f"{len(rows)} file(s) → {out}" + (f" · credits in {out / 'CREDITS.md'}" if rows else ""))


if __name__ == "__main__":
    main()
