"""
English number words -> digits for captions (make_phrase_captions.py --digits).

The transcript spells numbers out ("nineteen twenty-six", "four thousand
dollars"); the user's reference reels show them as digits ("1926", "$4,000",
"100 years"), which read faster on a phone. In the avocado test (2026-11-18)
this had to be fixed card by card by hand.

Rules (kept conservative - a wrong digit is worse than a word):
- a run of number words becomes one token, timed from its first to its last
  word, keeping the last word's punctuation;
- "nineteen twenty-six" (two 2-digit groups, no hundred/thousand) -> 1926;
- "a hundred" / "a thousand" count, "a million" alone does not ("one in a
  million" stays words);
- converted only when the value is >= 10 or money/percent follows
  ("one dollar" -> $1, "five percent" -> 5%); "one tree", "two kids" stay;
- dollars -> "$4,000" (the "dollars" word is merged in), percent -> "5%".
"""
import re

UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve "
                                     "thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if i >= 2}
SCALE = {"hundred": 100, "thousand": 1000, "million": 10 ** 6, "billion": 10 ** 9}
MONEY = {"dollar": "$", "dollars": "$", "bucks": "$"}
PERCENT = {"percent", "per-cent"}

PUNCT = re.compile(r"^(.*?)([.,!?;:…\"'”’)]*)$")


def core(tok):
    m = PUNCT.match(tok)
    return m.group(1).lower(), m.group(2)


def small(w):
    """value of a word under 100 (incl. 'twenty-six'), else None"""
    if w in UNITS:
        return UNITS[w]
    if w in TENS:
        return TENS[w]
    if "-" in w:
        a, b = w.split("-", 1)
        if a in TENS and b in UNITS and 0 < UNITS[b] < 10:
            return TENS[a] + UNITS[b]
    return None


def parse(ws):
    """value of a list of number words, or None"""
    groups = [small(w) for w in ws if w not in SCALE and w not in ("and", "a")]
    if not any(w in SCALE for w in ws) and len(groups) == 2 and 10 <= groups[0] <= 99 and groups[1] >= 10:
        return groups[0] * 100 + groups[1]            # a year: nineteen twenty-six
    total = cur = 0
    seen = False
    for w in ws:
        v = small(w)
        if v is not None:
            if seen and cur % 100 and v < 100 and cur % 10 == 0 and v < 10:
                cur += v
            elif seen and cur % 100 and v < 100:
                return None                            # "five six" - not one number
            else:
                cur += v
            seen = True
        elif w == "a":
            cur += 1
        elif w == "and":
            continue
        elif w in SCALE:
            cur = max(cur, 1) * SCALE[w]
            if SCALE[w] >= 1000:
                total += cur
                cur = 0
    return total + cur if seen or any(w in SCALE for w in ws) else None


def convert(words):
    """words: [[text, start, end], ...] -> same, number runs merged into digit tokens"""
    out, i, n = [], 0, len(words)
    while i < n:
        c, _ = core(words[i][0])
        j = i
        run = []
        while j < n:
            w, p = core(words[j][0])
            nxt = core(words[j + 1][0])[0] if j + 1 < n else ""
            ok = (small(w) is not None or w in SCALE or
                  (w == "and" and run and nxt and (small(nxt) is not None)) or
                  (w == "a" and not run and nxt in ("hundred", "thousand")))
            if not ok:
                break
            run.append(w)
            j += 1
            if p:                                      # punctuation ends the number
                break
        if run and run[-1] == "and":
            run.pop()
            j -= 1
        has_digit_word = any(small(w) is not None for w in run) or (run[:1] == ["a"] and len(run) > 1)
        val = parse(run) if run and has_digit_word else None
        if val is None:
            out.append(list(words[i]))
            i += 1
            continue
        last_p = core(words[j - 1][0])[1]
        end = words[j - 1][2]
        unit, k = "", j
        if not last_p and j < n:
            u, up = core(words[j][0])
            if u in MONEY:
                unit, last_p, end, k = "$", up, words[j][2], j + 1
            elif u in PERCENT:
                unit, last_p, end, k = "%", up, words[j][2], j + 1
        if val < 10 and not unit:
            out.append(list(words[i]))
            i += 1
            continue
        is_year = len(run) == 2 and val >= 1000 and not any(w in SCALE for w in run)
        txt = str(val) if is_year or val < 10000 and not unit else f"{val:,}"
        if unit == "$":
            txt = f"${val:,}"
        elif unit == "%":
            txt = f"{val}%"
        if words[i][0][:1].isupper() and not txt[:1].isdigit() and txt[:1] != "$":
            txt = txt.capitalize()
        out.append([txt + last_p, words[i][1], end])
        i = k
    return out


if __name__ == "__main__":
    tests = [
        "exactly one hundred years ago in nineteen twenty-six.",
        "he gets one dollar per clone sold",
        "earned just four thousand dollars for inventing",
        "is a one in a million genetic accident",
        "One of these trees, one tree and two kids",
        "a hundred years. Twenty five percent of it",
        "for a hundred and fifty thousand people",
        "thousands more from it",
    ]
    for s in tests:
        ws = [[w, k, k + 0.5] for k, w in enumerate(s.split())]
        print(" ".join(w[0] for w in convert(ws)))
