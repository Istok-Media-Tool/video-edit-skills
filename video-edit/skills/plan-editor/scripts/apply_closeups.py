#!/usr/bin/env python3
"""
Turn the CLOSEUPS_JSON the user sent from the editor's "Close-up" mode into
the closeups file the render overlays (name<TAB>start<TAB>end<TAB>offset),
plus an edges file for check_video.py --edges.

Times are on the editor media's timeline (the render without close-ups);
off already moved with the start, so the close-up's frames stay where they
were in time. Prints every changed edge so it can be read back to the user.

Usage:
  apply_closeups.py plan_reply.txt old_closeups.txt new_closeups.txt [edges.txt]
"""
import json
import re
import sys


def main():
    reply, old, new = sys.argv[1:4]
    m = re.search(r"^CLOSEUPS_JSON:\s*(.+)$", open(reply, encoding="utf-8").read(), re.M)
    if not m:
        sys.exit("reply has no CLOSEUPS_JSON - no close-up was moved")
    cus = json.loads(m.group(1))
    before = {l.split("\t")[0]: l.rstrip("\n").split("\t") for l in open(old, encoding="utf-8") if l.strip()}
    with open(new, "w", encoding="utf-8") as f:
        for c in cus:
            f.write(f"{c['name']}\t{c['start']:.2f}\t{c['end']:.2f}\t{c['off']:.2f}\n")
            b = before.get(c["name"])
            if b and (abs(float(b[1]) - c["start"]) > 0.005 or abs(float(b[2]) - c["end"]) > 0.005):
                print(f"{c['name']}: {float(b[1]):.2f}-{float(b[2]):.2f} -> {c['start']:.2f}-{c['end']:.2f}", file=sys.stderr)
    if len(sys.argv) > 4:
        with open(sys.argv[4], "w") as f:
            for c in cus:
                f.write(f"{c['start']:.2f}\n{c['end']:.2f}\n")


if __name__ == "__main__":
    main()
