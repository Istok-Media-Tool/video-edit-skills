#!/usr/bin/env python3
"""
Re-arrange a track for one video: build a new version of it, bar by bar,
so its strongest moments land exactly on the places marked in the
plan-editor's Muzika mode (poenta / promena), and play it back as WAV.

align_music.py can only choose where the video STARTS in the track; with
two or three main places one start rarely serves them all. This script
cuts the track at bar lines and joins bars the way an editor would:

- the output is a beat grid anchored on the main accents: the gap between
  two of them becomes a whole number of beats; the rest (at most half a
  beat) is taken up by stretching that stretch of music slightly with
  rubberband (pitch unchanged, typically < 2 %, limit --max-stretch);
- when the gap is not a whole number of bars, the bar right before the
  accent is played from a later beat - the run-up into the hit stays
  natural, like a drop edit in a trailer;
- which source bar plays in each output bar is chosen for the whole video
  at once (Viterbi): each main accent gets a fitting event (poenta -> the
  strongest hit, also a bass entry; promena -> a section start, a hit, the
  bass coming in / out), jumps only along track_map.py's joins (seams that
  sound alike), as few jumps as possible, and strong hits are not spent
  on unmarked places inside the video;
- joins: 20 ms equal-power crossfade ending ON the new bar's downbeat, so
  its attack stays intact;
- naglasak accents are not forced: the report says whether a beat of the
  new version falls on them (within 70 ms), else suggests a sound effect;
- the END is the track's own ending (track_map's closure: its final chord /
  hit): it lands right after the last word (--close-at, default last word
  end + 0.12 s from --words, else the video's end) and rings out untouched -
  every video ends on a clear, emphasized closure (the user's rule). A
  track without one (closure strength < 0.3) ends where the video does, and
  the report says so.

Several different versions (--variants, default 3) are made by steering
each next one away from the events the previous ones used. Each gets a
WAV, its plan, and a music.json for the editor (A / B / C), where hits,
new sections and joins of the new version are marked.

Usage:
  arrange_music.py map.json --accents accents.json --words words.json \\
      --durations 6.28,... --sentences sentences.txt --out-dir music/arr
  arrange_music.py map.json --at "12.4:poenta,31.2:promena" --video-len 47.3 --out-dir music/arr
  options: [--audio full.wav] (render from the full-quality file when the map
  was made from a preview) [--tail 2.5] [--variants 3] [--max-stretch 0.04]
  [--close-at 83.2] [--ending closure|any] [--score-only] (plan only, JSON to stdout - rank_tracks.py)

Outputs in --out-dir: arr_A.wav ..., arrange.json (every variant: segments,
joins, where each accent landed, stretch, suggested SFX), music.json
(make_plan_widget.py --music; serve the WAVs with --music-file).
Check every WAV with verify_music.py before mixing (mix_bed.py
--track-start 0).
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from align_music import accent_times, LEAD  # same accent parsing and lead as align_music.py

SR = 48000
XF = 0.02          # crossfade at a join, ending on the new bar's downbeat
INF = 1e9
# a main accent on a real event is worth several joins (a join costs 0.25 + its seam cost)
KIND_W = {"promena": 6.0, "poenta": 6.0}


def load_stereo(path):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path, "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def stretch(x, ratio):
    """Time-stretch stereo samples by ratio (output = ratio x longer), pitch unchanged."""
    if abs(ratio - 1) < 1e-4:
        return x
    with tempfile.TemporaryDirectory() as d:
        i, o = os.path.join(d, "i.wav"), os.path.join(d, "o.wav")
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2",
                        "-i", "-", "-c:a", "pcm_f32le", i], input=x.tobytes(), check=True)
        subprocess.run(["rubberband", "-q", "-3", "-t", f"{ratio:.6f}", i, o], check=True, capture_output=True)
        return load_stereo(o)


def events(M):
    """Candidate events per main kind: {kind: {bar index: (strength, what)}}."""
    bars = M["bars"]
    nb = len(bars)
    dbs = np.array([b["db"] for b in bars])
    lo, hi = dbs.min(), dbs.max()
    loud = (dbs - lo) / max(1e-6, hi - lo)
    t2i = {round(b["t"], 2): i for i, b in enumerate(bars)}
    idx = lambda t: t2i.get(round(t, 2), int(np.argmin(np.abs(np.array([b["t"] for b in bars]) - t))))
    after = lambda i: float(loud[i:i + 4].mean())
    ev = {"poenta": {}, "promena": {}}

    def add(kind, i, s, what):
        if 0 < i < nb - 1 and s > ev[kind].get(i, (0, ""))[0]:
            ev[kind][i] = (round(float(s), 3), what)

    hits = [i for i in range(1, nb) if dbs[i] - dbs[i - 1] >= 4]
    for i in hits:
        jump = dbs[i] - dbs[i - 1]
        s = min(1.5, jump / 6) * (0.5 + 0.5 * after(i))
        add("poenta", i, s, f"udarac +{jump:.0f} dB")
        add("promena", i, 0.7 * s, f"udarac +{jump:.0f} dB")
    secs = M["sections"]
    for p, sct in zip(secs, secs[1:]):
        i = idx(sct["start"])
        diff = sct["db"] - p["db"]
        # a turn into a louder part counts fully; a drop counts less, and a near-silent
        # part (12 dB under the track's median) is no bed under speech
        s = 0.5 + (diff / 8 if diff > 0 else min(-diff, 8) / 8 * 0.6) + (0.3 if i in hits else 0)
        if sct["db"] < np.median(dbs) - 12:
            s *= 0.4
        add("promena", i, s, f"nov deo pesme ({diff:+.0f} dB)")
        if diff > 2:
            add("poenta", i, 0.6 * s, f"nov, glasniji deo ({diff:+.0f} dB)")
    for b in M.get("bass", []):
        i = idx(b["t"])
        add("promena", i, 0.6 if b["kind"] == "in" else 0.5, f"bas {'ulazi' if b['kind'] == 'in' else 'izlazi'}")
        if b["kind"] == "in":
            add("poenta", i, 0.5, "bas ulazi")
    # always feasible: any loud bar start, weak (the report then suggests a sound effect)
    for i in range(1, nb - 1):
        for k in ev:
            add(k, i, 0.05 + 0.1 * loud[i], "takt")
    hit_strength = {i: min(1.5, (dbs[i] - dbs[i - 1]) / 6) for i in hits}
    return ev, hit_strength, loud


def plan(M, acc, vlen, a, avoid=None):
    """Choose a source bar for every output bar. Returns a plan dict (no audio)."""
    bars = M["bars"]
    nb = len(bars)
    B = M["bar_seconds"]
    beat = B / 4
    T = np.array([b["t"] for b in bars] + [M["duration"]])
    blen = np.diff(T)
    usable = np.array([blen[i] > 0.9 * B for i in range(nb)])
    ev, hit_s, loud = events(M)
    avoid = avoid or {}

    # main accents become anchors; two closer than ~1 bar can't both be anchors
    main = sorted([x for x in acc if x["kind"] in KIND_W], key=lambda x: x["t"])
    dropped = []
    anchors = []
    for x in main:
        if anchors and x["t"] - anchors[-1]["t"] < B * 0.9:
            loser = anchors[-1] if x["kind"] == "poenta" or anchors[-1]["kind"] != "poenta" else x
            dropped.append(loser)
            if loser is anchors[-1]:
                anchors[-1] = x
            continue
        anchors.append(x)
    total = vlen + a.tail

    # the track's own ending as the last anchor: its bar starts so that the final chord lands on close_at
    cl = M.get("closure") or {}
    close = None
    if a.ending == "closure" and cl.get("t") is not None and cl.get("strength", 0) >= 0.3:
        i_c = int(np.searchsorted(T[:nb], cl["t"] + 1e-6) - 1)
        off = cl["t"] - T[i_c]
        ring = min(M["duration"], cl["t"] + cl["ring"] + 0.3) - T[i_c]
        close = {"t": a.close_at - off + LEAD, "kind": "kraj", "word": "kraj pesme", "bar": i_c, "ring": ring,
                 "close_at": a.close_at, "what": cl.get("what", "kraj"), "strength": cl["strength"]}
        usable[i_c] = True
        while anchors and anchors[-1]["t"] > close["t"] - B * 0.9:
            dropped.append(anchors.pop())
        anchors.append(close)
        total = close["t"] - LEAD + ring

    # output slots: (kind, anchor k or None, partial beats or 0)
    slots = []
    if anchors:
        v0 = anchors[0]["t"] - LEAD
        n0 = max(1, math.ceil(v0 / B))
        slots += [{"type": "pre"} for _ in range(n0)]
        intervals = []
        for k, x in enumerate(anchors):
            if k + 1 < len(anchors):
                G = anchors[k + 1]["t"] - x["t"]
                nbeats = max(4, int(round(G / beat)))
                m, rem = divmod(nbeats, 4)
                intervals.append((G, nbeats))
                slots.append({"type": "anchor", "k": k})
                slots += [{"type": "mid", "k": k} for _ in range(m - 1)]
                if rem:
                    slots.append({"type": "partial", "k": k, "beats": rem})
            elif x["kind"] == "kraj":
                slots.append({"type": "anchor", "k": k})      # the ending rings out: no bars after it
            else:
                slots.append({"type": "anchor", "k": k})
                n_post = max(1, math.ceil((total - (x["t"] - LEAD)) / B))
                slots += [{"type": "post", "k": k} for _ in range(n_post - 1)]
    else:
        slots = [{"type": "post", "k": None} for _ in range(math.ceil(total / B) + 1)]
        intervals = []

    # transition costs between source bars
    Tm = np.full((nb, nb), INF)
    for i in range(nb - 1):
        Tm[i, i + 1] = 0.0
    for i, j, c in M.get("joins", []):
        Tm[i, j] = min(Tm[i, j], 0.25 + c + (0.1 if j <= i else 0))
    Tm[:, ~usable] = INF

    S = len(slots)
    U = np.zeros((S, nb))
    U[:, ~usable] = INF
    choice_info = {}
    # where each slot sits in the output (video seconds), for the waste penalty
    if anchors:
        t_slot, t = [], anchors[0]["t"] - LEAD - sum(1 for s in slots if s["type"] == "pre") * B
        for s in slots:
            t_slot.append(t)
            t += s.get("beats", 4) * beat
    else:
        t_slot = [k * B for k in range(S)]
    for si, s in enumerate(slots):
        if s["type"] == "anchor":
            x = anchors[s["k"]]
            row = np.full(nb, INF)
            if x["kind"] == "kraj":
                row[x["bar"]] = 0.0
                U[si] = row
                continue
            cand = ev[x["kind"]]
            for i, (st, what) in cand.items():
                if usable[i]:
                    row[i] = -KIND_W[x["kind"]] * st + avoid.get((s["k"], i), 0)
            U[si] = row
        else:
            # a strong hit inside the video on an unmarked bar wastes it
            if 0 <= t_slot[si] < vlen:
                for i, hs in hit_s.items():
                    U[si, i] += 0.6 * hs
    # music under the opening: rather a phrase start
    phr = np.array([b.get("phrase", 0) for b in bars])
    U[0] += np.where(phr == 0, 0, 0.15)

    # Viterbi; the bar before a partial-anchor run is entered mid-bar (small extra cost),
    # and an anchor after a partial bar must follow its natural predecessor
    cost = U[0].copy()
    back = np.zeros((S, nb), int)
    for si in range(1, S):
        Ts = Tm.copy()
        if slots[si - 1]["type"] == "partial":
            Ts = np.full((nb, nb), INF)
            for j in range(1, nb):
                Ts[j - 1, j] = 0.0
        if slots[si]["type"] == "partial":
            Ts = Ts + np.where(Ts < INF, 0.15, 0)
        tot = cost[:, None] + Ts
        back[si] = np.argmin(tot, 0)
        cost = tot[back[si], np.arange(nb)] + U[si]
    end = int(np.argmin(cost))
    if cost[end] >= INF / 2:
        return None
    seq = [end]
    for si in range(S - 1, 0, -1):
        seq.append(int(back[si, seq[-1]]))
    seq = seq[::-1]

    # exact timing: each interval's stretch so the next anchor lands exactly
    out = []
    if anchors:
        # pre-roll: ratio 1, ending exactly at the first anchor
        pre = [si for si, s in enumerate(slots) if s["type"] == "pre"]
        t = anchors[0]["t"] - LEAD - sum(blen[seq[si]] for si in pre)
        for si in pre:
            out.append({"slot": si, "src": seq[si], "s0": float(T[seq[si]]), "len": float(blen[seq[si]]),
                        "ratio": 1.0, "o0": t})
            t += blen[seq[si]]
        for k, x in enumerate(anchors):
            ks = [si for si, s in enumerate(slots) if s.get("k") == k and s["type"] in ("anchor", "mid", "partial", "post")]
            pieces = []
            for si in ks:
                i = seq[si]
                if x["kind"] == "kraj":
                    pieces.append((si, i, float(T[i]), float(x["ring"])))
                elif slots[si]["type"] == "partial":
                    nbt = slots[si]["beats"]
                    ln = blen[i] * nbt / 4
                    pieces.append((si, i, float(T[i + 1] - ln), float(ln)))
                else:
                    pieces.append((si, i, float(T[i]), float(blen[i])))
            o = x["t"] - LEAD
            if k + 1 < len(anchors):
                G = anchors[k + 1]["t"] - x["t"]
                r = G / sum(p[3] for p in pieces)
            else:
                r = 1.0
            for si, i, s0, ln in pieces:
                out.append({"slot": si, "src": i, "s0": s0, "len": ln, "ratio": r, "o0": o})
                o += ln * r
    else:
        t = 0.0
        for si in range(S):
            i = seq[si]
            out.append({"slot": si, "src": i, "s0": float(T[i]), "len": float(blen[i]), "ratio": 1.0, "o0": t})
            t += blen[i]

    # report
    joins = []
    for p, q in zip(out, out[1:]):
        natural = abs((p["s0"] + p["len"]) - q["s0"]) < 1e-3
        if not natural:
            mid = slots[q["slot"]]["type"] == "partial"
            c = Tm[p["src"], q["src"]]
            # into a partial bar the seam is inside a bar (beats skipped): its cost is the
            # bar-level join + 0.15, the real seam is measured by verify_music.py
            c = None if c >= INF else (0.0 if c == 0 else float(c) - 0.25) + (0.15 if mid else 0)
            joins.append({"t": round(q["o0"], 3), "from_bar": p["src"], "to_bar": q["src"],
                          "from": round(p["s0"] + p["len"], 3), "to": round(q["s0"], 3),
                          "cost": None if c is None else round(c, 2), "mid_bar": mid})
    landed = []
    for k, x in enumerate(anchors):
        si = next(si for si, s in enumerate(slots) if s["type"] == "anchor" and s["k"] == k)
        i = seq[si]
        st, what = (x["strength"], x["what"]) if x["kind"] == "kraj" else ev[x["kind"]].get(i, (0, "?"))
        landed.append({"word": x["word"], "kind": x["kind"], "t": x["t"], "bar": i, "src_t": round(float(T[i]), 3),
                       "lands": what, "strength": st, "error_ms": 0})
        if x["kind"] == "kraj":
            landed[-1]["close_at"] = round(x["close_at"], 3)
    for x in dropped:
        landed.append({"word": x["word"], "kind": x["kind"], "t": x["t"], "lands": "preblizu prethodnom",
                       "strength": 0, "error_ms": None})
    # output beats, to check the naglasak accents
    obeats, ohits, osecs = [], [], []
    sec_starts = {round(s["start"], 2) for s in M["sections"][1:]}
    for p in out:
        nbt = int(round(p["len"] / beat))
        for b in range(nbt):
            obeats.append(p["o0"] + b * beat * p["ratio"])
        full = p["len"] > 0.9 * B
        if full and p["src"] in hit_s:
            ohits.append(round(p["o0"], 3))
        if full and round(float(T[p["src"]]), 2) in sec_starts:
            osecs.append(round(p["o0"], 3))
    obeats = np.array(obeats)
    for x in acc:
        if x["kind"] in KIND_W:
            continue
        tau = x["t"] - LEAD
        d = float(obeats[np.argmin(np.abs(obeats - tau))] - tau) if len(obeats) else None
        landed.append({"word": x["word"], "kind": x["kind"], "t": x["t"],
                       "lands": "otkucaj" if d is not None and abs(d) <= 0.07 else "ništa",
                       "strength": 0.5 if d is not None and abs(d) <= 0.07 else 0,
                       "error_ms": None if d is None else round(d * 1000)})
    sfx = []
    for L_ in landed:
        if L_["kind"] in KIND_W and L_["strength"] < 0.45:
            sfx.append({"at": round(L_["t"] - LEAD, 3), "align": "peak", "kind": "impact", "why": f"„{L_['word']}“: pesma ovde ima samo {L_['lands']}"})
        if L_["kind"] == "naglasak" and L_["lands"] == "ništa":
            sfx.append({"at": round(L_["t"] - LEAD, 3), "align": "peak", "kind": "hit", "why": f"„{L_['word']}“: nijedan otkucaj ne pada na reč"})
    builds = {round(b["hit"], 2) for b in M.get("builds", [])}
    for L_ in landed:
        if L_["kind"] == "poenta" and L_.get("src_t") is not None and round(L_["src_t"], 2) not in builds \
                and L_["strength"] >= 0.45:
            sfx.append({"at": round(L_["t"] - LEAD, 3), "align": "peak", "kind": "riser",
                        "why": f"„{L_['word']}“: udarac bez zaleta u pesmi"})
    wasted = [t for t in ohits if 0 <= t < vlen and not any(abs(t - (x["t"] - LEAD)) < 0.25 for x in anchors)]
    stretch_max = max((abs(p["ratio"] - 1) for p in out), default=0)
    score = float(-cost[end])
    return {"segments": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in p.items()} for p in out],
            "joins": joins, "accents": landed, "sfx": sfx, "wasted": [round(w, 2) for w in wasted],
            "hits": ohits, "sections": osecs, "stretch_max": round(stretch_max, 4), "score": round(score, 2),
            "used": [(L_.get("bar"), k) for k, L_ in enumerate(landed[:len(anchors)])], "length": round(total, 3),
            "closure": None if close is None else {"at": round(close["close_at"], 3), "what": close["what"],
                                                     "strength": close["strength"], "ends": round(total, 3)}}


def plan_distinct(M, acc, vlen, a, avoid):
    """plan(), steered so one event (the same drop) doesn't serve several accents:
    a repeated event costs REUSE per repeat; replan up to 3 times, keep the best."""
    REUSE = 2.5
    local = dict(avoid)
    best = None
    for _ in range(4):
        P = plan(M, acc, vlen, a, local)
        if P is None:
            break
        bars = [b for b, k in P["used"] if b is not None]
        dups = len(bars) - len(set(bars))
        val = P["score"] - REUSE * dups
        if best is None or val > best[0]:
            best = (val, P)
        if not dups:
            break
        seen = set()
        for b, k in P["used"]:
            if b in seen:
                local[(k, b)] = local.get((k, b), 0) + REUSE
            seen.add(b)
    if best:
        bars = [b for b, k in best[1]["used"] if b is not None]
        best[1]["repeats"] = len(bars) - len(set(bars))
    return best[1] if best else None


def render(P, audio, out_wav):
    total = P["length"]
    n = int(round(total * SR))
    y = np.zeros((n + SR, 2), np.float32)
    segs = P["segments"]
    # merge segments that are contiguous in the source and share a ratio into runs
    runs = []
    for s in segs:
        if runs and abs(runs[-1]["s0"] + runs[-1]["len"] - s["s0"]) < 1e-3 and abs(runs[-1]["ratio"] - s["ratio"]) < 1e-6:
            runs[-1]["len"] += s["len"]
        else:
            runs.append(dict(s))
    pad = 0.05
    for k, r in enumerate(runs):
        a0 = max(0, int(round((r["s0"] - pad) * SR)))
        a1 = min(len(audio), int(round((r["s0"] + r["len"] + pad) * SR)))
        lead = (r["s0"] * SR - a0) / SR                      # seconds of pre-roll actually taken
        piece = stretch(audio[a0:a1], r["ratio"])
        o_start = r["o0"] - lead * r["ratio"]                # where the piece's first sample goes
        t = o_start + np.arange(len(piece)) / SR
        g = np.ones(len(piece), np.float32)
        # fade in over [o0 - XF, o0] (not for the very first run), out over [o1 - XF, o1]
        o0, o1 = r["o0"], r["o0"] + r["len"] * r["ratio"]
        if k > 0:
            g *= np.where(t < o0 - XF, 0, np.where(t < o0, np.sin(0.5 * np.pi * (t - o0 + XF) / XF), 1))
        if k < len(runs) - 1:
            g *= np.where(t > o1, 0, np.where(t > o1 - XF, np.cos(0.5 * np.pi * (t - o1 + XF) / XF), 1))
        i0 = int(round(o_start * SR))
        lo, hi = max(0, i0), min(len(y), i0 + len(piece))
        if hi > lo:
            y[lo:hi] += (piece * g[:, None])[lo - i0:hi - i0]
    y = y[:n]
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2",
                    "-i", "-", "-c:a", "pcm_s24le", out_wav], input=y.tobytes(), check=True)


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("map")
    ap.add_argument("--audio", help="audio to render from (default: the map's track)")
    ap.add_argument("--accents")
    ap.add_argument("--words")
    ap.add_argument("--durations")
    ap.add_argument("--sentences")
    ap.add_argument("--at")
    ap.add_argument("--video-len", type=float)
    ap.add_argument("--tail", type=float, default=2.5)
    ap.add_argument("--variants", type=int, default=3)
    ap.add_argument("--max-stretch", type=float, default=0.04)
    ap.add_argument("--ending", choices=["closure", "any"], default="closure",
                    help="closure: end on the track's own final chord / hit (default); any: just stop at video + tail")
    ap.add_argument("--close-at", type=float, help="video time (s) of the final chord (default: last word end + 0.12)")
    ap.add_argument("--out-dir")
    ap.add_argument("--score-only", action="store_true")
    a = ap.parse_args()

    M = json.load(open(a.map))
    vlen = a.video_len or (sum(float(x) for x in a.durations.split(",")) if a.durations else None)
    if vlen is None:
        sys.exit("pass --durations or --video-len")
    acc = accent_times(a) if (a.accents or a.at) else []
    if a.close_at is None:
        from mix_bed import last_word_end
        a.close_at = last_word_end(a.words) + 0.12 if a.words else vlen

    plans, avoid = [], {}
    for v in range(a.variants):
        P = plan_distinct(M, acc, vlen, a, avoid)
        if P is None:
            break
        if P["stretch_max"] > a.max_stretch:
            P["note"] = f"istezanje {P['stretch_max'] * 100:.1f} % - preko granice, preslušaj"
        key = tuple(P["used"])
        if any(tuple(q["used"]) == key and q["joins"] == P["joins"] for q in plans):
            break
        plans.append(P)
        for bar, k in P["used"]:
            if bar is not None:
                avoid[(k, bar)] = avoid.get((k, bar), 0) + 1.5
    if not plans:
        sys.exit("no arrangement possible (track too short or no usable bars)")

    mmss = lambda t: f"{int(t // 60)}:{t % 60:05.2f}"
    if a.score_only:
        print(json.dumps({"track": M["track"], "plans": plans}, ensure_ascii=False))
        return

    os.makedirs(a.out_dir or ".", exist_ok=True)
    audio = load_stereo(a.audio or M["track"])
    tracks = []
    for v, P in enumerate(plans):
        lab = chr(65 + v)
        wav = os.path.join(a.out_dir or ".", f"arr_{lab}.wav")
        render(P, audio, wav)
        P["label"], P["wav"] = lab, wav
        hit = [x for x in P["accents"] if x["strength"] >= 0.45 and x["kind"] != "kraj"]
        print(f"\n{lab}: {wav}  ({len(P['joins'])} spojeva, istezanje do {P['stretch_max'] * 100:.1f} %, ocena {P['score']})"
              + (f"  ! {P['note']}" if P.get("note") else "")
              + (f"  (isti udarac {P['repeats'] + 1}x)" if P.get("repeats") else ""))
        for x in P["accents"]:
            if x["kind"] == "kraj":
                continue
            src = f" (takt iz {mmss(x['src_t'])})" if x.get("src_t") is not None else ""
            em = "" if x["error_ms"] in (None, 0) else f" {x['error_ms']:+d} ms"
            print(f"   {'OK' if x['strength'] >= 0.45 else '--'} {x['kind']:8s} „{x['word']}“ {x['t']:6.2f}s -> {x['lands']}{src}{em}")
        for j in P["joins"]:
            c = "?" if j["cost"] is None else f"{j['cost']:.2f}"
            print(f"   spoj {mmss(j['t'])}: {mmss(j['from'])} -> {mmss(j['to'])}  (cena {c}{', usred takta' if j['mid_bar'] else ''})")
        c = P.get("closure")
        print(f"   {'OK' if c and c['strength'] >= 0.5 else '--'} kraj     " + (
            f"{c['what']} na {c['at']:.2f}s, muzika se završava na {c['ends']:.2f}s" if c else
            "pesma nema jasan kraj - prekida se na kraju videa (izaberi drugu pesmu)"))
        if P["wasted"]:
            print(f"   jaki udarci na neoznačenim mestima (s): {', '.join(f'{w:.1f}' for w in P['wasted'])}")
        for s in P["sfx"]:
            print(f"   predlog efekta: {s['kind']} (vrh) na {s['at']:.2f}s - {s['why']}")
        marks = [{"t": t, "kind": "hit"} for t in P["hits"] if 0 <= t <= vlen]
        marks += [{"t": t, "kind": "section"} for t in P["sections"] if 0 <= t <= vlen and t not in P["hits"]]
        marks += [{"t": j["t"], "kind": "join"} for j in P["joins"] if 0 <= j["t"] <= vlen]
        if P.get("closure") and P["closure"]["at"] <= vlen:
            marks.append({"t": P["closure"]["at"], "kind": "hit"})
        tracks.append({"track": wav, "start": 0.0, "vol": 0.35, "label": lab, "title": f"aranžman {lab}",
                       "marks": sorted(marks, key=lambda m: m["t"]),
                       "info": f"{lab}: {len(hit)}/{len([x for x in P['accents'] if x['kind'] != 'kraj'])} mesta, {len(P['joins'])} spojeva, "
                               f"istezanje {P['stretch_max'] * 100:.1f} %"})
    json.dump({"track": M["track"], "map": a.map, "video_len": vlen, "tail": a.tail, "plans": plans},
              open(os.path.join(a.out_dir or ".", "arrange.json"), "w"), ensure_ascii=False, indent=1)
    json.dump({"tracks": tracks}, open(os.path.join(a.out_dir or ".", "music.json"), "w"), ensure_ascii=False, indent=1)
    print(f"\n-> {a.out_dir}/arrange.json, music.json (make_plan_widget.py --music; serve_plan_editor.py --music-file "
          + " ".join(Path(t['track']).name for t in tracks) + ")")
    print("   next: verify_music.py on each WAV, then mix_bed.py <video> arr_X.wav out.mp4 --track-start 0")


if __name__ == "__main__":
    main()
