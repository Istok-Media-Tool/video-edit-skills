#!/usr/bin/env python3
"""
Cut small preview clips of the close-ups (inserts that cover the whole frame
while a name is spoken, e.g. the tablet photo on a real reel), so the plan
editor's "Close-up" mode can show each one over the player while the user
slides its start and end.

The user asked for it: "da mogu da pomerim malo napred ili nazad početak i
kraj". The close-up content stays locked to the timeline - moving the start
earlier reveals what comes before in the close-up file, it does not restart
it - so each preview carries SLACK seconds on both sides.

Input: the closeups file the render uses, one per line
  name<TAB>start<TAB>end<TAB>offset
  (start/end on the editor media's timeline, offset = where in <srcdir>/<name>.MP4
  the close-up begins)

Writes <outdir>/cu<N>.mp4 and <outdir>/closeups.json:
  [{"name", "st", "en", "off", "file", "o", "min", "max"}]
  o = time inside the preview clip that plays at "st"; min / max = earliest
  start / latest end the source file allows.
Pass that json to make_plan_widget.py --closeups and the outdir to
serve_plan_editor.py --closeups-dir.

Usage:
  make_closeup_clips.py closeups.txt srcdir outdir [--pre-filter transpose=1] [--ext .MP4]
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from venc import venc
import argparse
import json
import subprocess
from pathlib import Path

SLACK = 1.5  # how far each edge can move, seconds


def dur(f):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(f)]).decode())


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("closeups")
    ap.add_argument("srcdir")
    ap.add_argument("outdir")
    ap.add_argument("--pre-filter", default="")
    ap.add_argument("--ext", default=".MP4")
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    vf = ",".join(f for f in (a.pre_filter, "scale=-2:960") if f)
    res = []
    for k, line in enumerate(l for l in open(a.closeups, encoding="utf-8") if l.strip()):
        name, st, en, off = line.rstrip("\n").split("\t")[:4]
        st, en, off = float(st), float(en), float(off)
        src = Path(a.srcdir) / (name + a.ext)
        total = dur(src)
        s0 = max(0.0, off - SLACK)
        s1 = min(total, off + (en - st) + SLACK)
        f = f"cu{k + 1}.mp4"
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-ss", f"{s0:.3f}", "-to", f"{s1:.3f}", "-i", str(src), "-vf", vf,
                        "-an", *venc(26, "fast"), "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", str(out / f), "-loglevel", "error"], check=True, stdin=subprocess.DEVNULL)
        res.append({"name": name, "st": st, "en": en, "off": off, "file": f, "o": round(off - s0, 3),
                    "min": round(st - (off - s0), 3), "max": round(st + (s1 - off), 3)})
    (out / "closeups.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out / "closeups.json")


if __name__ == "__main__":
    main()
