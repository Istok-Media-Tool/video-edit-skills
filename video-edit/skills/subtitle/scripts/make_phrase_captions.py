#!/usr/bin/env python3
"""
Phrase-card captions in the style of the user's two hand-edited reference
reels (Mouse Paradise, Johanna / Van Gogh - analysed 2026-11-10).

What those reels do, and this script reproduces:
- HOOK: the whole first sentence on one big card (bold white on a solid
  black box, 3-4 short lines), held for the entire sentence.
- BODY: one spoken phrase per card (3-8 words, 1-2 lines, <= 32 characters
  a line), white medium-weight text on a ~85% black box, top-anchored in the
  middle of the frame (first line at y = 47%), changing with the speech.
  A card that stops mid-sentence ends with "…" so the eye expects more.
- EMPHASIS: the video's ONE key term (--emphasis "social interaction
  overload") as a huge condensed display font with no box, revealed letter
  by letter in time with the words being spoken.
- CENSOR: words Instagram punishes are shown with "=" for the first vowel
  (--censor "sex,seks" -> "s=x", "s=ks").
- 0.12 s empty moment between consecutive cards (subtitle skill, lesson 5).

The body style is named "Default" and the hook "Hook", so the plan-editor
treats the body as captions (move up/down, fix text) and the hook card as
the title (Naslov mode).

Input: word times from word_times.py ([[word, start, end], ...]) or stt.py's
.json ({"words": [{"word", "start", "end"}, ...]}), in the FINAL video's
timeline.

Usage:
  make_phrase_captions.py words.json out.ass [--emphasis "key term"]
      [--censor "sex,seks"] [--no-hook] [--no-ellipsis] [--size 1080x1920]
      [--body-y 0.47] [--emphasis-font Impact]
"""
import argparse
import json
import re

GAP = 0.12           # empty moment between cards
MAX_WORDS = 8
MIN_WORDS = 3
LINE_CHARS = 32
HOOK_LINE_CHARS = 24
PAUSE = 0.18         # a gap this long between words ends a phrase
# a line should not end on one of these (they belong with the next word)
GLUE = set("a i u o na za od do sa iz po pri kroz da je se ne ni ili ali kao što koji koja koje "
           "the a an of to in on at for and or but with by from that this his her their my your its our".split())
SENT_END = re.compile(r"[.?!…]+[\"”’)]*$")


def t(s):
    s = max(0.0, s)
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def load_words(path):
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, dict):
        d = d["words"]
    out = []
    for w in d:
        if isinstance(w, dict):
            w = (w["word"], w["start"], w["end"])
        word = str(w[0]).strip()
        if word:
            out.append([word, float(w[1]), float(w[2])])
    return out


def censor(word, bad):
    core = re.sub(r"\W", "", word).lower()
    if core in bad:
        return re.sub(r"[aeiouAEIOU]", "=", word, count=1)
    return word


def split_lines(words, limit, two=True):
    """Break a card into lines at the most natural point: after punctuation,
    never after a glue word, as balanced as possible."""
    text = " ".join(words)
    if len(text) <= limit or len(words) < 2:
        return [text]
    best = None
    for k in range(1, len(words) if two else 1):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        if len(a) > limit + 4 or len(b) > limit + 4:
            continue
        score = abs(len(a) - len(b))
        if re.search(r"[,;:]$", words[k - 1]):
            score -= 12
        if re.sub(r"\W", "", words[k - 1]).lower() in GLUE:
            score += 25
        if k > 1 and words[k - 1][:1].isupper() and words[k][:1].isupper():
            score += 25   # keep names together
        if best is None or score < best[0]:
            best = (score, [a, b])
    if best:
        return best[1]
    # three lines (hook cards): greedy, then the same glue rule on each break
    lines, cur = [], []
    for w in words:
        if cur and len(" ".join(cur + [w])) > limit:
            name = cur[-1][:1].isupper() and w[:1].isupper() and len(cur) > 1   # "Van | Gogh"
            if (re.sub(r"\W", "", cur[-1]).lower() in GLUE or name) and len(cur) > 1:
                lines.append(" ".join(cur[:-1]))
                cur = [cur[-1]]
            else:
                lines.append(" ".join(cur))
                cur = []
        cur.append(w)
    lines.append(" ".join(cur))
    return lines


def phrases(words, start):
    """Group words[start:] into phrase cards."""
    core = lambda w: re.sub(r"\W", "", w).lower()
    cards, cur = [], []
    for i in range(start, len(words)):
        w = words[i]
        cur.append(i)
        nxt = words[i + 1] if i + 1 < len(words) else None
        n = len(cur)
        chars = len(" ".join(words[j][0] for j in cur))
        forced = n >= MAX_WORDS or chars >= 2 * LINE_CHARS - 6
        end_here = (
            nxt is None
            or SENT_END.search(w[0])
            or forced
            or (n >= MIN_WORDS and (re.search(r"[,;:]$", w[0]) or nxt[1] - w[2] >= PAUSE))
        )
        # never leave the next card with 1-2 words before a sentence end:
        # finish the sentence on this card if it still fits two lines
        if end_here and nxt is not None and not SENT_END.search(w[0]) and n >= MIN_WORDS:
            rest = []
            for j in range(i + 1, len(words)):
                rest.append(words[j][0])
                if SENT_END.search(words[j][0]):
                    break
            if (len(rest) <= 2 and SENT_END.search(rest[-1]) and n + len(rest) <= MAX_WORDS + 2
                    and chars + len(" ".join(rest)) < 2 * LINE_CHARS - 2):
                end_here = False
        if end_here:
            carry = []
            # a card cut by length must not end on "his" / "the" / "na": move those to the next card
            if forced and nxt is not None and not re.search(r"[,;:.?!…]$", w[0]):
                while len(cur) > MIN_WORDS and core(words[cur[-1]][0]) in GLUE:
                    carry.insert(0, cur.pop())
            cards.append(cur)
            cur = carry
    if cur:
        cards.append(cur)
    return cards


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("words")
    ap.add_argument("out")
    ap.add_argument("--emphasis", default="", help="the one key term, shown big with a letter reveal")
    ap.add_argument("--censor", default="", help="comma list of words shown with = for the first vowel")
    ap.add_argument("--no-hook", action="store_true")
    ap.add_argument("--no-ellipsis", action="store_true")
    ap.add_argument("--size", default="1080x1920")
    # Instagram safe zone (basic skill): everything inside x 120-960, y 260-1330
    # and out of the button rail (x > 860, y 950-1660) on 1080x1920. The
    # references put captions at ~47-55%, but there 2 lines would reach the
    # rail - so the body starts at 40% and the hook at 28%.
    ap.add_argument("--body-y", type=float, default=0.40, help="first caption line, fraction of height")
    ap.add_argument("--hook-y", type=float, default=0.28)
    ap.add_argument("--emphasis-font", default="Impact")
    a = ap.parse_args()

    W, H = (int(x) for x in a.size.split("x"))
    k = W / 1080
    bad = {x.strip().lower() for x in a.censor.split(",") if x.strip()}
    words = load_words(a.words)
    for w in words:
        w[0] = censor(w[0], bad)

    events = []  # (start, end, style, text)
    i = 0
    if not a.no_hook:
        j = next((n for n, w in enumerate(words) if SENT_END.search(w[0])), len(words) - 1)
        tw = [w[0] for w in words[:j + 1]]
        tw[-1] = re.sub(r"\.+$", "", tw[-1])
        events.append([words[0][1], words[j][2], "Hook", r"\N".join(split_lines(tw, HOOK_LINE_CHARS, two=False))])
        i = j + 1

    emph = [x.lower() for x in re.findall(r"\w+", a.emphasis)]
    emph_at = None
    if emph:
        norm = [re.sub(r"\W", "", w[0]).lower() for w in words]
        for s in range(i, len(words) - len(emph) + 1):
            if norm[s:s + len(emph)] == emph:
                emph_at = (s, s + len(emph))
                break
        if emph_at is None:
            print(f"emphasis '{a.emphasis}' not found in the words - skipped")

    cards = []
    if emph_at:
        cards = phrases(words[:emph_at[0]], i) + [list(range(*emph_at))] + \
            [[x + emph_at[1] for x in c] for c in phrases(words[emph_at[1]:], 0)]
    else:
        cards = phrases(words, i)

    for c in cards:
        ws = [words[n] for n in c]
        if emph_at and c[0] == emph_at[0]:
            # letter-by-letter reveal: each word's letters spread over its spoken time
            parts = []
            for w in ws:
                txt = re.sub(r"[^\w'’=-]", "", w[0]).upper()
                cs = max(1, round((w[2] - w[1]) * 100 / max(1, len(txt))))
                parts.append((txt, "".join(f"{{\\k{cs}}}{ch}" for ch in txt)))
            lines, cur = [], []   # <= 14 letters a line keeps it inside x 120-960
            for txt, tagged in parts:
                if cur and sum(len(x) + 1 for x, _ in cur) + len(txt) > 14:
                    lines.append(cur)
                    cur = []
                cur.append((txt, tagged))
            lines.append(cur)
            events.append([ws[0][1], ws[-1][2] + 0.6, "Emphasis",
                           r"\N".join(" ".join(t for _, t in l) for l in lines)])
            continue
        tw = [w[0] for w in ws]
        last = tw[-1]
        if not SENT_END.search(last):
            last = re.sub(r"[,;:]+$", "", last)
            nxt = c[-1] + 1
            if not a.no_ellipsis and nxt < len(words):
                last += "…"
        else:
            last = re.sub(r"\.+$", "", last)   # no full stop on a caption (subtitle skill)
        tw[-1] = last
        events.append([ws[0][1], ws[-1][2], "Default", r"\N".join(split_lines(tw, LINE_CHARS))])

    # timing: start on the first word, hold to the next card minus GAP (max +0.6 s)
    for n, e in enumerate(events):
        e[0] = max(0.0, e[0] - 0.03)
        nxt = events[n + 1][0] - 0.03 if n + 1 < len(events) else None
        hold = e[1] + 0.6
        e[1] = min(hold, nxt - GAP) if nxt is not None else e[1] + 0.4
        e[1] = max(e[1], e[0] + 0.3)

    fs_body, fs_hook, fs_emph = round(54 * k), round(68 * k), round(96 * k)
    style = ("Style: {name},{font},{fs},&H00FFFFFF,{sec},{box},&H00000000,{bold},0,0,0,100,100,0,0,"
             "{bs},{ol},{sh},8,{m},{m},{y},1")
    styles = [
        style.format(name="Default", font="Inter Medium", fs=fs_body, sec="&H000000FF", box="&H26000000",
                     bold=0, bs=3, ol=round(12 * k), sh=0, m=round(132 * k), y=round(a.body_y * H)),
        style.format(name="Hook", font="Inter", fs=fs_hook, sec="&H000000FF", box="&H00000000",
                     bold=-1, bs=3, ol=round(22 * k), sh=0, m=round(142 * k), y=round(a.hook_y * H)),
        style.format(name="Emphasis", font=a.emphasis_font, fs=fs_emph, sec="&HFF000000", box="&H00000000",
                     bold=0, bs=1, ol=0, sh=round(3 * k), m=round(120 * k), y=round(a.body_y * H)),
    ]
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(f"[Script Info]\nScriptType: v4.00+\nWrapStyle: 2\nScaledBorderAndShadow: yes\n"
                f"PlayResX: {W}\nPlayResY: {H}\n\n[V4+ Styles]\n"
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
                "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n" + "\n".join(styles) +
                "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for s, e, st, tx in events:
            f.write(f"Dialogue: {1 if st != 'Default' else 0},{t(s)},{t(e)},{st},,0,0,0,,{tx}\n")
    body = sum(1 for e in events if e[2] == "Default")
    print(f"{len(events)} events ({body} phrase cards"
          f"{', hook' if not a.no_hook else ''}{', emphasis' if emph_at else ''}) -> {a.out}")


if __name__ == "__main__":
    main()
