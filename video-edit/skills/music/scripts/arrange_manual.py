#!/usr/bin/env python3
"""
Hand-made arrangement: play chosen stretches of a track at chosen places of
the video, joined with short equal-power crossfades, ending on the track's
own ending.

The fallback when arrange_music.py can't do it. On "avocado hass"
(2026-11-18) the track ("Dust on the Road") ends in a fade, so track_map
found no closure and arrange_music reused the same hit three times; the
reference editor had simply jumped the track at three section starts and let
its real last seconds play under the end. This script does exactly that.

  --at "0:0, 90.18:16.68, 105.54:47.45"   video_time:track_time - from that
        video time on, the track plays from that track time (put each jump
        on a bar line of the track: track_map.py's bars / sections)
  --end-on-track-end                       the last stretch is placed so the
        TRACK's end lands on the video's end (its own fade / final chord),
        starting at the video time given by --end-from (default: the last
        --at point gets cut to make room, see the report)
  --xfade 0.04                             crossfade at each join (s)

Every join is reported (video time, track time before -> after) to listen to.

Usage:
  arrange_manual.py track.mp3 out.wav --video video.mp4 --at "0:0,90.18:16.68,105.54:47.45" \
      --end-on-track-end --end-from 129.84
Then mix_bed.py video.mp4 out.wav final.mp4 --track-start 0 (the wav already fits the video).
"""
import argparse
import subprocess
import sys

import numpy as np

SR = 48000


def load(path):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-vn", "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", path]).decode())


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("track")
    ap.add_argument("out")
    ap.add_argument("--video", required=True)
    ap.add_argument("--at", required=True)
    ap.add_argument("--end-on-track-end", action="store_true")
    ap.add_argument("--end-from", type=float, help="video time where the track's last stretch begins")
    ap.add_argument("--xfade", type=float, default=0.04)
    a = ap.parse_args()

    tr = load(a.track)
    T = len(tr) / SR
    V = dur(a.video)
    pts = sorted((float(x.split(":")[0]), float(x.split(":")[1])) for x in a.at.split(",") if x.strip())
    if pts[0][0] > 0.001:
        sys.exit("the first --at must start at video time 0")
    if a.end_on_track_end:
        start = a.end_from if a.end_from is not None else max(pts[-1][0] + 1, V - 8)
        pts = [p for p in pts if p[0] < start - 0.5] + [(start, T - (V - start))]
        if pts[-1][1] < 0:
            sys.exit("--end-from leaves more video than the track has")
    n = int(round(V * SR))
    out = np.zeros((n, 2))
    xf = int(a.xfade * SR)
    for k, (vt, tt) in enumerate(pts):
        v0 = int(round(vt * SR))
        v1 = int(round(pts[k + 1][0] * SR)) if k + 1 < len(pts) else n
        t0 = int(round(tt * SR))
        seg_len = v1 - v0 + (xf if k + 1 < len(pts) else 0)
        seg = tr[t0:t0 + seg_len]
        if len(seg) < seg_len:
            print(f"warning: track runs out {((seg_len - len(seg)) / SR):.2f}s before the next join at video "
                  f"{(v1 / SR):.2f}s - silence there", file=sys.stderr)
            seg = np.vstack([seg, np.zeros((seg_len - len(seg), 2))])
        g = np.ones(len(seg))
        if k > 0 and xf:                              # fade in (equal power)
            g[:xf] = np.sin(np.linspace(0, np.pi / 2, xf))
        if k + 1 < len(pts) and xf:                   # fade out into the next stretch
            g[-xf:] = np.cos(np.linspace(0, np.pi / 2, xf))
        end = min(n, v0 + len(seg))
        out[v0:end] += seg[:end - v0] * g[:end - v0, None]
        if k:
            prev_tt = pts[k - 1][1] + (vt - pts[k - 1][0])
            print(f"join at video {vt:7.2f}s: track {prev_tt:6.2f}s -> {tt:6.2f}s", file=sys.stderr)
    peak = np.max(np.abs(out))
    if peak > 1:
        out /= peak
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s24le", a.out], input=out.astype(np.float32).tobytes(), check=True)
    last = pts[-1]
    print(f"-> {a.out} ({V:.2f}s); last stretch: video {last[0]:.2f}s = track {last[1]:.2f}s"
          + (" -> track end on the video's last frame" if a.end_on_track_end else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
