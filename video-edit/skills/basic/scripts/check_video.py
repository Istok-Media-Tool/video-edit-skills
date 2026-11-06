#!/usr/bin/env python3
"""
Check a finished (or cut) video for the glitches that must never reach the
user: stray / held frames at cuts, shots only a few frames long, audio
drifting from video, and captions that flash or show on the wrong shot.

Run it on EVERY render before sending it. It found what the user caught by
eye on a real reel (one stray frame of the wide shot at 1:05) plus ten
more held frames nobody had noticed.

Checks:
  1. timestamp holes: consecutive frames more than 1.5 frame apart, and
     lone repeated frames (the same hole after a re-encode filled it) - a
     held frame on screen, the concat-demuxer bug, see cut_and_concat.sh
  2. audio vs video length (drift)
  3. very short shots: two picture cuts less than --min-shot apart
     (a 1-3 frame flash, e.g. an overlay ending a few frames before a cut)
  4. with --ass: caption screens shorter than 0.4s, and screens that start
     or end 1-3 frames away from a picture cut (they show on the wrong shot)
  5. with --edges (one time per line, seconds): overlay / zoom edges that
     sit 2-5 frames from a picture cut
  6. with --cuts (the joins of the cut list, one time per line): jump cuts
     inside the same framing, which scene detection misses, count as cuts
     for 3-5 - a zoom change 3 frames before one is a 3-frame flash
  7. with --fx (one "start end" window per line): intentional transition
     effects (TV static, glitch). Every frame there changes, so picture
     cuts detected inside a window or on its end are not counted

Exit code 1 if anything is found; prints each problem with its time.

Usage:
  check_video.py video.mp4 [--ass captions.ass] [--edges edges.txt] [--cuts joins.txt] [--fx fx.txt] [--min-shot 0.2]
"""
import argparse
import re
import subprocess
import sys


def probe(args):
    return subprocess.check_output(["ffprobe", "-v", "error"] + args).decode()


def t2s(x):
    h, m, s = x.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("video")
    ap.add_argument("--ass")
    ap.add_argument("--edges", help="times (s) of overlay starts/ends to test against picture cuts")
    ap.add_argument("--cuts", help="times (s) of the cut list's joins (e.g. from durs.txt), one per line")
    ap.add_argument("--fx", help="'start end' windows (s) of intentional transition effects, one per line")
    ap.add_argument("--min-shot", type=float, default=0.2)
    ap.add_argument("--scene", type=float, default=0.25)
    a = ap.parse_args()
    bad = []
    num, den = probe(["-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0",
                      a.video]).strip().split("/")
    fr = int(den) / int(num)

    # 1. holes
    raw = probe(["-select_streams", "v:0", "-show_entries", "frame=best_effort_timestamp_time", "-of", "csv=p=0",
                 a.video]).split()
    ts = sorted(float(x.split(",")[0]) for x in raw if x.split(",")[0] not in ("", "N/A"))
    for p, q in zip(ts, ts[1:]):
        if q - p > 1.5 * fr:
            bad.append(f"{p:7.2f}s  held frame: {round((q - p) / fr) - 1} frame(s) missing before {q:.2f}s")
    # 1b. repeated frames: a hole that a later re-encode (-r) filled with a
    # copy of the previous frame. A lone repeat is a glitch; a cluster is just
    # a still picture (a photo close-up), so only isolated ones count.
    out = subprocess.run(["ffmpeg", "-nostdin", "-i", a.video, "-vf", "mpdecimate=max=0:hi=200:lo=100:frac=0.5,showinfo",
                          "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    kept = [float(m.group(1)) for m in re.finditer(r"pts_time:([\d.]+)", out)]
    rep = [p for p, q in zip(kept, kept[1:]) if q - p > 1.5 * fr]
    for k, t in enumerate(rep):
        if all(abs(t - u) > 0.3 for j, u in enumerate(rep) if j != k):
            bad.append(f"{t:7.2f}s  repeated (frozen) frame")
    # 2. drift
    d = {}
    for line in probe(["-show_entries", "stream=codec_type,duration", "-of", "csv=p=0", a.video]).split():
        k, v = line.split(",")[:2]
        if v in ("", "N/A"):
            continue
        d.setdefault(k, float(v))
    if "audio" in d and abs(d["audio"] - d["video"]) > 1.5 * fr:
        bad.append(f"  end    audio {d['audio']:.2f}s vs video {d['video']:.2f}s - out of sync")
    # 3. short shots
    out = subprocess.run(["ffmpeg", "-nostdin", "-i", a.video, "-vf", "select='gte(scene,0)',metadata=print:key=lavfi.scene_score",
                          "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    score = {}
    for m in re.finditer(r"pts_time:([\d.]+)\s*\n[^\n]*lavfi\.scene_score=([\d.]+)", out):
        score[round(float(m.group(1)), 2)] = float(m.group(2))
    cuts = sorted(t for t, s in score.items() if s > a.scene)
    if a.cuts:
        # jump cuts inside one shot (same framing) score far below --scene,
        # so a zoom change 3 frames before one went unnoticed on a real reel
        # (1:15). Known join points count as cuts when they are visible at
        # all (a join under a close-up scores ~0).
        for line in open(a.cuts):
            if line.strip():
                t = float(line.split()[0])
                k = min(score, key=lambda x: abs(x - t)) if score else None
                if k is not None and abs(k - t) < fr and score[k] > 0.02 and all(abs(c - t) > 1.5 * fr for c in cuts):
                    cuts.append(k)
        cuts.sort()
    if a.fx:
        win = [tuple(map(float, l.split()[:2])) for l in open(a.fx) if l.strip()]
        cuts = [c for c in cuts if not any(s0 - fr / 2 <= c <= e0 + fr / 2 for s0, e0 in win)]
    for p, q in zip(cuts, cuts[1:]):
        if q - p < a.min_shot:
            bad.append(f"{p:7.2f}s  shot only {round((q - p) / fr)} frame(s) long (cut at {p:.2f}s and {q:.2f}s)")
    # 4. captions
    if a.ass:
        for line in open(a.ass, encoding="utf-8"):
            if not line.startswith("Dialogue:"):
                continue
            p = line.split(",", 9)
            if p[3] != "Default":
                continue
            s, e, txt = t2s(p[1]), t2s(p[2]), p[9].strip().replace("\\N", " ")[:40]
            if e - s < 0.4:
                bad.append(f"{s:7.2f}s  caption on screen only {e - s:.2f}s: {txt}")
            for c in cuts:
                if 0 < c - s <= 3.5 * fr:
                    bad.append(f"{s:7.2f}s  caption starts {round((c - s) / fr)} frame(s) before the cut at {c:.2f}s: {txt}")
                if 0 < e - c <= 3.5 * fr:
                    bad.append(f"{e:7.2f}s  caption ends {round((e - c) / fr)} frame(s) after the cut at {c:.2f}s: {txt}")
    # 5. overlay edges
    if a.edges:
        for line in open(a.edges):
            if not line.strip():
                continue
            t = float(line.split()[0])
            for c in cuts:
                # within 1 frame = the cut this edge itself makes
                if 1.5 * fr < abs(c - t) <= 5.5 * fr:
                    bad.append(f"{t:7.2f}s  overlay edge {round((t - c) / fr):+d} frame(s) from the cut at {c:.2f}s")
    print(f"{len(ts)} frames, {len(cuts)} picture cuts, video {d.get('video', 0):.2f}s, audio {d.get('audio', 0):.2f}s")
    for b in bad:
        print(b)
    print("OK - nothing found" if not bad else f"{len(bad)} problem(s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
