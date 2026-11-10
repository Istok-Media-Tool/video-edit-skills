#!/usr/bin/env python3
"""
Check every caption screen of an .ass file against the Instagram safe zone
(basic skill, "Instagram safe zone"): on 1080x1920 everything must sit in
x 120-960, y 260-1330 and out of the button rail (x > 860, y 950-1660).

Renders each Dialogue event once (middle of its time) on a flat grey frame
with the same libass / fonts as the burn, and measures the real pixels -
box, outline and shadow included - so a long word or CAPITALS that libass
draws wider than expected are caught before the full render.

Usage:
  check_safe_zone.py captions.ass [--ffmpeg /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg]
Exit code 1 when any screen is outside.
"""
import argparse
import os
import subprocess
import sys

import numpy as np


def ts(x):
    h, m, s = x.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("ass")
    ap.add_argument("--ffmpeg", default="/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
    a = ap.parse_args()
    W, H = 1080, 1920
    ev = []
    for line in open(a.ass, encoding="utf-8"):
        if line.startswith("PlayResX:"):
            W = int(line.split(":")[1])
        elif line.startswith("PlayResY:"):
            H = int(line.split(":")[1])
        elif line.startswith("Dialogue:"):
            p = line.rstrip("\n").split(",", 9)
            ev.append(((ts(p[1]) + ts(p[2])) / 2, p[3], p[9]))
    if not ev:
        sys.exit("no Dialogue events")
    k, kh = W / 1080, H / 1920
    x0z, x1z, y0z, y1z = 120 * k, 960 * k, 260 * kh, 1330 * kh
    rail_x, rail_y0, rail_y1 = 860 * k, 950 * kh, 1660 * kh
    sel = "+".join(f"between(t,{t:.3f},{t + 0.039:.3f})" for t, _, _ in ev)
    fonts = os.path.expanduser("~/Library/Fonts")
    raw = subprocess.run([a.ffmpeg, "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                          f"color=c=0x808080:s={W}x{H}:d={ev[-1][0] + 1:.2f}:r=25",
                          "-vf", f"subtitles={a.ass}:fontsdir={fonts},select='{sel}'",
                          "-fps_mode", "vfr", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W)
    bad = 0
    for (t, style, text), f in zip(ev, frames):
        ys, xs = np.where(np.abs(f.astype(int) - 128) > 20)
        if not len(xs):
            continue
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        why = []
        if x0 < x0z or x1 > x1z:
            why.append(f"x {x0}-{x1}")
        if y0 < y0z or y1 > y1z:
            why.append(f"y {y0}-{y1}")
        if x1 > rail_x and y1 > rail_y0 and y0 < rail_y1:
            why.append("button rail")
        if why:
            bad += 1
            print(f"{t:7.2f}s {style}: {', '.join(why)}  |  {text[:60]}")
    print(f"{len(frames)} screens checked, {bad} outside the safe zone")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
