#!/usr/bin/env python3
r"""
Render the final video from a plan the user sent from the plan editor - one
command instead of re-running every step by hand.

Steps, in the only order that works:
  1. read the reply (PLAN_JSON, SENTENCES_JSON, CAPTIONS_JSON, POS_JSON,
     BROLL_JSON, TITLE_JSON) and write the pieces into the work dir
  2. zoom: build_zoom_selections.py -> cut_and_concat.sh (stops if a planned
     word can't be found in the speech)
  3. B-roll over the zoom render (apply_broll.py) - captions go on top later
  4. captions: shift to the new clip starts if durations changed, apply text
     fixes, force the agreed style rules (top anchor, 0.12s empty gap
     between screens), apply per-screen positions, burn
  5. a contact sheet (sheet.jpg) with frames just before/after every zoom
     change and inside every B-roll range, to look at before delivering

project.json (paths relative to the json file):
  {
    "source": "/path/to/raw/C0112.MP4",
    "cuts": "cuts.txt",            unpadded start<TAB>end per clip
    "positions": "pos.json",       [[cx, head_top_y], ...] on the (rotated) frame
    "pre_filter": "transpose=1",   optional, e.g. sideways footage
    "ass": "captions.ass",         captions timed against "durations" (optional)
    "words": "words.json",         word_times.py output for that same render
    "durations": [6.28, 6.04, ...] clip durations of that render
    "wide_zoom": 1.3               optional: zoom for "1,0x" instead of the baseline crop
    "alternate": true              optional: different shot size on every cut
                                   (build_zoom_selections.py --alternate)
  }

Usage:
  render_from_plan.py project.json plan_reply.txt workdir out.mp4
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from venc import venc
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HOME = Path.home() / ".claude" / "skills"
ZOOM = HOME / "zoom" / "scripts"
PE = HOME / "plan-editor" / "scripts"
SUB = HOME / "subtitle" / "scripts"
FFMPEG_FULL = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
GAP = 0.12  # empty screen between captions - the user asked for it


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd[:3]), "...", file=sys.stderr)
    return subprocess.run([str(c) for c in cmd], check=True, stdin=subprocess.DEVNULL, **kw)


def parse_reply(text):
    out = {}
    for key in ("PLAN_JSON", "SENTENCES_JSON", "CAPTIONS_JSON", "POS_JSON", "BROLL_JSON", "TAKES_JSON", "TITLE_JSON"):
        m = re.search(rf"^{key}:\s*(.+)$", text, re.M)
        if m:
            out[key] = json.loads(m.group(1))
    if "PLAN_JSON" not in out or "SENTENCES_JSON" not in out:
        sys.exit("reply has no PLAN_JSON / SENTENCES_JSON - was it sent from the plan editor?")
    if out.get("TAKES_JSON"):
        # another take changes the clip's length, words and caption timing -
        # none of the files this plan was made against still fit
        sys.exit("reply picks other takes (TAKES_JSON " + json.dumps(out["TAKES_JSON"]) + "): put those "
                 "takes' start/end into cuts.txt, re-render the cut, redo words.json / durations / "
                 "captions, and reopen the editor - see the plan-editor skill, 'Dublovi'")
    return out


def clip_durations(build):
    # skip macOS "._" AppleDouble files (exFAT external drives)
    files = sorted(f for f in (Path(build) / "clips").glob("*.mp4") if not f.name.startswith("._"))
    # frames / fps, not the container duration: cut_and_concat.sh joins
    # clips frame-exactly, so this is exactly where each clip starts
    out = []
    for f in files:
        n, r = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                        "stream=nb_frames,r_frame_rate", "-of", "csv=p=0", str(f)]).decode().strip().split(",")[::-1]
        num, den = r.split("/")
        out.append(int(n) * int(den) / int(num))
    return out


def t2s(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def s2t(x):
    x = max(0.0, x)
    return f"{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}"


def fix_captions(src, dst, old_durs, new_durs):
    """Resync to the new clip starts, top anchor, 0.12s gap between screens."""
    old = [0.0]
    for d in old_durs:
        old.append(old[-1] + d)
    new = [0.0]
    for d in new_durs:
        new.append(new[-1] + d)
    lines = open(src, encoding="utf-8").read().split("\n")
    ev = []
    for n, l in enumerate(lines):
        if l.startswith("Style: Default,"):
            f = l.split(",")
            if f[18] != "8":  # bottom anchor made captions jump with line count
                f[18], f[21] = "8", "1215"
                lines[n] = ",".join(f)
        elif l.startswith("Dialogue:"):
            p = l.split(",", 9)
            st, en = t2s(p[1]), t2s(p[2])
            k = max(i for i in range(len(old_durs)) if old[i] <= st + 0.05)
            sh = new[k] - old[k]
            p[1], p[2] = s2t(st + sh), s2t(en + sh)
            lines[n] = ",".join(p)
            if p[3] == "Default":  # the title spans many screens - no gap rule for it
                ev.append(n)
    for a, b in zip(ev, ev[1:]):
        pa, nb = lines[a].split(",", 9), t2s(lines[b].split(",", 9)[1])
        if t2s(pa[2]) > nb - GAP:
            pa[2] = s2t(nb - GAP)
            lines[a] = ",".join(pa)
    open(dst, "w", encoding="utf-8").write("\n".join(lines))


def main():
    proj_path, reply_path, work, out = sys.argv[1:5]
    base = Path(proj_path).resolve().parent
    P = json.load(open(proj_path, encoding="utf-8"))
    rel = lambda k: str((base / P[k]).resolve()) if P.get(k) else None
    work = Path(work).resolve()
    work.mkdir(parents=True, exist_ok=True)
    R = parse_reply(open(reply_path, encoding="utf-8").read())

    json.dump(R["PLAN_JSON"], open(work / "plan.json", "w"))
    (work / "sentences.txt").write_text("\n".join(R["SENTENCES_JSON"]) + "\n", encoding="utf-8")
    durs = ",".join(str(d) for d in P["durations"])

    # 2. zoom
    sel = work / "selections.txt"
    rep = subprocess.run([sys.executable, ZOOM / "build_zoom_selections.py", "--cuts", rel("cuts"),
                          "--positions", rel("positions"), "--plan", work / "plan.json",
                          "--sentences", work / "sentences.txt", "--words", rel("words"),
                          "--durations", durs, "--pre-filter", P.get("pre_filter", "")]
                         + (["--wide-zoom", str(P["wide_zoom"])] if P.get("wide_zoom") else [])
                         + (["--alternate"] if P.get("alternate") else []),
                         stdout=open(sel, "w"), stderr=subprocess.PIPE, text=True, check=True).stderr
    print(rep, file=sys.stderr, end="")
    if "no match" in rep:
        sys.exit("a planned zoom word was not found in the speech - fix it by hand (see report above)")
    changes = [(int(m.group(1)) - 1, float(m.group(2)))
               for m in re.finditer(r"clip (\d+): .* at ([\d.]+)s in clip", rep)]
    zoom_mp4 = work / "zoom.mp4"
    run([ZOOM / "cut_and_concat.sh", P["source"], sel, zoom_mp4, work / "build"], stdout=subprocess.DEVNULL)
    new_durs = clip_durations(work / "build")
    starts = [0.0]
    for d in new_durs:
        starts.append(starts[-1] + d)
    video = zoom_mp4
    checks = [t for c, t0 in changes for t in (starts[c] + t0 - 0.2, starts[c] + t0 + 0.25)]

    words = rel("words")
    if (R.get("BROLL_JSON") or R.get("TITLE_JSON")) and \
            [round(d, 2) for d in new_durs] != [round(d, 2) for d in P["durations"]]:
        words = str(work / "words.json")  # timing moved: re-time on this render
        run([sys.executable, ZOOM / "word_times.py", zoom_mp4, words])

    # 3. B-roll
    if R.get("BROLL_JSON"):
        missing = [r["media"] for r in R["BROLL_JSON"] if not os.path.isfile(os.path.expanduser(r["media"]))]
        if missing:
            sys.exit(f"B-roll media not resolved to real files yet: {missing} - find/ask, then edit the reply")
        json.dump(R["BROLL_JSON"], open(work / "broll.json", "w"), ensure_ascii=False)
        br = subprocess.run([sys.executable, PE / "apply_broll.py", zoom_mp4, work / "broll.mp4",
                             "--broll", work / "broll.json", "--sentences", work / "sentences.txt",
                             "--words", words, "--durations", ",".join(str(d) for d in new_durs)],
                            stderr=subprocess.PIPE, text=True, check=True).stderr
        print(br, file=sys.stderr, end="")
        for m in re.finditer(r"B\d+: ([\d.]+)s -> ([\d.]+)s", br):
            a, b = float(m.group(1)), float(m.group(2))
            checks += [a + 0.3, b - 0.3]
        video = work / "broll.mp4"

    # 4. captions
    if P.get("ass"):
        ass = work / "captions.ass"
        fix_captions(rel("ass"), ass, P["durations"], new_durs)
        if R.get("CAPTIONS_JSON"):
            json.dump(R["CAPTIONS_JSON"], open(work / "caption_edits.json", "w"), ensure_ascii=False)
            run([sys.executable, SUB / "apply_caption_edits.py", ass, work / "caption_edits.json", work / "c.tmp"])
            os.replace(work / "c.tmp", ass)
        if R.get("POS_JSON"):
            json.dump(R["POS_JSON"], open(work / "caption_pos.json", "w"))
            run([sys.executable, SUB / "apply_caption_positions.py", ass, work / "caption_pos.json", ass])
            ev = [l.split(",", 9) for l in open(ass, encoding="utf-8") if l.startswith("Dialogue:")]
            checks += [(t2s(ev[int(k)][1]) + t2s(ev[int(k)][2])) / 2 for k in R["POS_JSON"]]  # moved screens
        if R.get("TITLE_JSON") is not None and "TITLE_JSON" in R:
            # last: it removes the old title line, which shifts Dialogue indices
            json.dump(R["TITLE_JSON"], open(work / "title.json", "w"), ensure_ascii=False)
            tr = subprocess.run([sys.executable, PE / "apply_title.py", ass, work / "title.json",
                                 work / "sentences.txt", words, ",".join(str(d) for d in new_durs), ass],
                                stderr=subprocess.PIPE, text=True, check=True).stderr
            print(tr, file=sys.stderr, end="")
            m = re.search(r"title ([\d.]+)s -> ([\d.]+)s", tr)
            if m:
                checks += [float(m.group(1)) + 0.3, float(m.group(2)) - 0.3]
        run([FFMPEG_FULL, "-nostdin", "-y", "-i", video, "-vf", f"subtitles={ass}", *venc(18), "-pix_fmt", "yuv420p", "-c:a", "copy", out, "-loglevel", "error"])
    else:
        run(["cp", video, out])

    # 5. contact sheet
    chk = work / "chk"
    chk.mkdir(exist_ok=True)
    for f in chk.glob("*.png"):
        f.unlink()
    for n, t in enumerate(sorted(checks)[:24]):
        run([FFMPEG_FULL, "-nostdin", "-y", "-i", out, "-ss", f"{max(0, t):.2f}", "-frames:v", "1",
             "-vf", "scale=270:480", chk / f"f_{n:02d}.png", "-loglevel", "error"])
    if checks:
        cols = min(8, len(checks))
        run(["ffmpeg", "-nostdin", "-y", "-pattern_type", "glob", "-i", str(chk / "f_*.png"),
             "-vf", f"tile={cols}x{-(-min(24, len(checks)) // cols)}", "-frames:v", "1",
             work / "sheet.jpg", "-loglevel", "error"])
    print(f"-> {out}\n   check: {work / 'sheet.jpg'} (frames at {', '.join(f'{t:.2f}' for t in sorted(checks)[:24])})",
          file=sys.stderr)


if __name__ == "__main__":
    main()
