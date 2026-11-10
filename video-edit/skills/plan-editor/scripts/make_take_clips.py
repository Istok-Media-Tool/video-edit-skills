#!/usr/bin/env python3
"""
Cut short preview clips of alternative takes, so the plan editor can show
them side by side (left / right) and the user picks the better one.

The basic skill finds sentences recorded more than once. Instead of picking
silently or describing the takes in chat, list them here; the editor's
"Dublovi" mode then plays each take next to the other.

Input JSON (clip index = 0-based position in the cut, same as sentences.txt):
  {"7": {"current": 1,
         "takes": [{"label": "Dubl 1", "start": 60.43, "end": 63.88,
                    "text": "i ovde vidimo pune, izražajne obrve"},
                   {"label": "Dubl 2", "start": 74.2, "end": 77.5,
                    "text": "I ovde vidimo ovako ovaj pune obrve izražajne"}]}}
  current = index of the take that is in the cut now
  start/end = unpadded source times (same as cuts.txt)

Writes <outdir>/clip<N>_take<K>.mp4 (small, rotated with --pre-filter) and
<outdir>/takes.json with a "file" name per take - pass that json to
make_plan_widget.py --takes and the outdir to serve_plan_editor.py --takes-dir.

Usage:
  make_take_clips.py source.mp4 takes_src.json outdir [--pre-filter transpose=1]
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from venc import venc
import argparse
import json
import subprocess
from pathlib import Path

PRE, POST = 0.15, 0.35  # same padding as cut_and_concat.sh, so the take sounds like it will in the cut


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("source")
    ap.add_argument("takes")
    ap.add_argument("outdir")
    ap.add_argument("--pre-filter", default="")
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    data = json.load(open(a.takes, encoding="utf-8"))
    vf = ",".join(f for f in (a.pre_filter, "scale=-2:960") if f)
    for clip, entry in data.items():
        for k, t in enumerate(entry["takes"]):
            name = f"clip{int(clip) + 1}_take{k + 1}.mp4"
            s = max(0.0, t["start"] - PRE)
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-ss", f"{s:.3f}", "-to", f"{t['end'] + POST:.3f}",
                            "-i", a.source, "-vf", vf, *venc(24, "fast"),
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                            str(out / name), "-loglevel", "error"], check=True, stdin=subprocess.DEVNULL)
            t["file"] = name
    (out / "takes.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out / "takes.json")


if __name__ == "__main__":
    main()
