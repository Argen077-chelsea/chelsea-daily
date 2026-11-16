#!/usr/bin/env python3
"""vo-timing-sync: estimate when each scene of a script starts inside a voice-over, with no speech-to-text.

    python3 sync_vo.py AUDIO SCRIPT.json [--out result.json] [--noise -32] [--min-silence 0.12]
                       [--min-gap 0.5] [--snap 1.3] [--snap-min 0.2]

SCRIPT.json:
  {"paragraphs": [ {"scenes": [ {"key": "intro", "text": "..."}, {"key": "body", "text": "..."} ]},
                   {"scenes": [ ... ], "start": 21.5, "end": 51.4}   # start/end optional = manual anchors
                 ]}
A "paragraph" is a block the narrator separates from the next by a clear pause (a section of the script).
Needs ffmpeg + ffprobe on PATH. Python standard library only.
"""
import argparse, json, re, subprocess, sys, unicodedata


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def duration(audio):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio]).stdout.strip()
    return float(out)


def silences(audio, noise, min_silence):
    err = run(["ffmpeg", "-hide_banner", "-i", audio, "-af", f"silencedetect=noise={noise}dB:d={min_silence}",
               "-f", "null", "-"]).stderr
    res, start = [], None
    for line in err.splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            start = float(m.group(1))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            res.append((start, float(m.group(1))))
            start = None
    if start is not None:                      # silence runs to the end of the file
        res.append((start, None))
    return res


def weight(text):
    """Letters + digits (Thai consonants and vowels count, tone marks and spaces do not): a stand-in for syllables."""
    return sum(1 for c in text if unicodedata.category(c)[0] in "LN") or 1


def pick_gaps(gaps, expected):
    """Choose one gap per expected boundary, in time order, close to the expected time and preferably long (DP)."""
    n, m = len(expected), len(gaps)
    if m < n:
        return None
    INF = float("inf")

    def local(k, j):
        return abs(gaps[j]["mid"] - expected[k]) - 2 * gaps[j]["dur"]

    cost = [[INF] * m for _ in range(n)]
    back = [[-1] * m for _ in range(n)]
    for j in range(m):
        cost[0][j] = local(0, j)
    for k in range(1, n):
        for j in range(m):
            for i in range(j):
                c = cost[k - 1][i] + local(k, j)
                if c < cost[k][j]:
                    cost[k][j], back[k][j] = c, i
    j = min(range(m), key=lambda x: cost[n - 1][x])
    if cost[n - 1][j] == INF:
        return None
    path = [j]
    for k in range(n - 1, 0, -1):
        j = back[k][j]
        path.append(j)
    return [gaps[i] for i in reversed(path)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio"); ap.add_argument("script")
    ap.add_argument("--out"); ap.add_argument("--noise", type=float, default=-32)
    ap.add_argument("--min-silence", type=float, default=0.12)
    ap.add_argument("--min-gap", type=float, default=0.5, help="shortest pause treated as a paragraph break")
    ap.add_argument("--snap", type=float, default=1.3, help="max distance (s) to move a scene start onto a pause")
    ap.add_argument("--snap-min", type=float, default=0.2, help="shortest pause a scene start may snap to")
    a = ap.parse_args()

    spec = json.load(open(a.script))
    paras = spec["paragraphs"]
    total_dur = duration(a.audio)
    sil = silences(a.audio, a.noise, a.min_silence)
    speech_start = sil[0][1] if sil and sil[0][0] < 0.05 and sil[0][1] else 0.0
    speech_end = sil[-1][0] if sil and sil[-1][1] is None else total_dur
    if sil and sil[-1][1] is not None and total_dur - sil[-1][1] < 0.05:
        speech_end = sil[-1][0]
    inner = [{"start": s, "end": e, "mid": (s + e) / 2, "dur": e - s} for s, e in sil
             if e is not None and s > speech_start + 0.05 and e < speech_end - 0.05]

    pw = [sum(weight(s["text"]) for s in p["scenes"]) for p in paras]
    tot = sum(pw)
    warnings, ambiguous = [], []

    # 1) paragraph anchors
    need = [i for i in range(1, len(paras)) if "start" not in paras[i]]
    exp, acc = {}, 0
    for i, w in enumerate(pw):
        if i > 0:
            exp[i] = speech_start + (speech_end - speech_start) * acc / tot
        acc += w
    cand = [g for g in inner if g["dur"] >= a.min_gap]
    gap = {}                                    # paragraph index (>=1) -> (pause_start, pause_end) before it
    if need:
        chosen = pick_gaps(cand, [exp[i] for i in need])
        if chosen is None:
            sys.exit(f"Found only {len(cand)} pauses >= {a.min_gap}s but need {len(need)} paragraph breaks. "
                     f"Lower --min-gap, or give manual start/end for paragraphs. Pauses seen: "
                     f"{[(round(g['start'],2), round(g['end'],2)) for g in inner]}")
        for i, g in zip(need, chosen):
            gap[i] = (g["start"], g["end"])
            alts = [x for x in cand if x is not g and abs(x["mid"] - g["mid"]) <= 4.0 and x["dur"] >= 0.7 * g["dur"]]
            if alts:
                ambiguous.append({"paragraph": i + 1, "chosen": [round(g["start"], 2), round(g["end"], 2)],
                                  "alternatives": [[round(x["start"], 2), round(x["end"], 2)] for x in alts]})
    for i in range(1, len(paras)):
        if i not in gap:                        # manual anchor
            st = paras[i]["start"]
            hit = [g for g in inner if abs(g["end"] - st) <= 0.35]       # the real pause that ends at this start
            before = min(hit, key=lambda g: abs(g["end"] - st))["start"] if hit else st - 0.5
            gap[i] = (paras[i - 1].get("end", before), st)
    p_start = [round(paras[0].get("start", speech_start) if i == 0 else gap[i][1], 2) for i in range(len(paras))]
    p_end = [round(paras[-1].get("end", speech_end) if i == len(paras) - 1 else gap[i + 1][0], 2) for i in range(len(paras))]

    # 2) scene starts inside each paragraph
    gaps_all = [g for g in inner if g["dur"] >= a.snap_min]
    scenes, devs = {}, []
    for i, p in enumerate(paras):
        s0, e0 = p_start[i], p_end[i]
        ws = [weight(s["text"]) for s in p["scenes"]]
        cum, prev = 0, s0
        for j, sc in enumerate(p["scenes"]):
            if j == 0:
                t = s0
            else:
                est = s0 + (e0 - s0) * cum / sum(ws)
                near = [g for g in gaps_all if abs(g["mid"] - est) <= a.snap and s0 < g["mid"] < e0 and g["mid"] > prev + 0.4]
                t = min(near, key=lambda g: abs(g["mid"] - est))["mid"] if near else est
                devs.append(abs(t - est))
            scenes[sc["key"]] = round(t, 2)
            prev = t
            cum += ws[j]

    # 3) sanity checks: does the recording look like this script?
    for i in range(len(paras)):
        actual = p_end[i] - p_start[i]
        expect = (speech_end - speech_start) * pw[i] / tot
        r = actual / expect if expect else 1
        if r < 0.6 or r > 1.6:
            warnings.append(f"paragraph {i+1}: lasts {actual:.1f}s but its share of the text predicts {expect:.1f}s (x{r:.2f}) — "
                            f"the recording may skip, add or reorder text compared with the script; confirm with the user")
    if len(cand) < len(paras) - 1:
        warnings.append("fewer clear pauses than paragraph breaks")
    for amb in ambiguous:
        warnings.append(f"break before paragraph {amb['paragraph']} is ambiguous: chose {amb['chosen']} but "
                        f"{amb['alternatives']} look just as likely — confirm with the user or set \"start\" for that paragraph")

    result = {"audio_seconds": round(total_dur, 2), "speech": [round(speech_start, 2), round(speech_end, 2)],
              "paragraphs": [{"start": s, "end": e, "seconds": round(e - s, 2), "expected_seconds": round((speech_end - speech_start) * w / tot, 2)} for s, e, w in zip(p_start, p_end, pw)],
              "scenes": scenes, "ambiguous_breaks": ambiguous, "warnings": warnings}
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if a.out:
        open(a.out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
