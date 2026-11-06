#!/usr/bin/env python3
"""
Overlay B-roll (video clips or still images) on a cut video, each one shown
from the start of a chosen word to the end of another chosen word - the
ranges the user marks in the plan editor's "B-roll" mode (BROLL_JSON).

The speaker's audio keeps playing underneath; B-roll audio is dropped.
Media is scaled to COVER the frame (crop, never letterbox). A video shorter
than its range freezes on its last frame; an image is held for the range.

Run it on the zoomed video BEFORE burning captions, so captions stay on top
of the B-roll.

Inputs:
  video         the cut (and zoomed) video, e.g. zoom render, no captions
  --broll       BROLL_JSON: [{"from": [clip, word], "to": [clip, word], "media": path}]
                word = index in sentences.txt line `clip` split on spaces.
                Every "media" must be an existing file by now: if the user
                typed a description instead of a path, get the actual file
                first (ask them, or source it), then write its path in.
  --sentences   sentences.txt (the SENTENCES_JSON from the same reply)
  --words       word_times.py output FOR THIS VIDEO (zoom/scripts/word_times.py)
  --durations   comma list of this video's clip durations (ffprobe clip_NNN.mp4)
  --lead        seconds the B-roll starts before its first word (default 0.08)
  --tail        seconds it stays after its last word ends (default 0.10)

Prints where each range landed (and how each word was matched) for checking.

Usage:
  apply_broll.py zoomed.mp4 out.mp4 --broll broll.json --sentences sentences.txt \
    --words words.json --durations 6.28,6.04,...
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "zoom", "scripts"))
from build_zoom_selections import norm  # noqa: E402  (same word normalisation as zoom placement)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic"}


def probe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height,r_frame_rate:format=duration", "-of", "json", path])
    d = json.loads(out)
    s = d["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(num) / float(den), float(d["format"]["duration"])


def find_span(target_words, j, spoken):
    """(start, end, how) of sentence word j among this clip's spoken (norm, start, end)."""
    t = norm(target_words[j])
    nth = sum(1 for w in target_words[:j] if norm(w) == t)
    hits = [(s, e) for n, s, e in spoken if n == t]
    if len(hits) > nth:
        return hits[nth] + ("exact",)
    import difflib
    expect = j / max(1, len(target_words) - 1)
    best = None
    for k, (n, s, e) in enumerate(spoken):
        score = difflib.SequenceMatcher(None, t, n).ratio() - 0.3 * abs(k / max(1, len(spoken) - 1) - expect)
        if best is None or score > best[0]:
            best = (score, s, e, n)
    if best and best[0] > 0.45:
        return best[1], best[2], f"fuzzy~{best[3]}"
    return None, None, "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    for a in ("--broll", "--sentences", "--words", "--durations"):
        ap.add_argument(a, required=True)
    ap.add_argument("--lead", type=float, default=0.08)
    ap.add_argument("--tail", type=float, default=0.10)
    a = ap.parse_args()

    ranges = json.load(open(a.broll, encoding="utf-8"))
    sents = [l.strip() for l in open(a.sentences, encoding="utf-8") if l.strip()]
    words = json.load(open(a.words, encoding="utf-8"))
    durs = [float(x) for x in a.durations.split(",")]
    if len(durs) != len(sents):
        sys.exit(f"{len(durs)} durations but {len(sents)} sentences")
    starts = [0.0]
    for d in durs:
        starts.append(starts[-1] + d)
    W, H, fps, total = probe(a.video)

    def at(ref):
        i, j = ref
        cs, ce = starts[i], starts[i + 1]
        spoken = [(norm(w), s - cs, e - cs) for w, s, e in words if cs - 0.05 <= s < ce]
        tw = sents[i].split(" ")
        s, e, how = find_span(tw, j, spoken)
        if s is None:
            sys.exit(f"clip {i + 1}: word '{tw[j]}' not found in the transcript - place this range by hand")
        return cs + s, cs + e, f"'{tw[j]}' ({how})"

    inputs, chains, overlays = [], [], []
    for k, r in enumerate(ranges, 1):
        media = os.path.expanduser(r["media"])
        if not os.path.isfile(media):
            sys.exit(f"B{k}: media is not a file: {r['media']!r} - resolve it to a real file first")
        s0, _, how0 = at(r["from"])
        _, e1, how1 = at(r["to"])
        t0 = round(max(0.0, s0 - a.lead), 3)
        t1 = round(min(total, e1 + a.tail), 3)
        dur = round(t1 - t0, 3)
        print(f"B{k}: {t0:.2f}s -> {t1:.2f}s ({dur:.2f}s)  from {how0} to {how1}  [{os.path.basename(media)}]",
              file=sys.stderr)
        is_img = os.path.splitext(media)[1].lower() in IMAGE_EXT
        inputs += (["-loop", "1", "-t", str(dur), "-i", media] if is_img else ["-t", str(dur), "-i", media])
        hold = "" if is_img else f",tpad=stop_mode=clone:stop_duration={dur}"
        chains.append(f"[{k}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                      f"fps={fps:g},format=yuv420p{hold},trim=duration={dur},setpts=PTS-STARTPTS+{t0}/TB[b{k}]")
        overlays.append((k, t0, t1))

    if not overlays:
        sys.exit("no B-roll ranges")
    cur = "0:v"
    for k, t0, t1 in overlays:
        nxt = f"v{k}"
        chains.append(f"[{cur}][b{k}]overlay=enable='between(t,{t0},{t1})':eof_action=pass[{nxt}]")
        cur = nxt
    cmd = (["ffmpeg", "-nostdin", "-y", "-i", a.video] + inputs +
           ["-filter_complex", ";".join(chains), "-map", f"[{cur}]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "copy", a.out, "-loglevel", "error"])
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)
    print(f"-> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
