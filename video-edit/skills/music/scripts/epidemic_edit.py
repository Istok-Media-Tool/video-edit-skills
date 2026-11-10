#!/usr/bin/env python3
"""
Let Epidemic Sound re-arrange one of its tracks for the video: write the
EditRecording request from the track map and the marked places, then
measure the edits it returns and put them in the editor next to
arrange_music.py's versions.

Epidemic's own editor builds the joins (it knows the track's stems and
structure); we only tell it which part of the original has to sit where:

  request   for every main accent (poenta / promena) the best event of the
            track (same choice as arrange_music.py: the strongest hit, a
            section start, the bass coming in) and the region around it -
            its build-up (or 2 bars) before, 2 bars after - required at
            (accent - 0.03 s - build) in the edit; length = video + tail.
            Each event is used once.

What Epidemic's editor can do (tested 2026-11-10 on "intuition", 120 BPM):
- it cuts on its own bar grid, so two required regions work only when the
  distance between them in the edit is a whole number of bars (8 bars apart:
  edit made; 5.4 s and 8.7 s apart: COMPLETED with no edit). Accents that
  don't fit the grid of the first one (within 60 ms) are left out of the
  request and reported - arrange_music.py serves those (it stretches).
- every region came out ~0.29-0.30 s LATER than asked, the same for all
  regions of one edit: collect measures it and shifts the whole edit
  (--track-start), after which the regions sat within +-8 ms.
- forceDuration and AVOID regions are untested on a successful edit - only
  with --force-duration / --avoid.
  collect   the downloaded edits: verify_music.py --regions on each (did the
            regions land, to the ms?), track_map.py for the editor's marks,
            and a music.json (labels after the ones already in --merge).

Usage:
  epidemic_edit.py request map.json --id <recording uuid> \\
      (--accents accents.json --words words.json --durations ... --sentences sentences.txt
       | --at "21.7:poenta,38.4:promena" --video-len 45) [--tail 2.5] [--out edit_request.json]
  -> pass the printed {"id", "input"} to the Epidemic Sound EditRecording tool, then
     PollEditRecordingJob until COMPLETED, DownloadRecordingEdit for each edit (WAV)
  epidemic_edit.py collect edit_1.wav edit_2.wav ... --request edit_request.json \\
      --source <full original> [--bpm 114] [--merge arr/music.json] --out music.json
  (PollEditRecordingJob shows one edit per job; maxResults > 1 is not visible through it)
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from align_music import accent_times, LEAD
from arrange_music import events, KIND_W


def request(a):
    M = json.load(open(a.map))
    vlen = a.video_len or sum(float(x) for x in a.durations.split(","))
    acc = sorted([x for x in accent_times(a) if x["kind"] in KIND_W], key=lambda x: x["t"])
    if not acc:
        sys.exit("no poenta / promena accents - nothing for Epidemic to place")
    bars = M["bars"]
    B = M["bar_seconds"]
    T = [b["t"] for b in bars] + [M["duration"]]
    ev, hit_s, _ = events(M)
    builds = {round(b["hit"], 2): b for b in M.get("builds", [])}
    used, regions, report = set(), [], []
    tol = 0.06
    # the grid is set by one accent; take the one that lets the most accents in (poenta, then later, wins a tie)
    fits = lambda r: [x for x in acc if abs((x["t"] - r["t"]) / B - round((x["t"] - r["t"]) / B)) * B <= tol]
    ref = max(acc, key=lambda r: (len(fits(r)), r["kind"] == "poenta", r["t"]))
    first_at = ref["t"]
    taken = []                                          # source spans already required
    out_end = -1.0
    # each part of the original is required once: an event inside a span already taken is skipped
    free = lambda i: all(not (s0 - 2 * B < T[i] < s1 + 2 * B) for s0, s1 in taken)
    for x in acc:
        cand = sorted(((st, i, what) for i, (st, what) in ev[x["kind"]].items() if i not in used and free(i)),
                      reverse=True)
        if not cand:
            report.append(f"  {x['kind']:8s} „{x['word']}“: no free event left in the track")
            continue
        st, i, what = cand[0]
        nbar = (x["t"] - first_at) / B
        off = abs(nbar - round(nbar)) * B
        if off > tol:
            report.append(f"  {x['kind']:8s} „{x['word']}“ {x['t']:6.2f}s: {nbar:+.2f} taktova od „{ref['word']}“ "
                          f"({off * 1000:.0f} ms van mreže) - Epidemic ga ne može složiti, ostaje za arrange_music.py")
            continue
        used.add(i)
        bd = builds.get(round(T[i], 2))
        pre = T[i] - bd["start"] if bd else 2 * B
        at = x["t"] - LEAD                              # where the event's downbeat must be in the edit
        pre = min(pre, at - max(0.0, out_end) - 0.05)   # don't overlap the previous region in the edit
        pre = max(0.0, min(pre, T[i]))
        post = min(2 * B, M["duration"] - T[i])
        r = {"startMs": int(round((T[i] - pre) * 1000)), "endMs": int(round((T[i] + post) * 1000)),
             "offsetMsInEdit": int(round((at - pre) * 1000))}
        if r["offsetMsInEdit"] < 0:
            r["startMs"] -= r["offsetMsInEdit"]
            r["offsetMsInEdit"] = 0
        regions.append(r)
        taken.append((r["startMs"] / 1000, r["endMs"] / 1000))
        out_end = at + post
        report.append(f"  {x['kind']:8s} „{x['word']}“ {x['t']:6.2f}s <- {what} at {T[i]:.2f}s "
                      f"(region {r['startMs'] / 1000:.2f}-{r['endMs'] / 1000:.2f}s at {r['offsetMsInEdit'] / 1000:.2f}s in the edit)")
    avoid = [{"startMs": int(T[i] * 1000), "endMs": int(T[i + 1] * 1000), "preferenceType": "AVOID"}
             for i in hit_s if i not in used and hit_s[i] >= 0.6
             and all(not (r["startMs"] < T[i + 1] * 1000 and T[i] * 1000 < r["endMs"]) for r in regions)]
    inp = {"targetDurationMs": int(round((vlen + a.tail) * 1000)), "downloadAudioFormat": "WAV",
           "maxResults": 3, "skipStems": True, "requiredRegionsAtOffsets": regions}
    if a.force_duration:
        inp["forceDuration"] = True
    if avoid and a.avoid:
        inp["preferenceRegions"] = avoid
    req = {"id": a.id, "input": inp}
    out = a.out or "edit_request.json"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump(req, open(out, "w"), indent=1)
    print(f"track {M['track']}, video {vlen:.1f}s + tail {a.tail}s")
    print("\n".join(report))
    if avoid and a.avoid:
        print(f"  AVOID: {len(avoid)} other strong hits")
    print(f"\n-> {out}; EditRecording input:\n{json.dumps(req)}")


def collect(a):
    req = json.load(open(a.request))
    prev = json.load(open(a.merge))["tracks"] if a.merge else []
    tracks = list(prev)
    n0 = len(prev)
    vlen = req["input"]["targetDurationMs"] / 1000
    for k, wav in enumerate(a.edits):
        lab = chr(65 + n0 + k)
        r = subprocess.run([sys.executable, str(HERE / "verify_music.py"), wav, "--regions", a.request,
                            "--source", a.source], capture_output=True, text=True)
        print(f"\n{lab}: {wav}\n{r.stdout.rstrip()}")
        mp = os.path.splitext(wav)[0] + ".map.json"
        cmd = [sys.executable, str(HERE / "track_map.py"), wav, "--out", mp]
        if a.bpm:
            cmd += ["--bpm", str(a.bpm)]
        subprocess.run(cmd, check=True, capture_output=True)
        M = json.load(open(mp))
        marks = [{"t": t, "kind": "hit"} for t in M["hits"] if t <= vlen]
        marks += [{"t": s["start"], "kind": "section"} for s in M["sections"][1:]
                  if s["start"] <= vlen and s["start"] not in M["hits"]]
        ok = r.returncode == 0
        # Epidemic snaps regions to its own grid (+289 ms on the first test): the whole edit is shifted
        # by the measured median error, so the video starts that much into it (negative = delayed)
        shift = next((float(l.split()[1]) for l in r.stdout.splitlines() if l.startswith("SHIFT ")), 0.0)
        marks = [dict(m, t=round(m["t"] - shift, 3)) for m in marks if 0 <= m["t"] - shift <= vlen]
        tracks.append({"track": wav, "start": round(max(0.0, shift), 3), "shift": round(shift, 3), "vol": 0.35,
                       "label": lab, "title": f"Epidemic {lab}", "marks": sorted(marks, key=lambda m: m["t"]),
                       "info": f"{lab}: Epidemic edit, pomak {shift * 1000:+.0f} ms, "
                               f"{'delovi na mestu' if ok else 'PROMAŠUJE - vidi proveru'}"})
        print(f"   -> mix_bed.py <video> {wav} out.mp4 --track-start {shift:.3f}")
    json.dump({"tracks": tracks}, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"\n-> {a.out}: make_plan_widget.py --music {a.out}; serve_plan_editor.py --music-file "
          + " ".join(Path(t["track"]).name for t in tracks))


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("request")
    r.add_argument("map")
    r.add_argument("--id", required=True, help="Epidemic recording id")
    for k in ("accents", "words", "durations", "sentences", "at", "out"):
        r.add_argument(f"--{k}")
    r.add_argument("--video-len", type=float)
    r.add_argument("--tail", type=float, default=2.5)
    r.add_argument("--force-duration", action="store_true", help="exact length (untested on a successful edit)")
    r.add_argument("--avoid", action="store_true", help="mark other strong hits AVOID (untested)")
    c = sub.add_parser("collect")
    c.add_argument("edits", nargs="+")
    c.add_argument("--request", required=True)
    c.add_argument("--source", required=True)
    c.add_argument("--bpm", type=float)
    c.add_argument("--merge")
    c.add_argument("--out", required=True)
    a = ap.parse_args()
    request(a) if a.cmd == "request" else collect(a)


if __name__ == "__main__":
    main()
