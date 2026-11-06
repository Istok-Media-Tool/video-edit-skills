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

The whisper model is loaded ONCE for the whole batch (not once per clip via
the CLI) - loading it per-clip wastes minutes on a long recording.

Usage:
    python3 transcribe_bursts.py audio.wav bursts.txt --language sr --model medium

bursts.txt: tab-separated start<TAB>end per line (output of detect_bursts.py,
first two columns only are read).

Output (stdout, tab-separated): start<TAB>end<TAB>transcribed_text
"""
import argparse
import os
import subprocess
import sys
import tempfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("bursts_file")
    ap.add_argument("--language", default="sr")
    ap.add_argument("--model", default="medium")
    ap.add_argument("--pad", type=float, default=0.2, help="seconds of padding added before/after each burst before transcribing")
    args = ap.parse_args()

    try:
        import whisper
    except ImportError:
        print("openai-whisper is not installed. Install with: pip3 install openai-whisper", file=sys.stderr)
        sys.exit(1)

    bursts = []
    with open(args.bursts_file) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                bursts.append((float(parts[0]), float(parts[1])))

    if not bursts:
        print("No bursts found in bursts file.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading whisper model '{args.model}'...", file=sys.stderr)
    model = whisper.load_model(args.model)

    with tempfile.TemporaryDirectory() as tmpdir:
        for s, e in bursts:
            clip_path = os.path.join(tmpdir, f"{s:.2f}_{e:.2f}.wav")
            pad_s = max(0.0, s - args.pad)
            pad_e = e + args.pad
            subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-ss", str(pad_s), "-to", str(pad_e),
                 "-i", args.audio, clip_path, "-loglevel", "error"],
                stdin=subprocess.DEVNULL, check=True,
            )
            result = model.transcribe(
                clip_path, language=args.language,
                condition_on_previous_text=False, temperature=0,
            )
            text = result["text"].strip()
            print(f"{s}\t{e}\t{text}")


if __name__ == "__main__":
    main()
