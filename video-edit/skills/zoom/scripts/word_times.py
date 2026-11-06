#!/usr/bin/env python3
"""
Word-level timestamps for an already-cut video, for placing zoom changes on
specific words (see build_zoom_selections.py).

Run it on a render of the SAME cut (same clips, same padding) that the zoom
plan will be applied to - e.g. a plain cut or a previous zoom render - so the
word times line up with that render's clip boundaries.

Usage:
  word_times.py cut_video.mp4 words.json [--language sr] [--model medium]

Writes a JSON list of [word, start, end] (seconds, in the cut video's timeline).
"""
import argparse
import json
import os
import subprocess
import tempfile

import whisper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--language", default="sr")
    ap.add_argument("--model", default="medium")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as d:
        wav = os.path.join(d, "a.wav")
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-i", a.video, "-vn", "-ac", "1", "-ar", "16000",
                        wav, "-loglevel", "error"], check=True, stdin=subprocess.DEVNULL)
        r = whisper.load_model(a.model).transcribe(
            wav, language=a.language, word_timestamps=True,
            condition_on_previous_text=False, temperature=0)
    words = [[w["word"].strip(), round(float(w["start"]), 2), round(float(w["end"]), 2)]
             for s in r["segments"] for w in s["words"]]
    json.dump(words, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{len(words)} words -> {a.out}")


if __name__ == "__main__":
    main()
