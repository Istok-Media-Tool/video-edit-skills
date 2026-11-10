#!/usr/bin/env python3
"""
Rank candidate tracks for one video: which one serves the places the user
and Claude marked (plan-editor "Muzika": poenta / naglasak / promena) best -
judged by what the track can do AFTER it is re-arranged, not only by the
best place to start it.

For every track (track_map.py, align_music.py, arrange_music.py --score-only),
six criteria, each measured 0..1 - the weights in rank_weights.json (next to
this script, or --weights your.json) add up to 100, so the score is out of 100:
- main_hits 30: poenta / promena land on a real event after arranging;
- closure 25: the track's own ending (a final chord / hit, not a fade) -
  every video ends on a clear, emphasized closure;
- natural 20: the arrangement still sounds like the track (few joins, clean
  seams, no event reused for several places, no level jumps at joins);
- voice 10: the music is not busy under the voice (onset density);
- arc 10: the music rises with the story;
- accents 5: naglasak places on a beat of the arrangement.
Tracks with vocals or shorter than the video + tail are not scored (listed
at the bottom). Per-criterion points of every track: <work>/rank.json.
Change the numbers in rank_weights.json to change what matters.

It ranks what is worth listening to; the user picks by ear in the editor.
Then make the arrangements of the top tracks with arrange_music.py (and,
for Epidemic tracks, epidemic_edit.py) and put them in the editor as A / B / C.

Usage:
  rank_tracks.py a.mp3 b.mp3 ... --accents accents.json --words words.json \\
      --durations 6.28,... --sentences sentences.txt [--meta meta.json] \\
      [--weights rank_weights.json] [--tail 2.5] [--work music_rank] [--out editor/music.json] [--top 3]
  (or --at "12.4:poenta,31.2:promena" --video-len 47.3 instead of the four)

--meta: {"<file name>": {"bpm": 120, "title": "Leveler", "id": "<epidemic id>", "vocals": false,
          "drums": "stems/x_drums.mp3", "bass": "stems/x_bass.mp3"}}
Epidemic's bpm avoids half / double tempo (see track_map.py); its preview
mp3 (lqmp3Url) and stem previews are enough to rank - download the full
track only for the pick.
--out: the top tracks, each from its best plain start, for make_plan_widget.py --music.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def mmss(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def arc_of(dbs):
    """-1..1: does the music rise like the story (louder at the end than the start)?"""
    if len(dbs) < 6:
        return 0.0, "kratko"
    k = max(1, len(dbs) // 3)
    first, last = sum(dbs[:k]) / k, sum(dbs[-k:]) / k
    rise = last - first
    score = max(-1.0, min(1.0, rise / 6))
    if first >= max(dbs) - 1.5:          # already at full energy from the first bars
        score -= 0.5
    word = "raste" if rise > 2 else "pada" if rise < -2 else "ravno"
    return round(max(-1.0, score), 2), f"{word} {rise:+.0f} dB"


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("tracks", nargs="+")
    ap.add_argument("--meta")
    ap.add_argument("--weights", default=str(HERE / "rank_weights.json"))
    ap.add_argument("--accents")
    ap.add_argument("--words")
    ap.add_argument("--durations")
    ap.add_argument("--sentences")
    ap.add_argument("--at")
    ap.add_argument("--video-len", type=float)
    ap.add_argument("--tail", type=float, default=2.5)
    ap.add_argument("--work", default="music_rank")
    ap.add_argument("--out")
    ap.add_argument("--top", type=int, default=3)
    a = ap.parse_args()

    meta = json.load(open(a.meta, encoding="utf-8")) if a.meta else {}
    W = {k: v for k, v in json.load(open(a.weights)).items() if not k.startswith("_")}
    os.makedirs(a.work, exist_ok=True)
    acc_args = []
    for k in ("accents", "words", "durations", "sentences", "at"):
        if getattr(a, k):
            acc_args += [f"--{k}", getattr(a, k)]
    if a.video_len:
        acc_args += ["--video-len", str(a.video_len)]
    vlen = a.video_len or sum(float(x) for x in a.durations.split(","))

    rows = []
    for tr in dict.fromkeys(a.tracks):          # each file once
        name, stem = Path(tr).name, Path(tr).stem
        info = meta.get(name, {})
        title = info.get("title") or stem
        mp = os.path.join(a.work, stem + ".map.json")
        cmd = [sys.executable, str(HERE / "track_map.py"), tr, "--out", mp, "--png", os.path.join(a.work, stem + ".png")]
        for k in ("bpm", "drums", "bass"):
            if info.get(k):
                v = str(info[k])
                if k != "bpm" and not os.path.isabs(v):        # stem paths are relative to meta.json
                    v = os.path.join(os.path.dirname(os.path.abspath(a.meta)), v)
                cmd += [f"--{k}", v]
        subprocess.run(cmd, check=True, capture_output=True)
        M = json.load(open(mp))
        row = {"track": tr, "title": title, "bpm": M["bpm"], "id": info.get("id"), "map": mp}
        parts = {}

        # 1. no editing: the best start
        al = os.path.join(a.work, stem + ".align.json")
        r = subprocess.run([sys.executable, str(HERE / "align_music.py"), mp, *acc_args, "--tail", str(a.tail),
                            "--out", al], capture_output=True, text=True)
        short = r.returncode != 0 and "shorter than the video" in (r.stderr + r.stdout)
        if r.returncode == 0:
            A = json.load(open(al))
            acc = A["accents"]
            hit = [x for x in acc if x["error_ms"] is not None and abs(x["error_ms"]) <= 70]
            row.update(start=A["start"], vol=A["vol"], marks=A["marks"], plain_hit=f"{len(hit)}/{len(acc)}")
            parts["plain"] = A["score"]
        else:
            row.update(start=None, plain_hit="-")
            parts["plain"] = 0.0
            if not short:
                row["note"] = r.stderr.strip().splitlines()[-1][:120] if r.stderr.strip() else "align_music failed"
        parts["short"] = 1.0 if short else 0.0

        # 2. the best re-arrangement
        r = subprocess.run([sys.executable, str(HERE / "arrange_music.py"), mp, *acc_args, "--tail", str(a.tail),
                            "--variants", "1", "--score-only"], capture_output=True, text=True)
        if r.returncode == 0:
            P = json.loads(r.stdout)["plans"][0]
            main = [x for x in P["accents"] if x["kind"] in ("poenta", "promena")]
            main_ok = [x for x in main if x["strength"] >= 0.45]
            nag = [x for x in P["accents"] if x["kind"] == "naglasak"]
            row["arr_hit"] = f"{len(main_ok)}/{len(main)}"
            row["joins"] = len(P["joins"])
            row["miss"] = [f"„{x['word']}“ ({x['lands']})" for x in main if x not in main_ok]
            row["wasted"] = P["wasted"]
            parts["main_hits"] = (sum(min(1.0, x["strength"] / 0.8) for x in main) / len(main)) if main else 1.0
            parts["accents"] = (sum(x["lands"] == "otkucaj" for x in nag) / len(nag)) if nag else 1.0
            # does the arrangement still sound like the track: joins, their seams, reused events, level jumps
            bars = M["bars"]
            J = P["joins"]
            costs = [j["cost"] for j in J if j["cost"] is not None]
            jumps = [max(0.0, abs(bars[j["from_bar"]]["db"] - bars[j["to_bar"]]["db"]) - 6) for j in J]
            pen = (min(0.4, 0.03 * len(J)) + min(0.2, 0.2 * (sum(costs) / len(costs) if costs else 0))
                   + min(0.2, 0.05 * P.get("repeats", 0)) + min(0.4, (sum(jumps) / len(jumps) if jumps else 0) / 25))
            parts["natural"] = max(0.0, 1 - pen)
            row["repeats"] = P.get("repeats", 0)
            # loudness and density of what plays under the video, bar by bar
            under = [g for g in P["segments"] if 0 <= g["o0"] < vlen]
            dbs = [bars[g["src"]]["db"] for g in under]
            dens = [bars[g["src"]]["density"] for g in under]
            arc, row["arc_txt"] = arc_of(dbs)
            parts["arc"] = (arc + 1) / 2
            d = sum(dens) / len(dens) if dens else 0.2
            parts["voice"] = min(1.0, max(0.0, 1 - (d - 0.05) / 0.15))
        else:
            row.update(arr_hit="-", joins=0, miss=[], wasted=[], arc_txt="-", repeats=0, arr_failed=True)
            if r.stderr.strip():
                row["note"] = "arrange_music: " + r.stderr.strip().splitlines()[-1][:120]
            parts.update(main_hits=0.0, accents=0.0, natural=0.0, arc=0.0, voice=0.0)
        cl = M.get("closure") or {}
        parts["closure"] = float(cl.get("strength", 0.0))
        row["close_txt"] = cl.get("what", "-")
        row["parts"] = {k: round(v, 2) for k, v in parts.items()}
        row["out"] = ("vokal" if info.get("vocals") else "prekratka" if short
                      else "aranžman nije uspeo" if row.get("arr_failed") else None)
        row["score"] = None if row["out"] else round(sum(W.get(k, 0) * v for k, v in parts.items()), 1)
        rows.append(row)

    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    # every track's criteria and what each one adds to the score - to tune rank_weights.json
    json.dump([{"title": r["title"], "score": r["score"], "out": r["out"], "parts": r["parts"],
                "points": {k: round(W.get(k, 0) * v, 1) for k, v in r["parts"].items() if k in W}} for r in rows],
              open(os.path.join(a.work, "rank.json"), "w"), ensure_ascii=False, indent=1)
    print(f"video {vlen:.1f}s + tail {a.tail}s, {len(rows)} tracks, weights {a.weights}")
    print("ocena od 100 = " + " + ".join(f"{k} {W[k]:g}" for k in W) + " (svaki kriterijum 0..1)\n")
    print(f"{'#':>2}  {'pesma':28s} {'BPM':>4}  {'mesta':>6} {'kraj':>5} {'spojevi':>7} {'glas':>5} {'tok':>5} "
          f"{'nagl.':>5}  {'ocena':>5}   glavna mesta / spojeva / kraj")
    for i, r in enumerate(rows):
        p = r["parts"]
        sc = f"{r['score']:5.1f}" if r["score"] is not None else "    -"
        print(f"{i + 1:2d}  {r['title'][:28]:28s} {r['bpm']:4.0f}  {p['main_hits']:6.2f} {p['closure']:5.2f} "
              f"{p['natural']:7.2f} {p['voice']:5.2f} {p['arc']:5.2f} {p['accents']:5.2f}  {sc}   "
              f"{r['arr_hit']} / {r['joins']}" + (f" (isti deo {r['repeats'] + 1}x)" if r["repeats"] else "")
              + f" / {r['close_txt']}" + (f"  ISKLJUČENA: {r['out']}" if r["out"] else ""))
        if r["miss"]:
            print(f"      ni aranžman ne pogađa: {', '.join(r['miss'])}")
        if r.get("note"):
            print(f"      {r['note']}")
    print(f"\n(mesta = glavna mesta na pravom udarcu posle preuređivanja; kraj = završni akord pesme; "
          f"spojevi = koliko aranžman zvuči kao pesma; glas = koliko muzika ne smeta govoru)"
          f"\nkriterijumi i poeni: {a.work}/rank.json, slike toka: {a.work}/<pesma>.png")
    top = [r for r in rows if r["score"] is not None][:a.top]
    q = lambda v: "'" + v + "'" if " " in v else v
    print("\nsledeće - aranžmani za najbolje:")
    for r in top:
        print(f"  arrange_music.py {q(r['map'])} {' '.join(q(x) for x in acc_args)} "
              f"--out-dir {a.work}/arr_{re.sub(r'[^A-Za-z0-9]+', '_', Path(r['track']).stem.removeprefix('ES_'))[:24].strip('_')}")
        if r.get("id"):
            print(f"  epidemic_edit.py request {q(r['map'])} --id {r['id']} {' '.join(q(x) for x in acc_args)}")

    if a.out:
        tops = [r for r in rows if r.get("start") is not None and r["score"] is not None][:a.top]
        for i, r in enumerate(tops):
            r["label"] = chr(65 + i)
            r["info"] = (f"{r['label']}: bez sečenja {r['plain_hit']}, aranžman {r['arr_hit']} glavnih, "
                         f"tok {r['arc_txt']}, od {mmss(r['start'])}")
        json.dump({"tracks": tops}, open(a.out, "w"), ensure_ascii=False, indent=1)
        print(f"-> {a.out}: make_plan_widget.py --music {a.out}; serve_plan_editor.py --music-file "
              + " ".join(Path(r["track"]).name for r in tops))


if __name__ == "__main__":
    main()
