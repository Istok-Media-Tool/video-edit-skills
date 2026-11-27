#!/usr/bin/env python3
r"""
Never let a caption cover a face - checked on the real picture, every screen.

check_safe_zone.py renders captions on flat grey, so it cannot see what is
UNDER a caption. This one can. For every Dialogue event of an .ass file it:
  1. renders the card alone with the burn's libass/fonts and measures its box
     (box, outline and shadow included);
  2. takes frames of the video under that card (every --step s, start to end)
     and finds faces and hands with Apple Vision;
  3. reports every card that touches a head (face box widened to hair above
     and chin/beard below, plus --air px) - faces in photos and B-roll count;
     hands count when the frame has no face (a close-up / insert, where the
     hands ARE the action; --hands always|never to change that);
  4. with --fix: moves each such card to the nearest height where it touches
     no head/hand in ANY of its frames and stays in the Instagram safe zone
     (y 260-1330, out of the button rail) - by the event's own MarginV, the
     same field the plan-editor sliders write - and writes the fixed .ass
     and/or the moves as POS_JSON for the plan-editor (make_plan_widget.py
     --pos), so the user sees them already moved.

The video must be the picture the captions go on, WITHOUT captions burned in
(after zoom, B-roll and close-ups), on the same timeline as the .ass.

Usage:
  check_caption_overlap.py captions.ass picture.mp4 [--fix fixed.ass] [--pos-json pos.json]
                           [--step 0.2] [--air 24] [--hands auto|always|never]
Exit code 1 while any card still covers a face (after --fix: one that has no free height).

Why it exists: the user rejected captions over the speaker's head several
times, and two prose rules ("look at 2-3 frames", "move it in the editor")
did not stop it - 2-3 frames chosen by text length never hit the shots where
the head sits low (the 1.0x shot), and photos/close-ups were never looked at.
This script is the rule now; it runs inside render_from_plan.py before the burn.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
SWIFT = HERE / "vision_look.swift"
BIN = Path.home() / ".cache" / "claude-skills" / "vision_look"
FFMPEG_FULL = next((p for p in ("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", "/usr/local/opt/ffmpeg-full/bin/ffmpeg") if os.path.exists(p)), "ffmpeg")  # keg-only, has libass


def ts(x):
    h, m, s = x.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def fmt(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def vision_bin():
    if not BIN.exists() or BIN.stat().st_mtime < SWIFT.stat().st_mtime:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", str(SWIFT), "-o", str(BIN)], check=True)
    return str(BIN)


def parse_ass(path):
    W, H, styles, events = 1080, 1920, {}, []
    sfmt = efmt = None
    for n, line in enumerate(open(path, encoding="utf-8").read().split("\n")):
        if line.startswith("PlayResX:"):
            W = int(line.split(":")[1])
        elif line.startswith("PlayResY:"):
            H = int(line.split(":")[1])
        elif line.startswith("Format:") and sfmt is None:
            sfmt = [x.strip() for x in line[7:].split(",")]
        elif line.startswith("Format:"):
            efmt = [x.strip() for x in line[7:].split(",")]
        elif line.startswith("Style:"):
            d = dict(zip(sfmt, [x.strip() for x in line[6:].split(",")]))
            styles[d["Name"]] = (int(d["Alignment"]), int(d["MarginV"]))
        elif line.startswith("Dialogue:"):
            p = line.split(",", 9)
            events.append({"line": n, "start": ts(p[1]), "end": ts(p[2]), "style": p[3],
                           "mv": int(p[7] or 0), "text": p[9]})
    return W, H, styles, events


def card_boxes(ass_path, events, W, H, ffmpeg):
    """Render every card alone (one frame each, animation tags removed) and measure it."""
    lines = open(ass_path, encoding="utf-8").read().split("\n")
    head = [l for l in lines if not l.startswith("Dialogue:")]
    body = []
    for i, e in enumerate(events):
        p = lines[e["line"]].split(",", 9)
        p[1], p[2] = fmt(i * 0.04 + 0.001), fmt(i * 0.04 + 0.039)
        p[9] = re.sub(r"\\(k[fo]?\d+|K\d+|fade?\([^)]*\)|t\([^)]*\))", "", p[9])
        body.append(",".join(p))
    tmp = tempfile.NamedTemporaryFile("w", suffix=".ass", delete=False, encoding="utf-8")
    tmp.write("\n".join(head + body) + "\n")
    tmp.close()
    raw = subprocess.run([ffmpeg, "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i",
                          f"color=c=0x808080:s={W}x{H}:d={len(events) * 0.04 + 0.04:.3f}:r=25",
                          "-vf", f"subtitles={tmp.name}:fontsdir={os.path.expanduser('~/Library/Fonts')}",
                          "-frames:v", str(len(events)), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    os.unlink(tmp.name)
    frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W)
    boxes = []
    for f in frames:
        ys, xs = np.where(np.abs(f.astype(int) - 128) > 20)
        boxes.append(None if not len(xs) else (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))
    return boxes


def obstacles(video, events, step, hands, W, H, ffmpeg):
    """{event index: [(x0, y0, x1, y1, kind, t)]} in PlayRes pixels."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=avg_frame_rate,width,height", "-of", "json", video],
                       capture_output=True, text=True, check=True)
    st = json.loads(r.stdout)["streams"][0]
    num, den = st["avg_frame_rate"].split("/")
    fps = float(num) / float(den)
    sx, sy = W / st["width"], H / st["height"]
    want = {}
    for i, e in enumerate(events):
        a, b = e["start"] + 0.04, max(e["start"] + 0.05, e["end"] - 0.04)
        k = max(3, int((b - a) / step) + 1)
        for t in np.linspace(a, b, k):
            want.setdefault(int(round(t * fps)), set()).add(i)
    idx = sorted(want)
    d = tempfile.mkdtemp(prefix="capov_")
    w2, h2 = st["width"] // 2, st["height"] // 2
    dec = subprocess.Popen([ffmpeg, "-nostdin", "-loglevel", "error", "-i", video, "-vf",
                            f"scale={w2}:{h2}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                           stdout=subprocess.PIPE)
    need, n = set(idx), 0
    while need:
        buf = dec.stdout.read(w2 * h2 * 3)
        if len(buf) < w2 * h2 * 3:
            break
        if n in need:
            cv2.imwrite(f"{d}/f{n:06d}.png", np.frombuffer(buf, np.uint8).reshape(h2, w2, 3))
            need.discard(n)
        n += 1
    dec.kill()
    idx = [n for n in idx if n not in need]
    files = sorted(Path(d).glob("f*.png"))
    out = subprocess.run([vision_bin()], input="\n".join(map(str, files)), capture_output=True,
                         text=True, check=True).stdout
    res = {i: [] for i in range(len(events))}
    found = {}
    for line in out.splitlines():
        a = line.split()
        found[a[0]] = a[1:]
    for n, f in zip(idx, files):
        a = found.get(str(f), [])
        items = [(a[j], *[int(v) * 2 for v in a[j + 1:j + 5]]) for j in range(0, len(a), 5)]
        faces = [it for it in items if it[0] == "F" and it[4] * sy >= 24]
        boxes = []
        for kind, x, y, w, h in items:
            if kind == "F" and h * sy >= 24:  # head: hair above, chin/beard below
                boxes.append((x - 0.1 * w, y - 0.45 * h, x + 1.1 * w, y + 1.12 * h, "face"))
            elif kind == "H" and (hands == "always" or (hands == "auto" and not faces)):
                boxes.append((x - 0.1 * w, y - 0.1 * h, x + 1.1 * w, y + 1.1 * h, "hand"))
        if not faces:
            # close-up / insert: a face cut by the frame edge (only mouth and beard
            # visible) is not detected, and it sits at the top - keep the top 30%
            # free (a card moved up to dodge the hands landed on the mouth)
            boxes.append((0, -1, st["width"], 0.30 * st["height"], "maybe face"))
        for i in want[n]:
            for x0, y0, x1, y1, kind in boxes:
                res[i].append((x0 * sx, y0 * sy, x1 * sx, y1 * sy, kind, n / fps))
    shutil.rmtree(d, ignore_errors=True)
    return res


def hits(box, obs, air):
    x0, y0, x1, y1 = box
    return [o for o in obs if x0 < o[2] + air and x1 > o[0] - air and y0 < o[3] + air and y1 > o[1] - air]


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("ass")
    ap.add_argument("video")
    ap.add_argument("--fix", help="write the .ass with every covering card moved")
    ap.add_argument("--pos-json", help="write the moves as POS_JSON {dialogue index: MarginV} for the plan-editor")
    ap.add_argument("--step", type=float, default=0.2)
    ap.add_argument("--air", type=int, default=24, help="px kept free around a head / hand")
    ap.add_argument("--hands", choices=["auto", "always", "never"], default="auto")
    ap.add_argument("--ffmpeg", default=FFMPEG_FULL)
    a = ap.parse_args()

    W, H, styles, events = parse_ass(a.ass)
    if not events:
        sys.exit("no Dialogue events")
    k, kh = W / 1080, H / 1920
    zy0, zy1 = 260 * kh, 1330 * kh
    rail_x, rail_y0, rail_y1 = 860 * k, 950 * kh, 1660 * kh
    boxes = card_boxes(a.ass, events, W, H, a.ffmpeg)
    obs = obstacles(a.video, events, a.step, a.hands, W, H, a.ffmpeg)

    lines = open(a.ass, encoding="utf-8").read().split("\n")

    def in_rail(b):
        return b[2] > rail_x and b[3] > rail_y0 and b[1] < rail_y1

    def free(i, ny, rail=True):
        """Card i with its top at ny: inside the safe zone, out of the rail, touching nothing.
        A card that already sat in the rail (the style's own choice) is not pushed out of it -
        that is check_safe_zone.py's business, and dodging it made cards jump above the head."""
        x0, y0, x1, y1 = boxes[i]
        rail = rail and not in_rail(boxes[i])
        nb = (x0, ny, x1, ny + y1 - y0)
        if nb[1] < zy0 or nb[3] > zy1:
            return False
        if rail and x1 > rail_x and nb[3] > rail_y0 and nb[1] < rail_y1:
            return False
        return not hits(nb, obs[i], a.air)

    def movable(i):
        e = events[i]
        return boxes[i] and "\\pos" not in e["text"] and "\\move" not in e["text"] \
            and styles.get(e["style"], (8, 0))[0] not in (4, 5, 6)

    bad = [i for i in range(len(events)) if boxes[i] and hits(boxes[i], obs[i], a.air)]
    for i in bad:
        e, (x0, y0, x1, y1), h = events[i], boxes[i], hits(boxes[i], obs[i], a.air)
        what = ", ".join(sorted({o[4] for o in h}))
        print(f"{e['start']:7.2f}s  {what:10s} caption y {y0}-{y1}, obstacle y {int(min(o[1] for o in h))}-"
              f"{int(max(o[3] for o in h))}  | {e['text'][:50]}")
    shift = {}   # event index -> new top y of its card
    left = 0
    if bad and (a.fix or a.pos_json):
        # 1. One common height per style first: captions should not jump between
        #    screens, so move the whole style if that alone clears (almost) every hit.
        for style in sorted({events[i]["style"] for i in bad}):
            grp = [i for i in range(len(events)) if events[i]["style"] == style and movable(i)]
            if len(grp) < 4:
                continue
            best = (sum(not free(i, boxes[i][1]) for i in grp), 0, 0)
            for d in range(-700, 701, 4):
                n = sum(not free(i, boxes[i][1] + d) for i in grp)
                if (n, abs(d)) < best[:2]:
                    best = (n, abs(d), d)
            best_d = best[2]
            if best_d:
                for i in grp:
                    shift[i] = boxes[i][1] + best_d
                print(f"-> all captions of style {style} moved by {best_d:+d}px ({best[0]} left to move one by one)")
        # 2. Then single cards that still touch something: nearest free height.
        for i in range(len(events)):
            if not boxes[i]:
                continue
            ny = shift.get(i, boxes[i][1])
            if (free(i, ny) if i in shift else not hits(boxes[i], obs[i], a.air)):
                continue
            e = events[i]
            if not movable(i):
                print(f"{e['start']:7.2f}s  CANNOT MOVE (\\pos/\\move or middle anchor) - fix by hand"); left += 1; continue
            cand = [y for y in range(int(zy0), int(zy1) + 1, 2) if free(i, y)]
            note = ""
            if not cand:  # a face weighs more than Instagram's button rail
                cand = [y for y in range(int(zy0), int(zy1) + 1, 2) if free(i, y, rail=False)]
                note = "  (the right end reaches the button zone - shorten the line if you can)"
            if not cand:
                print(f"{e['start']:7.2f}s  NO FREE HEIGHT in the safe zone - shorten the text or change the shot  | {e['text'][:50]}")
                left += 1; continue
            shift[i] = min(cand, key=lambda y: abs(y - ny))
            print(f"{e['start']:7.2f}s  moved alone to y {shift[i]}  | {e['text'][:50]}{note}")
    elif bad:
        left = len(bad)
    moves = {}
    for i, ny in shift.items():
        if ny == boxes[i][1]:
            continue
        e = events[i]
        align, smv = styles.get(e["style"], (8, 0))
        mv = e["mv"] or smv
        new = max(1, int(round(mv + (ny - boxes[i][1]) if align >= 7 else mv - (ny - boxes[i][1]))))
        moves[i] = new
        p = lines[e["line"]].split(",", 9)
        p[7] = str(new)
        lines[e["line"]] = ",".join(p)
    if a.fix:
        open(a.fix, "w", encoding="utf-8").write("\n".join(lines))
    if a.pos_json:
        json.dump({str(i): v for i, v in moves.items()}, open(a.pos_json, "w"))
    print(f"{len(events)} captions checked: {len(bad)} over the face/hand, {len(moves)} moved, {left} left for manual")
    sys.exit(1 if left else 0)


if __name__ == "__main__":
    main()
