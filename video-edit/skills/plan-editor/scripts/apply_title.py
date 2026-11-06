#!/usr/bin/env python3
"""
Put the title the user set in the plan editor's "Naslov" mode into the
captions file, so it is burned together with the captions.

TITLE_JSON (from the reply): {"text": "MODA NEKAD I SAD", "from": [clip, word],
"to": [clip, word]} - word = index in that clip's sentence (SENTENCES_JSON), or
{"text": ""} to remove the title. Text lines are split by "\n".

Every non-Default Dialogue is the title and is replaced (or removed). The
title runs from 0.08s before the from-word to 0.10s after the to-word
(the start of the video when the from-word is the very first word). A title
style ("Naslov": Inter Bold 92, black box, top-anchored at y=230) is added
when the file has none.

Usage:
  apply_title.py captions.ass title.json sentences.txt words.json durations out.ass
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_broll import find_span, norm  # noqa: E402

STYLE = ("Style: Naslov,Inter,92,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,"
         "3,22,0,8,100,100,230,1")


def s2t(x):
    x = max(0.0, x)
    return f"{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}"


def word_time(i, j, sentences, words, starts, end=False):
    cs, ce = starts[i], starts[i + 1]
    spoken = [(norm(w), s - cs, e - cs) for w, s, e in words if cs - 0.05 <= s < ce]
    s, e, _ = find_span(sentences[i].split(" "), j, spoken)
    if s is None:
        sys.exit(f"title word {j + 1} of clip {i + 1} ({sentences[i].split(' ')[j]!r}) not found in the speech")
    return cs + (e if end else s)


def main():
    ass, title_p, sent_p, words_p, durs, out = sys.argv[1:7]
    title = json.load(open(title_p, encoding="utf-8"))
    sentences = [l.strip() for l in open(sent_p, encoding="utf-8") if l.strip()]
    words = json.load(open(words_p, encoding="utf-8"))
    starts = [0.0]
    for d in durs.split(","):
        starts.append(starts[-1] + float(d))
    lines = open(ass, encoding="utf-8").read().split("\n")
    styles = [l.split(",")[0][6:].strip() for l in lines if l.startswith("Style:")]
    name = next((n for n in styles if n != "Default"), None)
    # drop the old title; the indices of the remaining captions shift, so
    # apply CAPTIONS_JSON / POS_JSON BEFORE this script
    lines = [l for l in lines if not (l.startswith("Dialogue:") and l.split(",", 9)[3] != "Default")]
    if title.get("text", "").strip():
        if name is None:
            name = "Naslov"
            k = max(n for n, l in enumerate(lines) if l.startswith("Style:"))
            lines.insert(k + 1, STYLE)
        (fi, fj), (ti, tj) = title["from"], title["to"]
        a = 0.0 if (fi, fj) == (0, 0) else word_time(fi, fj, sentences, words, starts) - 0.08
        b = min(word_time(ti, tj, sentences, words, starts, end=True) + 0.10, starts[ti + 1])  # never past its clip
        text = "\\N".join(l.strip() for l in title["text"].split("\n") if l.strip())
        k = next(n for n, l in enumerate(lines) if l.startswith("Format:") and n > lines.index("[Events]"))
        lines.insert(k + 1, f"Dialogue: 1,{s2t(a)},{s2t(b)},{name},,0,0,0,,{text}")
        print(f"title {a:.2f}s -> {b:.2f}s: {title['text']!r}", file=sys.stderr)
    else:
        print("title removed", file=sys.stderr)
    open(out, "w", encoding="utf-8").write("\n".join(lines))


if __name__ == "__main__":
    main()
