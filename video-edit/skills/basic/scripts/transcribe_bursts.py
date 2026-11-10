#!/usr/bin/env python3
"""
Transcribe each speech burst from detect_bursts.py in isolation.

Why isolate each burst instead of transcribing the whole file once: Whisper's
default settings (condition_on_previous_text=True, and its repeat-suppression
decoding) can merge or silently drop a repeated phrase when the same line is
said twice in a row with a short pause - a near-guarantee in raw single-take
recordings full of retakes. Cutting each silence-bounded burst out and
transcribing it alone, with condition_on_previous_text=False and temperature=0,
forces a fresh, unbiased decode of just that audio - this is what actually
surfaces hidden retakes and gives trustworthy text-to-timestamp mapping.

Engine (stt.py): ElevenLabs Scribe v2 by default, Groq Whisper if ElevenLabs
fails, local Whisper if neither works (it says so on stderr - tell the user).
Each burst is still its own request, so the isolation above holds. Bursts are
sent 4 at a time (ElevenLabs takes 8+ at once; Groq's 20/min limit is waited
out), so a take with 60 bursts comes back in well under a minute.

The local whisper model is loaded ONCE for the whole batch (not once per clip
via the CLI) - loading it per-clip wastes minutes on a long recording.

Usage:
    python3 transcribe_bursts.py audio.wav bursts.txt --language sr [--engine auto|local] [--terms "Masterbox, Claude"]

bursts.txt: tab-separated start<TAB>end per line (output of detect_bursts.py,
first two columns only are read).

Output (stdout, tab-separated): start<TAB>end<TAB>transcribed_text
"""
import argparse
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stt


def load_local(model_name):
    try:
        import whisper
    except ImportError:
        print("openai-whisper is not installed. Install with: pip3 install openai-whisper", file=sys.stderr)
        sys.exit(1)
    print(f"Loading local whisper model '{model_name}'...", file=sys.stderr)
    return whisper.load_model(model_name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("bursts_file")
    ap.add_argument("--language", default="sr")
    ap.add_argument("--engine", choices=["auto", "local"], default="auto",
                    help="auto = ElevenLabs, then Groq, then local whisper")
    ap.add_argument("--model", default="medium", help="local whisper model (fallback only)")
    ap.add_argument("--terms", default="", help="comma-separated names/terms spelled as they should be")
    ap.add_argument("--pad", type=float, default=0.2, help="seconds of padding added before/after each burst before transcribing")
    args = ap.parse_args()

    bursts = []
    with open(args.bursts_file) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                bursts.append((float(parts[0]), float(parts[1])))

    if not bursts:
        print("No bursts found in bursts file.", file=sys.stderr)
        sys.exit(1)

    engines = stt.available() if args.engine == "auto" else []
    terms = [t.strip() for t in args.terms.split(",") if t.strip()]
    if engines:
        print(f"Transcribing {len(bursts)} bursts with {' -> '.join(engines)}...", file=sys.stderr)
    else:
        print("No ElevenLabs or Groq key - using local whisper.", file=sys.stderr)

    with tempfile.TemporaryDirectory() as tmpdir:
        clips = []
        for s, e in bursts:
            clip_path = os.path.join(tmpdir, f"{s:.2f}_{e:.2f}.flac")
            subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-ss", str(max(0.0, s - args.pad)), "-to", str(e + args.pad),
                 "-i", args.audio, "-ac", "1", "-ar", "16000", clip_path, "-loglevel", "error"],
                stdin=subprocess.DEVNULL, check=True,
            )
            clips.append(clip_path)

        def cloud(clip):
            try:
                return stt.transcribe(clip, args.language, terms, engines=list(engines))["text"]
            except stt.STTError:
                return None

        texts = [None] * len(clips)
        if engines:
            with ThreadPoolExecutor(max_workers=4) as pool:
                texts = list(pool.map(cloud, clips))
        missing = [i for i, t in enumerate(texts) if t is None]
        if missing:
            if engines:
                print(f"{len(missing)} bursts failed in the cloud - transcribing them with local whisper.", file=sys.stderr)
            model = load_local(args.model)
            for i in missing:
                texts[i] = model.transcribe(clips[i], language=args.language,
                                            condition_on_previous_text=False, temperature=0)["text"].strip()

    for (s, e), text in zip(bursts, texts):
        print(f"{s}\t{e}\t{text}")


if __name__ == "__main__":
    main()
