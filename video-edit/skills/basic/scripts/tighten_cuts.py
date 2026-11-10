#!/usr/bin/env python3
"""
Tighten a cut so it flows without dead air between sentences - the user's
standard pacing ("mora biti sve zbijenije i tečnije").

detect_bursts.py edges are conservative (its threshold misses quiet trailing
consonants), which is why cut_and_concat.sh defaults to 0.15s / 0.35s padding.
That padding leaves a ~0.5s pause at every cut, which the user found broke the
rhythm. This script instead finds where speech REALLY starts and ends around
each selection (a lower -42 dB threshold, 80 ms), and splits a selection at
any internal pause longer than --max-pause, so long breaths inside a kept
take are shortened too.

Writes start<TAB>end[<TAB>vf] lines for cut_and_concat.sh; cut them with
  PRE_PAD=0.04 POST_PAD=0.08 cut_and_concat.sh ...
(nothing gets clipped: the edges already sit on the real speech).

The user's reference reels (vodič stila, 2026-11-10) cut every pause: the
median gap between words is 0.06 s and only a handful of gaps in a whole
reel are longer than 0.25 s - hence --max-pause 0.25. The one exception is
on purpose: a dramatic beat before the last line (--beat 1.0) and a silent
look into the camera after it (--tail 2.0). Both only extend into real
silence of the source (the room tone and the speaker's face stay natural),
never into the next speech.

Usage:
  tighten_cuts.py audio.wav selections.txt tight.txt [--max-pause 0.25] [--beat 1.0] [--tail 2.0]
"""
import argparse
import re
import subprocess
import sys


def silences(wav):
    out = subprocess.run(["ffmpeg", "-nostdin", "-i", wav, "-af", "silencedetect=n=-42dB:d=0.08", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    res, st = [], None
    for m in re.finditer(r"silence_(start|end): ([\d.]+)", out):
        if m.group(1) == "start":
            st = float(m.group(2))
        else:
            res.append((st, float(m.group(2))))
    return res


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("wav")
    ap.add_argument("selections")
    ap.add_argument("out")
    ap.add_argument("--max-pause", type=float, default=0.25)
    ap.add_argument("--beat", type=float, default=0.0,
                    help="seconds of pause kept before the LAST selection (dramatic beat)")
    ap.add_argument("--tail", type=float, default=0.0,
                    help="seconds kept after the last word (silent look before the end card)")
    a = ap.parse_args()
    S = silences(a.wav)
    rows = []
    for line in open(a.selections, encoding="utf-8"):
        if not line.strip():
            continue
        s, e, *vf = line.rstrip("\n").split("\t")
        s, e = float(s), float(e)
        # real edges: the silence that ends just before s / starts just after e
        ns = min(max([b for _, b in S if b <= s + 0.3] or [s]), s + 0.05)
        ne = max(min([x for x, _ in S if x >= e - 0.3] or [e]), e - 0.05)
        cur = ns
        for x, y in S:
            if x > ns + 0.05 and y < ne - 0.05 and y - x > a.max_pause:
                rows.append((cur, x, vf))
                cur = y
        rows.append((cur, ne, vf))
        print(f"{s:.2f}-{e:.2f} -> {ns:.2f}-{ne:.2f}", file=sys.stderr)
    def extend(k, sec, what):
        s, e, vf = rows[k]
        room = min([y for x, y in S if x <= e + 0.1 and y > e] or [e + 0.05]) - 0.05 - e
        add = max(0.0, min(sec, room))
        rows[k] = (s, e + add, vf)
        print(f"{what}: +{add:.2f}s after {e:.2f}" + (f" (only {room:.2f}s of silence there)" if add < sec else ""),
              file=sys.stderr)

    if a.beat and len(rows) > 1:
        extend(len(rows) - 2, a.beat, "beat before the last line")
    if a.tail and rows:
        extend(len(rows) - 1, a.tail, "tail after the last word")
    with open(a.out, "w", encoding="utf-8") as f:
        for s, e, vf in rows:
            f.write("\t".join([f"{s:.3f}", f"{e:.3f}", *vf]) + "\n")
    print(f"{len(rows)} segments, {sum(e - s for s, e, _ in rows):.2f}s of speech", file=sys.stderr)


if __name__ == "__main__":
    main()
