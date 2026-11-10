#!/usr/bin/env python3
"""
Fill the interactive plan editor (zoom plan + caption text) (assets/plan_editor_widget.html) with this
video's sentences, an optional starting plan and optional captions, and print
the HTML to pass verbatim as `widget_code` to the show_widget (visualize) tool.

One sentence per line in the sentences file, in final-video order, ONE LINE
PER CUT CLIP (the same order/count as the cut selections file) - the plan is
applied per clip, so sentences and clips must line up 1:1.

Plan JSON (optional; default = every clip wide, no changes) - same shape the
widget sends back after "PLAN_JSON:":
  [{"s": <start level>, "m": {"<word index>": <level>, ...}}, ...]
  level index: 0=1.0x, 1=1.5x, 2=1.7x, 3=2.0x, 4=2.2x
  word index = position in sentence.split(" ")

Captions (optional, --ass + --durations): the clicked words become the caption
text, and an "Izmeni tekst" toggle makes each sentence editable in place. Every Dialogue line of the ASS file
is assigned to the clip it starts in (clip found
from the rendered clip durations the ASS was timed against). The user fixes
wrong words there; the widget sends back "CAPTIONS_JSON:" with only the
changed screens, keyed by the Dialogue line's 0-based index - apply it with
apply_caption_edits.py.

Title: the first Dialogue of the ASS file whose Style is not Default (a
title such as "MODA NEKAD I SAD") is shown in the "Naslov" mode - its text
and the words it runs from / to. The widget sends back "TITLE_JSON:"
({"text", "from": [clip, word], "to": [clip, word]}, or {"text": ""} to
remove it) only when it changed; render_from_plan.py applies it.

Takes (optional, --takes): make_take_clips.py's takes.json. Adds a "Dublovi"
mode showing every alternative take of a sentence side by side (left / right)
with "Ovaj je bolji"; the widget sends back "TAKES_JSON:" ({"<clip>": take}),
only for clips whose take changed. Browser-pane version only (the clips are
served by serve_plan_editor.py --takes-dir).

Close-ups (optional, --closeups): make_closeup_clips.py's closeups.json. Adds
a "Close-up" mode: per close-up a start and an end slider (1 frame steps, ‹ ›
for one frame, snaps to caption / sentence edges within 2 frames) with the
close-up previewed over the player. --media must then be a render WITHOUT the
close-ups. Sends back "CLOSEUPS_JSON:" [{"name", "start", "end", "off"}] (all of
them, new times, off moved with the start) only when one changed. Browser-pane
version only (previews served by serve_plan_editor.py --closeups-dir).

Music accents (always available, "Muzika" mode): the user clicks words
where the music should hit - poenta (the strongest hit), naglasak (a strong
downbeat), promena (the track moves to a new section). The widget sends back
"ACCENTS_JSON:" [{"at": [clip, word], "kind", "word"}] (all of them, when
there are any); --accents shows a previous one again. With --music
(align_music.py's preview json) the aligned track plays with the video,
in sync, and grey ♪ / ♩ mark the words a hit / section change of the track
lands on now (music file served by serve_plan_editor.py --music-file).

B-roll (optional, --broll): a previous BROLL_JSON reply, so its ranges show
again. The widget's "B-roll" mode sends back "BROLL_JSON:" - render it with
apply_broll.py.

Playback (optional, --media + --words, needs --durations): the cut render
the durations belong to and its word_times.py output. Adds a video player
(play button per sentence, click a word with no mode checked = play from that
word). Only works in the browser-pane version (serve_plan_editor.py) - the
inline chat widget can't carry media, so don't pass these for show_widget.

Usage:
  make_plan_widget.py sentences.txt [plan.json] [--ass captions.ass --durations 6.28,6.08,...] [--broll broll.json] [--accents accents.json] [--music music_preview.json] [--takes takes.json] [--closeups closeups.json] [--media cut.mp4 --words words.json] > widget.html
"""
import argparse
import json
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "plan_editor_widget.html"


def ass_time(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def caption_style(ass_path):
    """Frame size and the Default style's font size / top position, for the position preview."""
    info = {"W": 1080, "H": 1920, "fs": 70, "y": 1215, "box": 16}
    for line in open(ass_path, encoding="utf-8"):
        if line.startswith("PlayResX:"):
            info["W"] = int(line.split(":")[1])
        elif line.startswith("PlayResY:"):
            info["H"] = int(line.split(":")[1])
        elif line.startswith("Style: Default,"):
            f = line.strip().split(",")
            info.update(fs=float(f[2]), box=float(f[16]), y=int(f[21]), align=int(f[18]))
    return info


def title_from_ass(ass_path, durations, sentences, media):
    """The first non-Default Dialogue (the title, e.g. "MODA NEKAD I SAD") as
    {text, a: [clip, word], b: [clip, word], st: style} for the Naslov mode."""
    style, ev, H = None, None, 1920
    for line in open(ass_path, encoding="utf-8"):
        if line.startswith("PlayResY:"):
            H = int(line.split(":")[1])
        if line.startswith("Style:") and not line.startswith("Style: Default,"):
            f = line.strip().split(",")
            style = style or {"name": f[0][6:].strip(), "fs": float(f[2]), "box": float(f[16]), "y": int(f[21])}
        elif line.startswith("Dialogue:") and ev is None:
            p = line.rstrip("\n").split(",", 9)
            if p[3] != "Default":
                ev = p
    if ev is None:
        return None
    st, en = ass_time(ev[1]), ass_time(ev[2])
    starts = [0.0]
    for d in durations:
        starts.append(starts[-1] + d)
    # word positions in the render: real word times if we have them, else spread over the clip
    pos = []
    for i, sent in enumerate(sentences):
        n = len(sent.split(" "))
        wt = media["words"][i] if media else None
        for j in range(n):
            t = wt[j] if wt and wt[j] is not None else starts[i] + (starts[i + 1] - starts[i]) * j / max(1, n)
            pos.append((t, [i, j]))
    a = next((w for t, w in pos if t >= st - 0.15), pos[0][1])
    b = [w for t, w in pos if t < en - 0.05] or [pos[-1][1]]
    st_ = dict(style or {"fs": 92, "box": 22, "y": 230}, H=H)
    return {"text": ev[9].replace("\\N", "\n"), "a": a, "b": b[-1], "st": st_, "style": ev[3]}


def captions_by_clip(ass_path, durations):
    starts = [0.0]
    for d in durations:
        starts.append(starts[-1] + d)
    out = [[] for _ in durations]
    idx = 0
    for line in open(ass_path, encoding="utf-8"):
        if not line.startswith("Dialogue:"):
            continue
        parts = line.rstrip("\n").split(",", 9)
        if parts[3] != "Default":
            # a title or other overlay style is not caption text; keep counting
            # it, since CAPTIONS_JSON / POS_JSON use the index over ALL Dialogue lines
            idx += 1
            continue
        st = ass_time(parts[1])
        clip = max(k for k in range(len(durations)) if starts[k] <= st + 0.05)
        # [dialogue index, text, start, end, own MarginV (0 = style default)]
        out[clip].append([idx, parts[9].replace("\\N", "\n"), round(st, 2), round(ass_time(parts[2]), 2),
                          int(parts[7] or 0)])
        idx += 1
    return out


def media_info(media, words_path, durs, sentences):
    """Clip [start, end] in the render and the start time of every sentence word."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from apply_broll import find_span, norm
    words = json.load(open(words_path, encoding="utf-8"))
    # word_times.py gives [[w, s, e], ...]; stt.py gives {"words": [{"word", "start", "end"}, ...]}
    if isinstance(words, dict):
        words = words["words"]
    words = [[w["word"], w["start"], w["end"]] if isinstance(w, dict) else w for w in words]
    starts = [0.0]
    for d in durs:
        starts.append(starts[-1] + d)
    clips, wt = [], []
    for i, sent in enumerate(sentences):
        cs, ce = starts[i], starts[i + 1]
        spoken = [(norm(w), s - cs, e - cs) for w, s, e in words if cs - 0.05 <= s < ce]
        tw = sent.split(" ")
        times = []
        for j in range(len(tw)):
            s, _, _ = find_span(tw, j, spoken)
            times.append(None if s is None else round(cs + max(0.0, s - 0.1), 2))
        clips.append([round(cs, 2), round(ce, 2)])
        wt.append(times)
    return {"src": "media/" + Path(media).name, "clips": clips, "words": wt}


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("sentences")
    ap.add_argument("plan", nargs="?")
    ap.add_argument("--ass")
    ap.add_argument("--durations")
    ap.add_argument("--write-sentences", help="write caption-derived sentences (one per clip) here")
    ap.add_argument("--media", help="video/audio of the cut render, for playback (browser-pane version)")
    ap.add_argument("--words", help="word_times.py output for --media")
    ap.add_argument("--pos", help="POS_JSON not yet applied to --ass (e.g. unsent slider moves), shown as changes")
    ap.add_argument("--broll", help="BROLL_JSON from a previous reply, to show existing B-roll ranges")
    ap.add_argument("--closeups", help="closeups.json from make_closeup_clips.py - shows the Close-up mode (browser pane only)")
    ap.add_argument("--accents", help="ACCENTS_JSON from a previous reply, to show the music accents again")
    ap.add_argument("--music", help="align_music.py --out json (one aligned track) or rank_tracks.py --out json "
                    "(A / B / C to switch tracks), played with the video (browser pane)")
    ap.add_argument("--takes", help="takes.json from make_take_clips.py - shows the Dublovi mode (browser pane only)")
    a = ap.parse_args()
    sentences = [l.strip() for l in open(a.sentences, encoding="utf-8") if l.strip()]
    if a.plan:
        plan = json.load(open(a.plan, encoding="utf-8"))
        if len(plan) != len(sentences):
            sys.exit(f"plan has {len(plan)} entries but there are {len(sentences)} sentences")
    else:
        plan = [{"s": 0, "m": {}} for _ in sentences]
    caps = [[] for _ in sentences]
    if a.ass:
        if not a.durations:
            sys.exit("--ass needs --durations (clip durations the captions are timed against)")
        durs = [float(x) for x in a.durations.split(",")]
        if len(durs) != len(sentences):
            sys.exit(f"{len(durs)} durations but {len(sentences)} sentences")
        caps = captions_by_clip(a.ass, durs)
        # With captions, the widget shows (and the user edits) the caption
        # text, so plan word indices refer to the caption words. Make sure
        # sentences.txt says the same words, or marks would land elsewhere.
        for i, c in enumerate(caps):
            if not c:
                continue
            cap_words = " ".join(t for _, t, *_ in c).split()
            if len(cap_words) != len(sentences[i].split()):
                sys.exit(f"clip {i + 1}: sentence has {len(sentences[i].split())} words but its captions "
                         f"have {len(cap_words)} - rewrite sentences.txt from the captions "
                         f"(--write-sentences) and redo plan word indices")
        if a.write_sentences:
            open(a.write_sentences, "w", encoding="utf-8").write(
                "\n".join(" ".join(" ".join(t for _, t, *_ in c).split()) if c else sentences[i]
                          for i, c in enumerate(caps)) + "\n")
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__SENTENCES__", json.dumps(sentences, ensure_ascii=False))
    html = html.replace("__PLAN__", json.dumps(plan, ensure_ascii=False))
    html = html.replace("__CAPTIONS__", json.dumps(caps, ensure_ascii=False))
    html = html.replace("__POS__", json.dumps(json.load(open(a.pos)) if a.pos else {}))
    html = html.replace("__CAPSTYLE__", json.dumps(caption_style(a.ass) if a.ass else None))
    broll = []
    if a.broll:
        # BROLL_JSON as the widget sends it -> the widget's own {a, b, media} shape
        broll = [{"a": r["from"], "b": r["to"], "media": r.get("media", "")}
                 for r in json.load(open(a.broll, encoding="utf-8"))]
    html = html.replace("__BROLL__", json.dumps(broll, ensure_ascii=False))
    takes = json.load(open(a.takes, encoding="utf-8")) if a.takes else {}
    for k in takes:
        if not 0 <= int(k) < len(sentences):
            sys.exit(f"takes.json: clip {k} is outside the {len(sentences)} sentences (indices are 0-based)")
    html = html.replace("__TAKES__", json.dumps(takes, ensure_ascii=False))
    cus = json.load(open(a.closeups, encoding="utf-8")) if a.closeups else []
    if cus and not a.media:
        sys.exit("--closeups needs --media (a render without the close-ups)")
    html = html.replace("__CLOSEUPS__", json.dumps(cus, ensure_ascii=False))
    acc = json.load(open(a.accents, encoding="utf-8")) if a.accents else []
    for x in acc:
        if not (0 <= x["at"][0] < len(sentences) and 0 <= x["at"][1] < len(sentences[x["at"][0]].split())):
            sys.exit(f"accents: {x} is outside the sentences")
    html = html.replace("__ACCENTS__", json.dumps([{"at": x["at"], "kind": x["kind"]} for x in acc]))
    mus = None
    if a.music:
        if not a.media:
            sys.exit("--music needs --media")
        m = json.load(open(a.music, encoding="utf-8"))
        # one aligned track (align_music.py --out) or a ranked list (rank_tracks.py --out)
        mus = [{"src": "music/" + Path(x["track"]).name, "track": Path(x["track"]).name, "start": x["start"],
                "vol": x.get("vol", 0.35), "marks": x.get("marks", []), "label": x.get("label"),
                "title": x.get("title"), "info": x.get("info")}
               for x in (m["tracks"] if "tracks" in m else [m])]
    html = html.replace("__MUSIC__", json.dumps(mus, ensure_ascii=False))
    media = None
    if a.media:
        if not (a.durations and a.words):
            sys.exit("--media needs --durations and --words")
        media = media_info(a.media, a.words, [float(x) for x in a.durations.split(",")], sentences)
    html = html.replace("__MEDIA__", json.dumps(media, ensure_ascii=False))
    title = title_from_ass(a.ass, durs, sentences, media) if a.ass else None
    html = html.replace("__TITLE__", json.dumps(title, ensure_ascii=False))
    sys.stdout.write(html)


if __name__ == "__main__":
    main()
