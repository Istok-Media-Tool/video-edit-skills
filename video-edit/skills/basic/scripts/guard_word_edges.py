#!/usr/bin/env python3
"""
Make sure no cut lands inside a word - every kept word is spoken to its end.

Why: the silence-based edges (detect_bursts.py, tighten_cuts.py at -42 dB)
miss quiet word endings - a soft final "s", "t", "f", a trailing vowel the
speaker lets fade - so a cut can clip the end of a word. Checking the result
by transcribing it does NOT catch that: "kraj" for "kraja" is often still
recognised as the full word. This script checks every edge against real word
times instead.

Rule (the user's, 2026-11-10): a clip ends at least --tail-margin (0.06 s)
after its last word ends and starts at least --head-margin (0.04 s) before its
first word starts, counting the padding cut_and_concat.sh adds (--pre-pad /
--post-pad, the PRE_PAD / POST_PAD you will cut with).

For each edge inside a word (or too close to it) the edge is moved out to
the word boundary + margin, but never into the neighbouring word. Every move
is printed with the word - tell the user. The padding may not reach into
the neighbouring word either (a retake or a dropped word right after the
kept one): such an edge is pulled back. When both cannot hold (the next word
follows with no gap) the edge is reported as "TIGHT": listen to it, or pick
a different cut point.

Word times: --words (stt.py .json / word_times.py output of THIS source
file), or, without it, the audio is transcribed here with stt.py (ElevenLabs,
then Groq) - one request for the whole recording.

Usage:
  guard_word_edges.py audio.wav tight.txt safe.txt --language sr
      [--words words.json] [--pre-pad 0.04] [--post-pad 0.08]
Then cut safe.txt with the same PRE_PAD / POST_PAD.
"""
import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stt  # noqa: E402


def load_words(path):
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, dict):
        d = d["words"]
    out = []
    for w in d:
        if isinstance(w, dict):
            w = (w["word"], w["start"], w["end"])
        out.append((str(w[0]).strip(), float(w[1]), float(w[2])))
    return sorted(out, key=lambda w: w[1])


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("audio")
    ap.add_argument("selections")
    ap.add_argument("out")
    ap.add_argument("--words")
    ap.add_argument("--language", default="sr")
    ap.add_argument("--terms", default="")
    ap.add_argument("--pre-pad", type=float, default=0.04)
    ap.add_argument("--post-pad", type=float, default=0.08)
    ap.add_argument("--head-margin", type=float, default=0.04)
    ap.add_argument("--tail-margin", type=float, default=0.06)
    a = ap.parse_args()

    if a.words:
        W = load_words(a.words)
    else:
        with tempfile.TemporaryDirectory() as d:
            flac = os.path.join(d, "a.flac")
            stt.to_flac(a.audio, flac)
            engines = stt.available()
            if "groq" in engines and os.path.getsize(flac) > 24 * 1024 * 1024:
                engines.remove("groq")
            if not engines:
                sys.exit("no ElevenLabs/Groq key - pass --words (e.g. from local whisper word_timestamps)")
            r = stt.transcribe(flac, a.language, [t.strip() for t in a.terms.split(",") if t.strip()],
                               words=True, engines=engines)
            print(f"word times: {r['engine']}, {len(r['words'])} words", file=sys.stderr)
            W = [(w["word"], w["start"], w["end"]) for w in r["words"]]
            W.sort(key=lambda w: w[1])

    rows = []
    for line in open(a.selections, encoding="utf-8"):
        if line.strip():
            s, e, *vf = line.rstrip("\n").split("\t")
            rows.append([float(s), float(e), vf])

    moved = tight = 0
    for n, (s, e, vf) in enumerate(rows):
        # END. The kept last word = the last word that starts before the raw
        # end e; the clip (with padding) must run past its end + margin, but
        # must stop before the next word (a retake / dropped word) begins.
        kept = [k for k, w in enumerate(W) if w[1] < e - 0.02]
        if kept:
            k = kept[-1]
            word, ws, we = W[k]
            need = we + a.tail_margin - a.post_pad            # lowest allowed e
            stop = (W[k + 1][1] - 0.02 - a.post_pad) if k + 1 < len(W) else None   # highest allowed e
            new = max(e, need)
            if stop is not None and new > stop:
                new = max(stop, min(e, stop))
            if abs(new - e) > 0.005:
                why = f"'{word}' ends at {we:.2f}" if new > e else f"padding ran into '{W[k + 1][0]}'"
                print(f"clip {n + 1} end {e:.2f} -> {new:.2f}: {why}", file=sys.stderr)
                e = new
                moved += 1
            if e < need - 0.01:
                print(f"clip {n + 1} end TIGHT: '{word}' ({we:.2f}) is followed by '{W[k + 1][0]}' "
                      f"({W[k + 1][1]:.2f}) with no gap - listen", file=sys.stderr)
                tight += 1
        # START. The kept first word = the first word still sounding after the
        # raw start s; the clip must begin before it starts - margin, but after
        # the previous word has ended.
        kept = [k for k, w in enumerate(W) if w[2] > s + 0.02]
        if kept:
            k = kept[0]
            word, ws, we = W[k]
            need = ws - a.head_margin + a.pre_pad             # highest allowed s
            stop = (W[k - 1][2] + 0.02 + a.pre_pad) if k > 0 else None   # lowest allowed s
            new = min(s, need)
            if stop is not None and new < stop:
                new = min(stop, max(s, stop))
            if abs(new - s) > 0.005:
                why = f"'{word}' starts at {ws:.2f}" if new < s else f"padding ran into '{W[k - 1][0]}'"
                print(f"clip {n + 1} start {s:.2f} -> {new:.2f}: {why}", file=sys.stderr)
                s = new
                moved += 1
            if s > need + 0.01:
                print(f"clip {n + 1} start TIGHT: '{word}' ({ws:.2f}) follows '{W[k - 1][0]}' "
                      f"({W[k - 1][2]:.2f}) with no gap - listen", file=sys.stderr)
                tight += 1
        rows[n] = [s, e, vf]

    with open(a.out, "w", encoding="utf-8") as f:
        for s, e, vf in rows:
            f.write("\t".join([f"{s:.3f}", f"{e:.3f}", *vf]) + "\n")
    print(f"{len(rows)} clips, {moved} edges moved out of words, {tight} tight", file=sys.stderr)


if __name__ == "__main__":
    main()
