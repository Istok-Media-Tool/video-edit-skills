#!/usr/bin/env python3
"""
Find real speech bursts in an audio file using ffmpeg's silencedetect filter.

Whisper's own segment timestamps are NOT reliable for cutting: when a speaker
pauses mid-sentence, stumbles, or repeats a line, Whisper often merges the
pause (sometimes several seconds of it) into one segment, or silently drops a
repeated phrase. Sample-accurate silence detection is the ground truth for
"where does speech actually start and stop" - use this BEFORE trusting any
Whisper timestamp for a cut point.

Usage:
    python3 detect_bursts.py audio.wav [--noise -30dB] [--min-silence 0.4] [--min-burst 0.5]

Output (stdout, tab-separated): start_seconds<TAB>end_seconds<TAB>duration_seconds
One line per detected burst, in chronological order.
"""
import argparse
import re
import subprocess
import sys


def detect_silence(path, noise, min_silence):
    cmd = [
        "ffmpeg", "-nostdin", "-i", path,
        "-af", f"silencedetect=noise={noise}:d={min_silence}",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    starts, ends = [], []
    for line in proc.stdout.splitlines():
        m = re.search(r"silence_start:\s*([\-0-9.]+)", line)
        if m:
            starts.append(float(m.group(1)))
        m = re.search(r"silence_end:\s*([\-0-9.]+)", line)
        if m:
            ends.append(float(m.group(1)))
    return starts, ends


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--noise", default="-30dB", help="silencedetect noise floor")
    ap.add_argument("--min-silence", type=float, default=0.4, help="minimum silence duration to count as a gap")
    ap.add_argument("--min-burst", type=float, default=0.5, help="discard bursts shorter than this (likely breath/noise, not real speech)")
    args = ap.parse_args()

    starts, ends = detect_silence(args.audio, args.noise, args.min_silence)
    if not ends or not starts:
        print(f"No silence detected in {args.audio} - file may be too short, too loud throughout, or the noise floor is wrong for this recording.", file=sys.stderr)
        sys.exit(1)

    bursts = []
    for i in range(len(ends)):
        if i + 1 < len(starts):
            b_start, b_end = ends[i], starts[i + 1]
            if b_end - b_start > args.min_burst:
                bursts.append((round(b_start, 2), round(b_end, 2)))

    for s, e in bursts:
        print(f"{s}\t{e}\t{round(e - s, 2)}")

    print(f"{len(bursts)} bursts found", file=sys.stderr)


if __name__ == "__main__":
    main()
