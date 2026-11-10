#!/usr/bin/env python3
"""
Word-level timestamps for an already-cut video, for placing zoom changes on
specific words (see build_zoom_selections.py).

Run it on a render of the SAME cut (same clips, same padding) that the zoom
plan will be applied to - e.g. a plain cut or a previous zoom render - so the
word times line up with that render's clip boundaries.

Usage:
  word_times.py cut_video.mp4 words.json [--language sr] [--engine auto|local] [--terms "Masterbox"]

Engine (stt.py): ElevenLabs Scribe v2 by default, then Groq Whisper, then local
Whisper - one request with word timestamps, a second or two for a reel. A cut
reel has no retakes left, so the whole-file pass is safe here.

Writes a JSON list of [word, start, end] (seconds, in the cut video's timeline).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--language", default="sr")
    ap.add_argument("--engine", choices=["auto", "local"], default="auto")
    ap.add_argument("--model", default="medium", help="local whisper model (fallback only)")
    ap.add_argument("--terms", default="", help="comma-separated names/terms spelled as they should be")
    a = ap.parse_args()
    words = None
    with tempfile.TemporaryDirectory() as d:
        wav = os.path.join(d, "a.flac")
        stt.to_flac(a.video, wav)
        engines = stt.available() if a.engine == "auto" else []
        if "groq" in engines and os.path.getsize(wav) > 24 * 1024 * 1024:
            engines.remove("groq")   # over Groq's 25 MB upload limit
        if engines:
            try:
                r = stt.transcribe(wav, a.language, [t.strip() for t in a.terms.split(",") if t.strip()],
                                   words=True, engines=engines)
                words = [[w["word"], round(w["start"], 2), round(w["end"], 2)] for w in r["words"]]
                print(f"engine: {r['engine']}", file=sys.stderr)
            except stt.STTError as err:
                print(f"{err} - using local whisper.", file=sys.stderr)
        if words is None:
            import whisper
            r = whisper.load_model(a.model).transcribe(
                wav, language=a.language, word_timestamps=True,
                condition_on_previous_text=False, temperature=0)
            words = [[w["word"].strip(), round(float(w["start"]), 2), round(float(w["end"]), 2)]
                     for s in r["segments"] for w in s["words"]]
    json.dump(words, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{len(words)} words -> {a.out}")


if __name__ == "__main__":
    main()
