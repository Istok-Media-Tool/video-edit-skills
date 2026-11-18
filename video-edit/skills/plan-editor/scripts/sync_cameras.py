#!/usr/bin/env python3
"""
Find which second-camera file belongs to which main-camera file, and the time
offset between them, from the sound both cameras recorded.

  second_time = main_time + offset

Output (stdout) is the "second_camera" block for apply_overlays.py, keyed by
the main file's name without extension:
  {"C0025": {"file": "/…/C0045.MP4", "offset": -2.258, "score": 282.9}, ...}

How: speech band (300-3000 Hz) at 4 kHz, normalised cross-correlation over the
whole files (FFT), then refined to 1 ms on a 60 s window. Score =
peak-to-noise of the correlation: a real pair scored 177-283 on "avocado hass"
(2026-11-18), wrong pairs 18-19; a main file whose best pair is under 40 or not
3x above the next one has no match (the cameras did not roll together).
It found C0045 = C0025 - 2.258 s and C0046 = C0026 + 2.255 s (hand-made test:
-2.263 / +2.25 - the same within a frame).

Usage:
  sync_cameras.py --main main/C0025.MP4 main/C0026.MP4 --second close/C0045.MP4 close/C0046.MP4
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfiltfilt

SR = 4000


def audio(path, sr=SR):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).astype(np.float64)
    sos = butter(4, [300, min(3000, sr / 2 - 100)], btype="band", fs=sr, output="sos")
    x = sosfiltfilt(sos, x)
    return x / (np.std(x) + 1e-9)


def best_lag(a, b):
    """lag (samples) where b[t + lag] matches a[t]; score = peak / std of the correlation
    (peak-to-noise: a real match stands 10-30x above it, a wrong pair ~5)."""
    c = np.abs(fftconvolve(b, a[::-1], mode="full"))
    k = int(np.argmax(c))
    return k - (len(a) - 1), float(c[k] / (np.std(c) + 1e-9))


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--main", nargs="+", required=True)
    ap.add_argument("--second", nargs="+", required=True)
    a = ap.parse_args()
    mains = {p: audio(p) for p in a.main}
    secs = {p: audio(p) for p in a.second}
    out = {}
    for m, x in mains.items():
        best, scores = None, []
        for s, y in secs.items():
            lag, score = best_lag(x, y)
            print(f"{Path(m).name} vs {Path(s).name}: offset {lag / SR:+.3f}s score {score:.2f}", file=sys.stderr)
            scores.append(score)
            if best is None or score > best[2]:
                best = (s, lag / SR, score)
        rest = sorted(scores)[:-1]
        if best[2] < 40 or (rest and best[2] < 3 * rest[-1]):
            print(f"{Path(m).name}: no second-camera match", file=sys.stderr)
            continue
        # refine to 1 ms on 60 s of speech in the middle of the overlap, at 16 kHz
        s, off, score = best
        xm, ys = audio(m, 16000), audio(s, 16000)
        t0 = max(0.0, -off) + 30
        seg = xm[int(t0 * 16000):int((t0 + 60) * 16000)]
        c0 = int((t0 + off - 0.05) * 16000)
        win = ys[max(0, c0):c0 + len(seg) + 1600]
        if len(seg) > 16000 and len(win) > len(seg):
            c = np.correlate(win, seg, mode="valid")
            off = (max(0, c0) + int(np.argmax(c))) / 16000 - t0
        out[Path(m).stem] = {"file": str(Path(s).resolve()), "offset": round(off, 3), "score": round(score, 2)}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
