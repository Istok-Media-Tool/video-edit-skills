#!/usr/bin/env python3
r"""
Apply per-caption vertical positions from the plan editor ("Pozicija titla"
mode, POS_JSON) to an ASS file.

The user moves single caption screens up or down so they never cover the
face at that moment. POS_JSON maps the Dialogue line's 0-based index to the
y of the caption's first line in PlayRes pixels (the style is top-anchored,
Alignment 8, so this is the event's own MarginV); 0 = back to the style's
default.

Usage:
  apply_caption_positions.py captions.ass pos.json out.ass
"""
import json
import sys


def main():
    src, pos_path, out = sys.argv[1:4]
    pos = {int(k): int(v) for k, v in json.load(open(pos_path, encoding="utf-8")).items()}
    lines = open(src, encoding="utf-8").read().split("\n")
    idx = 0
    for n, line in enumerate(lines):
        if not line.startswith("Dialogue:"):
            continue
        if idx in pos:
            parts = line.split(",", 9)
            parts[7] = str(pos[idx])  # MarginV of this event
            lines[n] = ",".join(parts)
        idx += 1
    missing = [k for k in pos if k >= idx]
    if missing:
        sys.exit(f"no Dialogue line with index {missing} (file has {idx})")
    open(out, "w", encoding="utf-8").write("\n".join(lines))
    print(f"{len(pos)} caption position(s) applied -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
