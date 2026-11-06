#!/usr/bin/env python3
"""
Turn a zoom plan from the interactive widget (PLAN_JSON) into a selections
file for cut_and_concat.sh, with each zoom change landing just before its
chosen word.

Why word-anchored: zoom has to follow the script - a punch-in lands on the
word that justifies it (a reveal, a key term, a personal question), and
pull-backs land on words about scale. Zoom placed per clip or at arbitrary
midpoints read as random to the user. Changes can happen mid-clip and more
than once per clip.

How a clip with several levels is rendered: the frame is split into one
crop per level and the later levels are overlaid only during their time
window (overlay enable='between(t,a,b)'), so the zoom change is a clean
punch-in/out at an exact time inside one continuous clip - no extra cut, no
audio seam.

Inputs:
  --cuts        source cut points, one "start<TAB>end" per clip (unpadded,
                as in the basic skill's selections file)
  --positions   JSON [[cx, head_top_y], ...] per clip, measured on the
                (rotated, if applicable) frame - see compute_crop.py
  --plan        PLAN_JSON from the widget: [{"s": lvl, "m": {"<word idx>": lvl}}]
                lvl: 0=wide (centered --baseline crop, ~1.2x) 1=1.5x 2=1.7x 3=2.0x 4=2.2x
  --sentences   the sentences file given to plan-editor/scripts/make_plan_widget.py (1 per clip)
  --words       word_times.py output for a render of the same cut
  --durations   comma list of that render's clip durations (ffprobe each
                clip_NNN.mp4), so word times map back into each clip
  --pre-filter  filter prepended to every chain, e.g. "transpose=1" for
                footage shot sideways (rotation happens BEFORE cropping,
                and --positions must be measured on the rotated frame)
  --lead        seconds the change lands before the word starts (default 0.08)

Prints a match report (planned word -> matched spoken word and its time) so
every placement can be checked before rendering.

Usage:
  build_zoom_selections.py --cuts cuts.txt --positions pos.json --plan plan.json \
    --sentences sentences.txt --words words.json --durations 6.28,6.08,... \
    [--pre-filter transpose=1] > selections.txt
"""
import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

LEVELS = [1.0, 1.5, 1.7, 2.0, 2.2]  # the user's chosen zoom steps
# Level 0 ("1.0x", the wide shot) is NOT the raw frame: the user wants it
# centered with headroom like every other shot, so it is the loosest
# --baseline crop (~1.2x) that meets the headroom target.
CROP = Path(__file__).resolve().parent / "compute_crop.py"

CYR = dict(zip("абвгдђежзијклљмнњопрстћуфхцчџшАБВГДЂЕЖЗИЈКЛЉМНЊОПРСТЋУФХЦЧЏШ",
               ["a", "b", "v", "g", "d", "đ", "e", "ž", "z", "i", "j", "k", "l", "lj", "m", "n", "nj",
                "o", "p", "r", "s", "t", "ć", "u", "f", "h", "c", "č", "dž", "š"] * 2))


def norm(w):
    w = "".join(CYR.get(c, c) for c in w).lower()
    return re.sub(r"[^\wčćžšđ]", "", w)


HEADROOM = None  # --headroom: more space above the head, e.g. for a header graphic


def crop(cx, ht, lvl, wide=None):
    # --wide-zoom: a fixed zoom for level 0 when the baseline crop shows too
    # much (on a real reel it showed half the desk and its bottom edge)
    if lvl == 0:
        args = ["--zoom", str(wide)] if wide else ["--baseline"]
    else:
        args = ["--zoom", str(LEVELS[lvl])]
    if HEADROOM is not None:
        args += ["--headroom", str(HEADROOM)]
    out = subprocess.check_output([sys.executable, str(CROP), "--cx", str(cx), "--head-top-y", str(ht)] + args)
    return out.decode().splitlines()[0]


def find_word(target_words, j, spoken):
    """Time of sentence word j among this clip's spoken words [(norm, start)]."""
    t = norm(target_words[j])
    nth = sum(1 for w in target_words[:j] if norm(w) == t)
    hits = [s for n, s in spoken if n == t]
    if len(hits) > nth:
        return hits[nth], "exact"
    # fuzzy: best text similarity, ties broken by expected relative position
    expect = j / max(1, len(target_words) - 1)
    best = None
    for k, (n, s) in enumerate(spoken):
        score = difflib.SequenceMatcher(None, t, n).ratio() - 0.3 * abs(k / max(1, len(spoken) - 1) - expect)
        if best is None or score > best[0]:
            best = (score, s, n)
    if best and best[0] > 0.45:
        return best[1], f"fuzzy~{best[2]}"
    return None, "none"


def main():
    ap = argparse.ArgumentParser()
    for a in ("--cuts", "--positions", "--plan", "--sentences", "--words", "--durations"):
        ap.add_argument(a, required=True)
    ap.add_argument("--pre-filter", default="")
    ap.add_argument("--lead", type=float, default=0.08)
    ap.add_argument("--wide-zoom", type=float, default=None,
                    help="zoom for level 0 instead of the --baseline crop, e.g. 1.3")
    ap.add_argument("--headroom", type=float, default=None,
                    help="headroom fraction passed to compute_crop.py (default there: 0.09)")
    a = ap.parse_args()
    global HEADROOM
    HEADROOM = a.headroom

    cuts = [l.rstrip("\n").split("\t")[:2] for l in open(a.cuts) if l.strip()]
    pos = json.load(open(a.positions))
    plan = json.load(open(a.plan))
    sents = [l.strip() for l in open(a.sentences, encoding="utf-8") if l.strip()]
    words = json.load(open(a.words, encoding="utf-8"))
    durs = [float(x) for x in a.durations.split(",")]
    n = len(cuts)
    if not (len(pos) == len(plan) == len(sents) == len(durs) == n):
        sys.exit(f"count mismatch: cuts {n}, positions {len(pos)}, plan {len(plan)}, "
                 f"sentences {len(sents)}, durations {len(durs)}")

    starts = [0.0]
    for d in durs:
        starts.append(starts[-1] + d)
    pre = (a.pre_filter + ",") if a.pre_filter else ""

    for i in range(n):
        cs, ce = starts[i], starts[i + 1]
        spoken = [(norm(w), s - cs) for w, s, _ in words if cs - 0.05 <= s < ce]
        tw = sents[i].split(" ")
        changes = [(0.0, plan[i]["s"])]
        for j, lvl in sorted(((int(k), v) for k, v in plan[i]["m"].items())):
            t, how = find_word(tw, j, spoken)
            if t is None:
                t = durs[i] * j / max(1, len(tw))
                how = "proportional (no match!)"
            t = round(max(0.0, t - a.lead), 2)
            print(f"clip {i + 1}: '{tw[j]}' -> {LEVELS[lvl]} at {t:.2f}s in clip ({how})", file=sys.stderr)
            changes.append((t, lvl))
        cx, ht = pos[i]
        crops = [crop(cx, ht, lvl, a.wide_zoom) for _, lvl in changes]
        if len(changes) == 1:
            vf = f"{pre}{crops[0]},setsar=1"
        else:
            m = len(changes)
            g = [f"{pre}setpts=PTS-STARTPTS,split={m}" + "".join(f"[s{k}]" for k in range(m))]
            g += [f"[s{k}]{crops[k]}[c{k}]" for k in range(m)]
            cur = "c0"
            for k in range(1, m):
                t0 = changes[k][0]
                en = f"gte(t,{t0})" if k + 1 == m else f"between(t,{t0},{changes[k + 1][0]})"
                g.append(f"[{cur}][c{k}]overlay=enable='{en}'[o{k}]")
                cur = f"o{k}"
            g[-1] = g[-1].rsplit("[", 1)[0] + ",setsar=1"
            vf = ";".join(g)
        print(f"{cuts[i][0]}\t{cuts[i][1]}\t{vf}")


if __name__ == "__main__":
    main()
