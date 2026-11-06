#!/usr/bin/env python3
r"""
Apply caption text fixes from the zoom-plan widget to an ASS file.

The widget (plan-editor skill, assets/plan_editor_widget.html) shows every caption
screen as an editable field; when the user corrects a wrong word it sends
back "CAPTIONS_JSON: {"<dialogue index>": "line 1\nline 2", ...}" - only the
screens that changed, keyed by the 0-based index of the Dialogue line in the
ASS file, with each newline being a line break on screen.

Only the Text field changes - timing and style stay as they were. Newlines
become explicit \N breaks, since the subtitle skill's style uses
WrapStyle: 2 (no auto-wrap), so the user's line breaks are kept exactly.
After applying, re-run the subtitle skill's test-frame check on the edited
screens (a longer word can push a line past the side margins) before
re-burning.

Usage:
  apply_caption_edits.py captions.ass edits.json captions_fixed.ass
"""
import json
import sys


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    src, edits_path, dst = sys.argv[1:]
    edits = {int(k): v for k, v in json.load(open(edits_path, encoding="utf-8")).items()}
    out, idx, applied = [], 0, []
    for line in open(src, encoding="utf-8"):
        if line.startswith("Dialogue:"):
            if idx in edits:
                parts = line.rstrip("\n").split(",", 9)
                new = "\\N".join(l.strip() for l in edits[idx].strip().split("\n") if l.strip())
                applied.append(f"#{idx + 1}: {parts[9]}  ->  {new}")
                parts[9] = new
                line = ",".join(parts) + "\n"
            idx += 1
        out.append(line)
    missing = sorted(set(edits) - set(range(idx)))
    if missing:
        sys.exit(f"no Dialogue line with index {missing} (file has {idx})")
    open(dst, "w", encoding="utf-8").write("".join(out))
    print("\n".join(applied) or "no changes")


if __name__ == "__main__":
    main()
