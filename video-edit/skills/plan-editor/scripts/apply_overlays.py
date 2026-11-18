#!/usr/bin/env python3
r"""
Picture pass for the "educational reel" look (recipe: STYLE_educational.md):
slow animated push-ins, inserts from a second camera (synced or from any other
moment), still images with a Ken Burns move, and a quiet end shot - over the
already cut + zoomed video, BEFORE captions.

Built from the "avocado hass" test (2026-11-18), where none of this existed in
the skills and a one-off renderer had to be written: the hard 1.45x punch-ins
come from build_zoom_selections.py, everything that MOVES or comes from
another file comes from here.

overlays.json (times in seconds on THIS video's timeline, or by phrase):
{
 "push":   [{"phrase": "rudolph hass earned", "until": "the modern avocado", "z0": 1.0, "z1": 1.45}],
 "second_camera": {"C0025": {"file": "/…/C0045.MP4", "offset": -2.263},     (sync_cameras.py)
                   "C0026": {"file": "/…/C0046.MP4", "offset": 2.25}},
 "insert": [{"phrase": "it says hass", "file": "/…/C0045.MP4", "in": 110.52, "z0": 1.3, "z1": 1.3},
            {"phrase": "i cut here", "sync": true}],
 "image":  [{"phrase": "that's rudolph hass", "until": "exactly a hundred years ago",
             "file": "/…/Rudolph Hass.png", "z0": 1.0, "z1": 1.1}],
 "tail":   {"file": "/…/C0046.MP4", "in": 922.92, "dur": 3.6, "z": 1.15}
}
- every item: "from"/"to" in seconds, OR "phrase" (+ optional "until"):
  starts 0.08 s before the first word, ends 0.10 s after the last one
  (word times from --words, same matching as the zoom placement);
- "in" = where in the source the insert starts; "sync": true instead =
  the SAME moment from the second camera: for each clip of the cut, its main
  source's "second_camera" entry gives the file and offset (second = main +
  offset). Needs --cuts and --durations; a synced range that spans a cut is
  split there, so lip sync holds across it;
- "transpose": true by default (sideways footage); "z0"/"z1" zoom the
  insert/image linearly over its range (Ken Burns ~2.5 %/s reads calm);
- "push": the speaker is kept with the head top 9 % below the frame top,
  measured on the frames of that range (Apple Vision); a push range must not
  span a hard zoom change - it warns.
Edges within 0.24 s of a cut snap onto the cut (no 1-6 frame slivers), all
edges land on the frame grid.

Usage:
  apply_overlays.py video.mp4 overlays.json out.mp4 --words words.json
                    [--cuts cuts.tsv --durations durs.txt]   (needed for "sync")
  cuts.tsv: source<TAB>start<TAB>... per clip, start = where the clip REALLY begins in the
  source (with any padding); durs.txt: one real clip duration per line (or a comma list) -
  the cumulative unpadded end-start drifts by the padding and picks the wrong clip.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from venc import venc  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "zoom", "scripts"))
from build_zoom_selections import norm  # noqa: E402

VISION_SWIFT = Path(__file__).resolve().parents[2] / "subtitle" / "scripts" / "vision_look.swift"
VISION_BIN = Path.home() / ".cache/claude-skills/vision_look"


def probe(path):
    st = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                             "stream=width,height,avg_frame_rate,nb_frames", "-of", "json", path]))
    s = st["streams"][0]
    n, d = s["avg_frame_rate"].split("/")
    return s["width"], s["height"], float(n) / float(d)


def load_words(path):
    w = json.load(open(path, encoding="utf-8"))
    w = w.get("words", w) if isinstance(w, dict) else w
    out = []
    for x in w:
        if isinstance(x, dict):
            t = x.get("word", x.get("text", ""))
            out.append((norm(t), float(x["start"]), float(x["end"])))
        else:
            out.append((norm(x[0]), float(x[1]), float(x[2])))
    return [x for x in out if x[0]]


def find_phrase(words, phrase, after=0.0):
    p = [norm(t) for t in phrase.split() if norm(t)]
    for i in range(len(words) - len(p) + 1):
        if words[i][1] >= after - 0.01 and all(words[i + k][0] == p[k] for k in range(len(p))):
            return words[i][1], words[i + len(p) - 1][2]
    sys.exit(f"phrase not in the speech: '{phrase}' - write it as the transcript has it (numbers spelled out?)")


def vision():
    if not VISION_BIN.exists() or VISION_BIN.stat().st_mtime < VISION_SWIFT.stat().st_mtime:
        VISION_BIN.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", str(VISION_SWIFT), "-o", str(VISION_BIN)], check=True)
    return str(VISION_BIN)


def frames_of(path, t0, dur, transpose, W, H, fps):
    """Exact frames from t0 on (seek a bit earlier, then select - avoids a doubled first frame)."""
    pre = min(1.0, t0)
    n = int(round(dur * fps)) + 3
    vf = f"select=gte(t\\,{pre - 0.02:.3f})," + ("transpose=1," if transpose else "") + \
         f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=bgr24"
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t0 - pre:.3f}", "-i", path, "-vf", vf,
                          "-fps_mode", "passthrough", "-frames:v", str(n), "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)


def zoom_img(img, z, cx, cy, W, H):
    if z <= 1.0001:
        return img
    w, h = W / z, H / z
    x = min(max(cx - w / 2, 0), W - w)
    y = min(max(cy - h / 2, 0), H - h)
    M = np.float32([[z, 0, -x * z], [0, z, -y * z]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LANCZOS4)


def lerp(a, b, u):
    return a + (b - a) * min(max(u, 0.0), 1.0)


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("video")
    ap.add_argument("overlays")
    ap.add_argument("out")
    ap.add_argument("--words", required=True)
    ap.add_argument("--cuts", help="source<TAB>start<TAB>... per clip of the cut (for synced inserts)")
    ap.add_argument("--durations", help="real clip durations: file (one per line) or comma list")
    ap.add_argument("--snap", type=float, default=0.24)
    a = ap.parse_args()

    W, H, fps = probe(a.video)
    words = load_words(a.words)
    O = json.load(open(a.overlays, encoding="utf-8"))
    clips = []
    if a.cuts:
        rows = [l.rstrip("\n").split("\t") for l in open(a.cuts, encoding="utf-8") if l.strip()]
        rows = [r for r in rows if len(r) >= 3 and r[1].replace(".", "", 1).isdigit()]
        if a.durations:
            txt = open(a.durations).read() if os.path.isfile(a.durations) else a.durations
            durs = [float(x) for x in txt.replace(",", "\n").split() if x.strip()]
            if len(durs) != len(rows):
                sys.exit(f"{len(rows)} clips in --cuts but {len(durs)} durations")
        else:
            durs = [float(r[2]) - float(r[1]) for r in rows]
            print("warning: no --durations - clip starts from end-start, may drift", file=sys.stderr)
        t = 0.0
        for r, d in zip(rows, durs):
            clips.append((round(t, 4), float(r[1]), Path(r[0]).stem))
            t += d
    joins = [c[0] for c in clips[1:]]
    total = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                           "-of", "csv=p=0", a.video]).decode())
    snaps = joins + [round(total * fps) / fps]   # the video's end too: no sliver before the tail

    def place(it):
        if "phrase" in it:
            s, e = find_phrase(words, it["phrase"])
            if it.get("until"):
                e = find_phrase(words, it["until"], after=s)[1]
            s, e = s - 0.08, e + 0.10
        else:
            s, e = float(it["from"]), float(it["to"])
        for j in snaps:  # an edge a few frames from a cut lands on the cut
            if abs(s - j) < a.snap:
                if "in" in it:
                    it["in"] += j - s
                s = j
            if abs(e - j) < a.snap:
                e = j
        it["from"], it["to"] = round(s * fps) / fps, round(e * fps) / fps
        return it

    over = []
    for kind in ("insert", "image"):
        for it in O.get(kind, []):
            it = place(dict(it, kind=kind))
            if kind == "insert" and it.get("sync"):
                if not clips:
                    sys.exit("synced insert needs --cuts and --durations")
                # split at every cut inside the range: each piece follows its own clip's source time,
                # so the second camera stays in lip sync across the cut
                edges = [it["from"]] + [j for j in joins if it["from"] + 1e-6 < j < it["to"] - 1e-6] + [it["to"]]
                for s, e in zip(edges, edges[1:]):
                    c = max((c for c in clips if c[0] <= s + 0.01), key=lambda c: c[0])
                    cam = O.get("second_camera", {}).get(c[2])
                    if not cam:
                        sys.exit(f"no second_camera entry for main source '{c[2]}' (needed at {s:.2f}s)")
                    p = dict(it, **{"from": s, "to": e, "file": cam["file"]})
                    p["in"] = c[1] + (s - c[0]) + float(cam["offset"])
                    if len(edges) > 2:  # a zoom moving over the whole range keeps moving across pieces
                        z0, z1 = it.get("z0", 1.0), it.get("z1", it.get("z0", 1.0))
                        u0 = (s - it["from"]) / (it["to"] - it["from"])
                        u1 = (e - it["from"]) / (it["to"] - it["from"])
                        p["z0"], p["z1"] = lerp(z0, z1, u0), lerp(z0, z1, u1)
                    over.append(p)
                continue
            over.append(it)
    over.sort(key=lambda o: o["from"])
    for p, q in zip(over, over[1:]):
        if q["from"] < p["to"] - 1e-6:
            sys.exit(f"overlays overlap: {p['from']:.2f}-{p['to']:.2f} and {q['from']:.2f}-{q['to']:.2f}")
    pushes = [place(dict(it)) for it in O.get("push", [])]

    # head anchor for every push: median face over 5 frames of the range
    tmp = Path(a.out).with_suffix(".faces")
    tmp.mkdir(exist_ok=True)
    for k, pz in enumerate(pushes):
        imgs = []
        for m, t in enumerate(np.linspace(pz["from"] + 0.05, pz["to"] - 0.05, 5)):
            f = tmp / f"p{k:02d}_{m}.png"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", a.video,
                            "-frames:v", "1", str(f)], check=True)
            imgs.append(str(f))
        xs, tops = [], []
        for line in subprocess.run([vision()] + imgs, capture_output=True, text=True).stdout.splitlines():
            p = line.split()
            fs = [p[j + 1:j + 5] for j in range(1, len(p), 5) if p[j] == "F"]
            if fs:
                x, y, w, h = map(int, max(fs, key=lambda b: int(b[3])))
                xs.append(x + w / 2)
                tops.append(y - 0.5 * h)
        pz["cx"] = float(np.median(xs)) if xs else W / 2
        pz["top"] = float(np.median(tops)) if tops else H * 0.12
        if not xs:
            print(f"warning: no face in push {pz['from']:.2f}-{pz['to']:.2f}s, zooming on the centre", file=sys.stderr)
        for j in joins:
            if pz["from"] + 0.1 < j < pz["to"] - 0.1:
                print(f"note: push {pz['from']:.2f}-{pz['to']:.2f}s runs over a jump cut at {j:.2f}s "
                      f"(fine for one sentence; not over a hard zoom change)", file=sys.stderr)
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()

    for o in over:
        d = o["to"] - o["from"]
        if o["kind"] == "insert":
            o["fr"] = frames_of(o["file"], float(o["in"]), d, o.get("transpose", True), W, H, fps)
        else:
            im = cv2.imread(o["file"])
            if im is None:
                sys.exit(f"cannot read image {o['file']}")
            ih, iw = im.shape[:2]
            s = max(W / iw, H / ih)
            im = cv2.resize(im, (int(iw * s + .5), int(ih * s + .5)), interpolation=cv2.INTER_LANCZOS4)
            y0, x0 = (im.shape[0] - H) // 2, (im.shape[1] - W) // 2
            o["img"] = im[y0:y0 + H, x0:x0 + W]
    tail = O.get("tail")
    NT = 0
    if tail:
        NT = int(round(tail["dur"] * fps))
        tail["fr"] = frames_of(tail["file"], float(tail["in"]), tail["dur"], tail.get("transpose", True), W, H, fps)

    dec = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", a.video, "-f", "rawvideo",
                            "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                            "-s", f"{W}x{H}", "-r", f"{fps:g}", "-i", "-", "-i", a.video,
                            "-filter_complex", f"[1:a]apad=pad_dur={NT / fps:.3f}[a]", "-map", "0:v", "-map", "[a]",
                            *venc(14), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-shortest", a.out],
                           stdin=subprocess.PIPE)
    n = 0
    fsz = W * H * 3
    while True:
        buf = dec.stdout.read(fsz)
        if len(buf) < fsz:
            break
        f = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        t = n / fps
        o = next((o for o in over if o["from"] <= t + 1e-6 < o["to"]), None)
        if o:
            u = (t - o["from"]) / max(o["to"] - o["from"], 1e-6)
            z = lerp(o.get("z0", 1.0), o.get("z1", o.get("z0", 1.0)), u)
            src = o["fr"][min(int(round((t - o["from"]) * fps)), len(o["fr"]) - 1)] if o["kind"] == "insert" else o["img"]
            f = zoom_img(src, z, W / 2, H / 2, W, H)
        else:
            pz = next((p for p in pushes if p["from"] <= t + 1e-6 < p["to"]), None)
            if pz:
                u = (t - pz["from"]) / max(pz["to"] - pz["from"], 1e-6)
                z = lerp(pz.get("z0", 1.0), pz.get("z1", 1.45), u)
                h = H / z
                f = zoom_img(f, z, pz["cx"], pz["top"] - 0.09 * h + h / 2, W, H)
        enc.stdin.write(np.ascontiguousarray(f).tobytes())
        n += 1
    for k in range(NT):
        fr = tail["fr"][min(k, len(tail["fr"]) - 1)]
        enc.stdin.write(np.ascontiguousarray(zoom_img(fr, tail.get("z", 1.0), W / 2, H / 2, W, H)).tobytes())
    enc.stdin.close()
    enc.wait()
    dec.wait()
    for o in over:
        print(f"{o['kind']:6s} {o['from']:7.2f}-{o['to']:7.2f}s  {Path(o['file']).name}"
              + (f" @ {float(o['in']):.2f}s" if o["kind"] == "insert" else ""), file=sys.stderr)
    for p in pushes:
        print(f"push   {p['from']:7.2f}-{p['to']:7.2f}s  {p.get('z0', 1.0)}->{p.get('z1', 1.45)}x", file=sys.stderr)
    print(f"-> {a.out} ({n} frames + tail {NT})", file=sys.stderr)


if __name__ == "__main__":
    main()
