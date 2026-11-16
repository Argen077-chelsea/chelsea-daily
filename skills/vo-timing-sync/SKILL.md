---
name: vo-timing-sync
description: Time on-screen visuals, captions or motion-graphic scenes to a voice-over audio file when there is no word-level transcript (no speech-to-text key, offline, or STT blocked). Detects pauses in the recording with ffmpeg, matches them to the script's paragraphs, and estimates each scene's start time from text length snapped to the nearest natural pause. Use this whenever the user hands over a narration/voice-over file (wav/mp3) plus a script split into sections or scenes and wants the visuals, cards, subtitles or cuts to line up with the speech — Thai or any language — even if they never say "timing" or "sync" (e.g. "ผูกภาพกับเสียงพากย์", "ปรับเวลาภาพให้ตรงเสียง", "เสียงพากย์ยาว 40 วิ ภาพต้องเปลี่ยนตอนไหน", "line up the scenes with my voiceover"). Do not use when exact word-by-word timing is required and a transcription service is available — use that instead.
---

# vo-timing-sync

Goal: answer "at what second does scene N begin in this recording?" without transcribing the speech.

It works because a narrator pauses between sections and, less clearly, between sentences. Pauses are measurable; text length predicts how long each part takes. Combine the two and you get start times that are usually within about a second or two of the speech. They are **estimates, not word-level timing**, and you must say so when reporting.

## Inputs you need
1. The audio file (wav/mp3/m4a). Convert to mp3 first if it is large: `ffmpeg -y -i in.wav -c:a libmp3lame -q:a 2 vo.mp3`.
2. The script split into **paragraphs** (a section the narrator separates with a clear pause) and, inside each paragraph, **scenes** (the visual changes you want to time). Each scene carries the text spoken while it is on screen. If the user's script has headings per section, those are the paragraphs; sentences or phrases that need a new visual are the scenes.

## Procedure
1. **Write the script JSON** (format in `scripts/sync_vo.py` header; an example is in `references/example-script.json`). Use the exact words the user wrote. Do not rewrite or shorten them.
2. **Run** `python3 scripts/sync_vo.py AUDIO SCRIPT.json --out result.json`. It needs only ffmpeg/ffprobe and Python 3.
3. **Read the warnings and the paragraph table before trusting anything.** The output lists, for every paragraph, how long it actually lasts versus how long its share of the text predicts.
   - *Ambiguous breaks* — two similar-looking pauses are both plausible for a paragraph boundary. This is the most common failure, because a pause inside a paragraph can be as long as the one between paragraphs. Do not guess: ask the user which one is right ("ช่วงที่ 2 เริ่มประมาณวินาทีที่ 18 หรือ 21?"), or if you can judge from the script's content (a greeting that obviously ends at the first long pause), set `"start"` on that paragraph and re-run.
   - *Duration ratio off (below 0.6 or above 1.6)* — the recording probably skips, adds or reorders text compared with the script. Tell the user; do not force-fit. In one real case the first recording of a script was 40 s long and the user later supplied a 54 s recording of the same script, so the first take evidently lacked part of the text. Timing it as if it were complete would have put visuals on the wrong words. The duration check will not always catch this; when the total length is far below what the script's length predicts (about 4-4.5 syllables per second for Thai), ask the user.
4. **Use the scene start times** for cards/subtitles. Make scenes contiguous (each starts where the previous ends) and let the last one hold at least 2 seconds past the end of the speech.
5. **Report honestly**: give the user the table of scene start times, state that these are pause-based estimates, and list any scene where you made a judgement call. Offer to move a scene if they tell you "at 36 s the score appears late".

## Why the method looks like this
- Silence detection at -32 dB for at least 0.12 s catches breaths and sentence ends but not most mid-word dips in clean synthetic or studio voices. Raise the threshold toward -28 for noisy recordings, lower toward -40 for very clean ones.
- Weighting by letters and digits (not spaces or tone marks) is a rough stand-in for syllables and works for Thai and Latin text alike. Numbers like "1-0" are spoken slowly relative to their length, so a scene that is mostly figures may start a little early.
- Snapping a scene start onto the nearest pause (within about 1.3 s) beats pure proportional estimates because narrators begin a new idea after a breath. If no pause is near, the proportional estimate is used.

## When a transcript is available
If the user can provide an ElevenLabs/Whisper-style word-timing file, use it instead; it is strictly better. This skill exists for the case where that is not possible.

## Limits
- Needs audible pauses. A narrator who reads without breaths gives poor results; say so and ask for a version with pauses or for manual timestamps.
- Does not verify that the words spoken match the script beyond the duration ratio check.
- See `references/lessons.md` for details found while building and testing it.
