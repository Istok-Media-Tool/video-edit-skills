#!/usr/bin/env python3
"""
Line the music up with the video: choose where in the track the video
starts so the track's strongest moments land on the words the user marked
in the plan-editor's "Muzika" mode - and are NOT spent elsewhere.

Accent kinds (ACCENTS_JSON from the editor):
  promena   the track moves into a new section here (a section start from
            track_map.py, best if it is also a hit) - a big change in the story
  poenta    the strongest hit (a bar >= 4 dB louder than the one before) -
            the punchline, the key line, the last sentence
  naglasak  a downbeat (bar start), the louder the better - an emphasised term
The beat lands 0.03 s before the word starts (the ear groups them).

Scoring: each accent scores by how close (Gaussian, 70 ms) its best event
lands and how strong that event is (promena / poenta count 3x, naglasak 1x);
every strong hit that lands inside the video but NOT on a poenta / promena
costs a little - the strongest beats are kept for the marked places. With no
accents the video simply starts on a downbeat. The window must fit in the
track (start + video length + --tail <= track length).

Prints the 3 best starts with what lands on each accent, and an Epidemic
Sound EditRecording request that would put the track's strongest moment
exactly on the main accent when one start can't satisfy them all (the
connector re-edits the track to the video's length around required regions).

Usage:
  align_music.py map.json --accents accents.json --words words.json \\
      --durations 6.28,6.04,... --sentences sentences.txt [--tail 2.5] \\
      [--out music_preview.json]
  align_music.py map.json --at "12.40:poenta,31.2:promena" --video-len 95.3

--out = {"track", "start", ...} - pass --track-start <start> to mix_bed.py,
and the same file to make_plan_widget.py --music to hear it in the editor.
"""
import argparse
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.expanduser("$SKILLS/plan-editor/scripts")))

KIND_W = {"promena": 3.0, "poenta": 3.0, "naglasak": 1.0}
SIG = 0.07
LEAD = 0.03


def g(d):
    return math.exp(-0.5 * (d / SIG) ** 2)


def accent_times(a):
    if a.at:
        out = []
        for part in a.at.split(","):
            t, k = part.split(":")
            out.append({"t": float(t), "kind": k.strip(), "word": f"{float(t):.2f}s"})
        return out
    from make_plan_widget import media_info   # same word matching as the editor
    sents = [l.strip() for l in open(a.sentences, encoding="utf-8") if l.strip()]
    durs = [float(x) for x in a.durations.split(",")]
    mi = media_info("x.mp4", a.words, durs, sents)
    out = []
    for x in json.load(open(a.accents, encoding="utf-8")):
        i, j = x["at"]
        t = mi["words"][i][j]
        if t is None:
            sys.exit(f"accent '{x.get('word')}' ({i + 1}.) has no time in words.json")
        out.append({"t": t + 0.1, "kind": x["kind"], "word": x.get("word") or sents[i].split()[j]})
    return out


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("map")
    ap.add_argument("--accents")
    ap.add_argument("--words")
    ap.add_argument("--durations")
    ap.add_argument("--sentences")
    ap.add_argument("--at", help='"t:kind,..." in video seconds, instead of --accents')
    ap.add_argument("--video-len", type=float)
    ap.add_argument("--tail", type=float, default=2.5, help="music needed after the video ends (held ending)")
    ap.add_argument("--out")
    a = ap.parse_args()

    M = json.load(open(a.map))
    dur_track = M["duration"]
    vlen = a.video_len or (sum(float(x) for x in a.durations.split(",")) if a.durations else None)
    if vlen is None:
        sys.exit("pass --durations or --video-len")
    acc = accent_times(a) if (a.accents or a.at) else []
    bars = M["bars"]
    dbs = [b["db"] for b in bars]
    lo, hi = min(dbs), max(dbs)
    loud = {round(b["t"], 3): (b["db"] - lo) / max(1e-6, hi - lo) for b in bars}
    hits = [(bars[i]["t"], dbs[i] - dbs[i - 1]) for i in range(1, len(bars)) if dbs[i] - dbs[i - 1] >= 4]
    secs = [(s["start"], abs(s["db"] - p["db"])) for p, s in zip(M["sections"], M["sections"][1:])]
    downs = [(b["t"], loud[round(b["t"], 3)]) for b in bars]
    hit_ts = {round(t, 2) for t, _ in hits}
    max_start = dur_track - vlen - a.tail
    if max_start < 0:
        sys.exit(f"the track ({dur_track:.1f}s) is shorter than the video + tail ({vlen + a.tail:.1f}s) - "
                 f"use a longer track or an Epidemic Sound edit to the video's length (EditRecording)")

    def best_event(kind, tau):
        """(score 0..~2, event time, what) of the best event for this accent at track time tau."""
        cands = []
        if kind == "promena":
            cands += [(g(tau - t) * (1 + st / 6) * (1.3 if round(t, 2) in hit_ts else 1), t, "nov deo pesme")
                      for t, st in secs]
        if kind in ("poenta", "promena"):
            cands += [(g(tau - t) * (1 + st / 6) * (1 if kind == "poenta" else 0.6), t, f"udarac +{st:.0f} dB")
                      for t, st in hits]
            cands += [(g(tau - t) * 0.35 * (0.5 + l), t, "takt") for t, l in downs]
        if kind == "naglasak":
            cands += [(g(tau - t) * (0.6 + 0.4 * l), t, "takt") for t, l in downs]
            cands += [(g(tau - t) * 0.35, t, "udarac") for t in M["beats"]]
        return max(cands) if cands else (0, None, "")

    def score(s):
        tot, rep = 0.0, []
        for x in acc:
            tau = s + x["t"] - LEAD
            sc, t, what = best_event(x["kind"], tau)
            tot += KIND_W.get(x["kind"], 1) * sc
            rep.append((x, sc, t, what, (t - tau) if t is not None else None))
        strong = [x["t"] for x in acc if x["kind"] in ("poenta", "promena")]
        wasted = []
        for t, st in hits:
            v = t - s + LEAD
            if 0 <= v <= vlen and not any(abs(v - u) < 0.25 for u in strong):
                tot -= 0.4 * st / 6
                wasted.append(v)
        tot += 0.3 * max(g(s - t) for t, _ in downs)     # start on a bar
        return tot, rep, wasted

    cand = {round(t, 3) for t, _ in downs if 0 <= t <= max_start}
    for x in acc:
        for t in [t for t, _ in hits + secs + downs]:
            s = t - x["t"] + LEAD
            if 0 <= s <= max_start:
                cand.add(round(s, 3))
    ranked = sorted(((score(s), s) for s in cand), key=lambda r: -r[0][0])[:3]
    if not ranked:
        sys.exit("no start fits")

    mmss = lambda t: f"{int(t // 60)}:{t % 60:05.2f}"
    print(f"track {M['track']} ({mmss(dur_track)}, {M['bpm']} BPM), video {vlen:.1f}s + tail {a.tail}s, "
          f"{len(acc)} accents")
    for n, ((tot, rep, wasted), s) in enumerate(ranked):
        print(f"\n#{n + 1}  start in track at {mmss(s)}  (score {tot:.2f})")
        for x, sc, t, what, d in rep:
            ok = "OK " if sc > 0.6 else "~  " if sc > 0.25 else "--"
            land = f"{what} at {mmss(t)} ({d * 1000:+.0f} ms)" if t is not None else "nothing"
            print(f"   {ok} {x['kind']:8s} „{x['word']}“ {x['t']:6.2f}s -> {land}")
        if wasted:
            print(f"   strong hits on unmarked places (video s): {', '.join(f'{v:.1f}' for v in wasted)}")

    (tot, rep, wasted), s = ranked[0]
    main_acc = [x for x in acc if x["kind"] in ("promena", "poenta")]
    if main_acc and any(sc < 0.6 for x, sc, *_ in rep if x["kind"] in ("promena", "poenta")):
        x = main_acc[-1]
        # the track's biggest moment: a hit INTO the loudest music - half the jump
        # plus how loud the 4 bars after it are (a big jump into a quiet part loses)
        idx = {round(bb["t"], 2): k for k, bb in enumerate(bars)}
        after = lambda t: sum(dbs[idx[round(t, 2)]:idx[round(t, 2)] + 4]) / len(dbs[idx[round(t, 2)]:idx[round(t, 2)] + 4])
        ev = max(hits or secs, key=lambda h: 0.5 * h[1] + after(h[0]) - lo)
        bar = M["bar_seconds"]
        r0 = max(0.0, ev[0] - 8 * bar)
        off = x["t"] - LEAD - (ev[0] - r0)
        if off >= 0:
            req = {"targetDurationMs": int((vlen + a.tail) * 1000), "downloadAudioFormat": "WAV",
                   "forceDuration": True,
                   "requiredRegionsAtOffsets": [{"startMs": int(r0 * 1000), "endMs": int(min(dur_track, ev[0] + 4 * bar) * 1000),
                                                 "offsetMsInEdit": int(off * 1000)}]}
            print(f"\nOne start can't hit every main accent. Epidemic Sound can re-edit the track so its "
                  f"strongest moment ({mmss(ev[0])}) lands on „{x['word']}“ - EditRecording input:\n"
                  + json.dumps(req))

    if a.out:
        marks = [{"t": round(t - s, 3), "kind": "hit"} for t, _ in hits if 0 <= t - s <= vlen]
        marks += [{"t": round(t - s, 3), "kind": "section"} for t, _ in secs
                  if 0 <= t - s <= vlen and round(t, 2) not in hit_ts]
        json.dump({"track": M["track"], "start": round(s, 3), "score": round(tot, 2), "vol": 0.35,
                   "marks": sorted(marks, key=lambda m: m["t"]),
                   "accents": [{"word": x["word"], "kind": x["kind"], "t": x["t"], "lands": what,
                                "error_ms": None if d is None else round(d * 1000)} for x, sc, t, what, d in rep]},
                  open(a.out, "w"), ensure_ascii=False, indent=1)
        print(f"\n-> {a.out}: mix_bed.py --track-start {s:.3f}; make_plan_widget.py --music {a.out}")


if __name__ == "__main__":
    main()
