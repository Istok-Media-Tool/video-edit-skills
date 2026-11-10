#!/usr/bin/env python3
"""
Map of a music track - what Claude cannot hear, measured: tempo, beats,
bars (downbeats), the track's sections and how its energy moves bar by bar.
Use it to pick the window of a track (Step 2), to put a cut or a key line
on a downbeat or a hit, and to see whether the track ends cleanly.

What it measures (numpy only):
- tempo + beats: onset strength (spectral flux) autocorrelation, then beat
  positions snapped to the real onsets. --bpm (e.g. from Epidemic Sound's
  metadata) fixes the tempo and avoids half/double-tempo mistakes.
- downbeats: of the 4 beat phases, the one with the most low-end (kick /
  bass) onsets starts the bar. 4/4 is assumed.
- per bar: loudness (dB), low end (< 150 Hz), brightness, onset density.
- sections: where the bar-to-bar character changes (self-similarity
  novelty over loudness, low end, brightness, density and harmony), snapped
  to 4-bar phrases. Each gets a level (low / mid / high, relative to the
  track) and a shape (steady / build / falling).
- hits: bars where loudness jumps >= 4 dB from the bar before (a drop, an
  impact) - the strongest moments to land a key line on.
- closure: the track's own ending - its last loud attack (final chord / hit),
  how long it rings and how strong it is (0..1); "ending" = "hard" when >= 0.5,
  else "fade". arrange_music.py ends every version on it; rank_tracks.py
  weighs it (the user: every video ends on a clear, emphasized closure).
- builds: the run-up into each hit (bars where the music keeps rising) -
  place the build under the lines before a poenta, not only the hit.
- joins: for every bar, the bars the music can JUMP to without it being
  heard (play bar i, then bar j instead of i+1). Cost 0 = the natural next
  bar; it compares the bars around the jump (loudness, low end,
  brightness, density, harmony) and the spectrum right at the seam, and
  adds 0.3 when j sits at another place in its 4-bar phrase. Below ~0.5
  a jump is usually inaudible, above ~1 it is heard - arrange_music.py
  builds new versions of the track from these.
- stems (--drums / --bass, e.g. Epidemic Sound's stem previews): beats and
  bar starts come from the drum stem alone (no melody in the way), and
  every bar gets the bass level (bass_db) - where the bass drops out or
  comes in is a section change the full mix can hide.

Usage:
  track_map.py track.mp3 [--bpm 120] [--drums drums.mp3] [--bass bass.mp3]
               [--out map.json] [--png map.png]
Prints a table of sections and hits; --png draws loudness per bar with the
sections, hits and minute marks (Read the PNG to look at it).
"""
import argparse
import json
import subprocess
import sys

import numpy as np

SR = 22050
HOP = 512
NFFT = 2048


def load(path):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def stft_mag(x):
    win = np.hanning(NFFT).astype(np.float32)
    n = 1 + (len(x) - NFFT) // HOP
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    return np.abs(np.fft.rfft(x[idx] * win, axis=1)).astype(np.float32)


def tempo(onset, fps, hint=None):
    o = onset - onset.mean()
    ac = np.correlate(o, o, "full")[len(o) - 1:]
    lags = np.arange(len(ac)) / fps                       # seconds per beat
    ok = (lags > 60 / 200) & (lags < 60 / 55)
    if hint:
        ok &= np.abs(60 / np.maximum(lags, 1e-6) - hint) < hint * 0.04
        if not ok.any():
            return refine(onset, fps, float(hint))
    # prefer 80-160 BPM (log-normal around 115) against octave errors
    bpm = 60 / np.maximum(lags, 1e-6)
    w = np.exp(-0.5 * (np.log2(bpm / 115) / 0.9) ** 2)
    score = np.where(ok, ac * w, -np.inf)
    k = int(np.argmax(score))
    # parabolic refinement of the lag
    if 0 < k < len(ac) - 1:
        a, b, c = ac[k - 1], ac[k], ac[k + 1]
        d = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0
        k = k + d
    return refine(onset, fps, 60 * fps / k)


def refine(onset, fps, bpm):
    """Fine-tune the tempo (+-3 %, 0.05 BPM steps): the comb of beats that
    collects the most onset over the WHOLE track. A 1 % error drifts a
    beat by 2-3 s over a 3-minute track - too much to cut on."""
    o = onset - onset.mean()
    n = len(o)
    best = (-np.inf, bpm)
    for b in np.arange(bpm * 0.97, bpm * 1.03, 0.05):
        period = 60 / b * fps
        pos = np.arange(0, n - 1, period)
        k = len(pos)
        # every phase at once: sample o at pos + phase (linear interpolation)
        ph = np.arange(0, period, 1.0)
        idx = pos[None, :] + ph[:, None]
        i0 = np.minimum(idx.astype(int), n - 2)
        fr = idx - i0
        val = (o[i0] * (1 - fr) + o[i0 + 1] * fr).sum(1) / k
        if val.max() > best[0]:
            best = (val.max(), b)
    return float(best[1])


def track_beats(onset, fps, bpm):
    period = 60 / bpm * fps
    n = len(onset)
    # best phase of a fixed comb
    phases = np.arange(int(period))
    score = [onset[np.arange(p, n, period).astype(int)].sum() for p in phases]
    t = float(phases[int(np.argmax(score))])
    beats = []
    while t < n:
        lo, hi = int(t - 0.1 * period), int(t + 0.1 * period) + 1
        seg = onset[max(0, lo):min(n, hi)]
        if len(seg) and seg.max() > onset.mean():
            t = 0.5 * t + 0.5 * (max(0, lo) + int(np.argmax(seg)))   # half-way to the real onset
        beats.append(t)
        t += period
    return np.array(beats) / fps


def closure(frame_db, fps, med, bars):
    """The track's own ending: its LAST loud attack (the final chord / hit) and how it rings out.
    {"t": the attack (s), "ring": seconds until the sound is gone, "strength": 0..1, "what"}.
    Strong = as loud as the body of the track, a clear attack, nothing louder after it, and it
    dies within a few seconds; a slow fade-out (the track sinks for bars first) scores low."""
    sm = np.convolve(frame_db, np.ones(5) / 5, "same")             # ~50 ms smoothing
    n = len(sm)
    alive = np.nonzero(sm > med - 40)[0]
    if not len(alive):
        return {"t": None, "ring": 0.0, "strength": 0.0, "what": "tiho"}
    e = int(alive[-1])
    end_t = e / fps
    d = max(1, int(0.1 * fps))
    rise = np.full(n, -99.0)
    rise[d:] = sm[d:] - sm[:-d]
    lo = max(d, int((end_t - 12) * fps))
    # attacks: a rise of >= 2 dB in 0.1 s while loud (within 6 dB of the track's median bar)
    cand = [k for k in range(lo, e) if rise[k] >= 2 and sm[k] >= med - 6
            and rise[k] == rise[max(0, k - d):k + d].max()]
    if not cand:
        return {"t": None, "ring": 0.0, "strength": 0.0, "what": "utapa se (nema završnog udarca)"}
    k = cand[-1]
    pk = k + int(np.argmax(sm[k:k + int(0.25 * fps)]))               # the attack's peak
    t = k / fps - 0.05
    ring = end_t - t
    level = sm[pk]
    after = sm[pk + int(0.4 * fps):e].max() if e > pk + int(0.4 * fps) else level - 20
    loud = float(np.clip((level - (med - 6)) / 6, 0, 1))
    attack = float(np.clip(rise[k] / 6, 0, 1))
    clean = 1.0 if after <= level + 1 else 0.3                       # nothing re-attacks after it
    ringf = 1.0 if 0.3 <= ring <= 6 else 0.5 if ring <= 10 else 0.2   # dies away, not a long fade
    # the track sinking for bars before the "ending" = a fade-out with one last bump
    body = sm[max(0, k - int(8 * fps)):max(1, k - int(4 * fps))]
    sinking = bool(len(body)) and np.median(body) - level > 6
    s = loud * (0.5 + 0.5 * attack) * clean * ringf * (0.3 if sinking else 1.0)
    on = bool(len(bars)) and np.abs(np.asarray(bars) - t).min() <= 0.08
    what = ("završni udarac" if ring < 1.2 else "završni akord odzvoni") + (" na taktu" if on else "")
    if s < 0.5:
        what = "utapa se" if sinking else "slab kraj"
    return {"t": round(float(t), 3), "ring": round(float(ring), 2), "strength": round(float(min(1.0, s)), 2),
            "what": what, "on_bar": bool(on)}


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("track")
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--out")
    ap.add_argument("--png")
    ap.add_argument("--drums", help="drum stem of the same track (beats and bars from it)")
    ap.add_argument("--bass", help="bass stem of the same track (bass level per bar)")
    a = ap.parse_args()

    x = load(a.track)
    dur = len(x) / SR
    S = stft_mag(x)
    fps = SR / HOP
    freqs = np.fft.rfftfreq(NFFT, 1 / SR)
    L = np.log1p(S * 10)
    flux = np.maximum(np.diff(L, axis=0), 0)
    onset = np.concatenate([[0], flux.sum(1)])
    low = freqs < 150
    onset_low = np.concatenate([[0], flux[:, low].sum(1)])

    def stem(path):
        y = load(path)
        y = np.pad(y, (0, max(0, len(x) - len(y))))[:len(x)]
        Sy = stft_mag(y)[:len(S)]
        Sy = np.pad(Sy, ((0, len(S) - len(Sy)), (0, 0)))
        fy = np.maximum(np.diff(np.log1p(Sy * 10), axis=0), 0)
        return Sy, np.concatenate([[0], fy.sum(1)]), np.concatenate([[0], fy[:, low].sum(1)])

    beat_onset = onset
    if a.drums:      # the drum stem alone: kicks and snares without the melody's onsets
        _, beat_onset, onset_low = stem(a.drums)
    bpm = tempo(beat_onset, fps, a.bpm)
    beats = track_beats(beat_onset, fps, bpm)
    bi = np.clip((beats * fps).astype(int), 0, len(onset) - 1)
    # downbeat phase: most low-end onset around the beat
    lowpk = np.array([onset_low[max(0, i - 2):i + 3].max() for i in bi])
    phase = int(np.argmax([lowpk[p::4].mean() for p in range(4)]))
    downbeats = beats[phase::4]
    bars = np.concatenate([[0.0] if downbeats[0] > 0.3 else [], downbeats])

    # per-bar features
    power = (S ** 2)
    nfr = len(S)
    fr = x[:nfr * HOP].reshape(nfr, HOP) if len(x) >= nfr * HOP else np.pad(x, (0, nfr * HOP - len(x))).reshape(nfr, HOP)
    frame_db = 10 * np.log10((fr.astype(np.float64) ** 2).mean(1) + 1e-10)   # dBFS per hop
    low_db = frame_db + 10 * np.log10(power[:, low].sum(1) / (power.sum(1) + 1e-10) + 1e-10)
    cent = (power * freqs).sum(1) / (power.sum(1) + 1e-10)
    pc = np.round(12 * np.log2(np.maximum(freqs, 1) / 440) + 69).astype(int) % 12
    band = (freqs > 60) & (freqs < 4000)
    chroma = np.stack([power[:, band & (pc == k)].sum(1) for k in range(12)], 1)
    bass_db = None
    if a.bass:
        Sb = stem(a.bass)[0]
        bass_db = 10 * np.log10((Sb ** 2).sum(1) / (power.sum(1).mean() + 1e-10) + 1e-10)
    feats, rows = [], []
    edges = list(bars) + [dur]
    for i in range(len(bars)):
        f0, f1 = int(edges[i] * fps), max(int(edges[i] * fps) + 1, int(edges[i + 1] * fps))
        sl = slice(f0, min(f1, len(frame_db)))
        if sl.start >= len(frame_db):
            break
        db = 10 * np.log10(np.mean(10 ** (frame_db[sl] / 10)))
        ldb = 10 * np.log10(np.mean(10 ** (low_db[sl] / 10)))
        br = float(np.mean(cent[sl]))
        dens = float((onset[sl] > onset.mean() + onset.std()).mean())
        ch = chroma[sl].sum(0)
        ch = ch / (np.linalg.norm(ch) + 1e-9)
        rows.append({"t": round(float(edges[i]), 2), "db": round(float(db), 1), "low_db": round(float(ldb), 1),
                     "bright": round(br), "density": round(dens, 2)})
        if bass_db is not None:
            rows[-1]["bass_db"] = round(float(10 * np.log10(np.mean(10 ** (bass_db[sl] / 10)))), 1)
        feats.append(np.concatenate([[db / 6, ldb / 6, br / 600, dens * 4], ch * 1.5]))
    F = np.array(feats)
    nb = len(F)

    # novelty from a checkerboard kernel over bar self-similarity
    Fn = (F - F.mean(0)) / (F.std(0) + 1e-9)
    D = np.linalg.norm(Fn[:, None] - Fn[None], axis=2)
    Ssim = np.exp(-D / (np.median(D) + 1e-9))
    K = 4
    kern = np.kron([[1, -1], [-1, 1]], np.ones((K, K)))
    nov = np.zeros(nb)
    for i in range(K, nb - K):
        nov[i] = (Ssim[i - K:i + K, i - K:i + K] * kern).sum()
    nov = np.maximum(nov, 0)
    floor = nov[nov > 0].mean() if (nov > 0).any() else np.inf
    cand = [i for i in range(K, nb - K) if nov[i] == nov[max(0, i - 2):i + 3].max() and nov[i] > floor]
    # snap to 4-bar phrases when close, keep >= 4 bars apart
    dbs = np.array([r["db"] for r in rows])
    # sections are 8+ bars (music moves in 8-bar phrases), except where the
    # loudness really jumps (a hit / a drop) - that always starts a section
    jumps = [i for i in range(1, nb) if abs(dbs[i] - dbs[i - 1]) >= 4]
    bounds = []
    for i in sorted(jumps, key=lambda i: -abs(dbs[i] - dbs[i - 1])) + sorted(cand, key=lambda i: -nov[i]):
        j = i if i in jumps else (int(round(i / 4) * 4) if abs(i - round(i / 4) * 4) <= 1 else i)
        gap = 4 if i in jumps else 8
        if all(abs(j - b) >= gap for b in bounds) and 0 < j < nb:
            bounds.append(j)
    bounds = sorted(bounds)
    # merge neighbours that sound the same (within 2 dB, no jump between)
    merged = []
    for b in bounds:
        prev = merged[-1] if merged else 0
        nxt = bounds[bounds.index(b) + 1] if bounds.index(b) + 1 < len(bounds) else nb
        if b not in jumps and abs(dbs[prev:b].mean() - dbs[b:nxt].mean()) < 2:
            continue
        merged.append(b)
    # a 1-bar scrap at the end (silence after the last note) joins the section before
    bounds = [b for b in merged if nb - b >= 2]

    lo_q, hi_q = np.percentile(dbs, 33), np.percentile(dbs, 67)
    hits = [i for i in range(1, nb) if dbs[i] - dbs[i - 1] >= 4]
    sections = []
    se = [0] + bounds + [nb]
    for s0, s1 in zip(se, se[1:]):
        seg = dbs[s0:s1]
        m = float(seg.mean())
        level = "low" if m < lo_q else "high" if m > hi_q else "mid"
        slope = np.polyfit(np.arange(len(seg)), seg, 1)[0] * len(seg) if len(seg) > 2 else 0
        shape = "build" if slope > 4 else "falling" if slope < -4 else "steady"
        sections.append({"start": rows[s0]["t"], "end": round(float(edges[s1]), 2), "bars": s1 - s0,
                         "db": round(m, 1), "level": level, "shape": shape})
    # the run-up into each hit: bars before it where the music keeps rising
    # (a dip of up to 1 dB is allowed), at least 3 dB in all
    builds = []
    for h in hits:
        k = h - 1
        while k > 0 and dbs[k] - dbs[k - 1] > -1 and h - k < 16:
            k -= 1
        if h - k >= 2 and dbs[h - 1] - dbs[k] >= 3:
            builds.append({"start": rows[k]["t"], "hit": rows[h]["t"], "bars": h - k,
                           "rise_db": round(float(dbs[h - 1] - dbs[k]), 1)})

    # the bass coming in / dropping out (>= 8 dB bar to bar) - a section change the full mix can hide
    bass_ev = []
    if bass_db is not None:
        bd = [r["bass_db"] for r in rows]
        bass_ev = [{"t": rows[i]["t"], "kind": "in" if bd[i] > bd[i - 1] else "out"}
                   for i in range(1, nb) if abs(bd[i] - bd[i - 1]) >= 8 and max(bd[i], bd[i - 1]) > -40]

    # place in the 4-bar phrase, counted from each section's start
    sec_of = np.searchsorted(np.array(se[1:]), np.arange(nb), side="right")
    phrase = [(i - se[sec_of[i]]) % 4 for i in range(nb)]
    for i in range(nb):
        rows[i]["phrase"] = int(phrase[i])

    # joins: play bar i, then bar j instead of i + 1. The bars around the seam
    # must sound alike (j like i+1, j-1 like i) and so must the spectrum right
    # at it (the last 70 ms of i like the last 70 ms of j-1, the first 70 ms of
    # j like the first of i+1). Normalised so the median jump costs 1.
    sf = lambda t: min(len(L) - 1, max(0, int(round(t * fps))))
    head = np.array([L[sf(edges[i]):sf(edges[i]) + 3].mean(0) for i in range(nb)])
    tailv = np.array([L[max(0, sf(edges[i + 1]) - 3):sf(edges[i + 1])].mean(0) if sf(edges[i + 1]) > sf(edges[i])
                      else head[i] for i in range(nb)])
    Dsp = lambda A, B: np.linalg.norm(A[:, None] - B[None], axis=2)
    joins = []
    if nb > 3:
        I = np.arange(nb - 1)                    # bar i has a natural next bar i+1
        J = np.arange(1, nb)                     # bar j has a natural previous bar j-1
        c_ctx = 0.5 * (D[np.ix_(I + 1, J)] + D[np.ix_(I, J - 1)])
        c_seam = 0.5 * (Dsp(tailv[I], tailv[J - 1]) + Dsp(head[J], head[I + 1]))
        cost = c_ctx / (np.median(c_ctx) + 1e-9) * 0.6 + c_seam / (np.median(c_seam) + 1e-9) * 0.4
        cost += 0.3 * (np.array(phrase)[J][None, :] != np.array(phrase)[I + 1][:, None])
        for ii in I:
            order = np.argsort(cost[ii])
            for jj in order[:12]:
                j = int(J[jj])
                if j != ii + 1 and cost[ii, jj] < 1.2:
                    joins.append([int(ii), j, round(float(cost[ii, jj]), 2)])
    close = closure(frame_db, fps, float(np.median([r["db"] for r in rows])), bars)
    ending = "hard" if close["strength"] >= 0.5 else "fade"

    out = {"track": a.track, "duration": round(dur, 2), "bpm": round(bpm, 1),
           "bar_seconds": round(240 / bpm, 3), "beats": [round(float(b), 3) for b in beats],
           "downbeats": [round(float(b), 3) for b in bars], "bars": rows, "sections": sections,
           "hits": [rows[i]["t"] for i in hits], "builds": builds, "bass": bass_ev, "ending": ending,
           "closure": close,
           "stems": {k: v for k, v in (("drums", a.drums), ("bass", a.bass)) if v}, "joins": joins}
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)

    mmss = lambda t: f"{int(t // 60)}:{t % 60:05.2f}"
    print(f"{a.track}: {mmss(dur)}, {bpm:.1f} BPM (bar {240 / bpm:.2f}s), {len(rows)} bars, ending: {ending} ({close['what']}, {close['strength']:.2f})")
    if not a.bpm:
        print(f"  (half/double tempo would be {bpm / 2:.1f} / {bpm * 2:.1f} - pass --bpm if the metadata says so)")
    print("  section          bars  level  shape    dB")
    for s in sections:
        print(f"  {mmss(s['start'])}-{mmss(s['end'])}  {s['bars']:4d}  {s['level']:5s}  {s['shape']:7s} {s['db']:6.1f}")
    print("  hits (>= +4 dB from the bar before):", ", ".join(mmss(rows[i]["t"]) for i in hits) or "none")
    if builds:
        print("  builds into a hit:", ", ".join(f"{mmss(b['start'])} ({b['bars']} bars, +{b['rise_db']:.0f} dB)"
                                                 for b in builds))
    if bass_ev:
        print("  bass:", ", ".join(f"{e['kind']} {mmss(e['t'])}" for e in bass_ev))
    good = [c for c in joins if c[2] < 0.5]
    print(f"  joins: {len(good)} near-seamless jumps (cost < 0.5) of {len(joins)} listed"
          + (f"; stems: {', '.join(k for k in ('drums', 'bass') if getattr(a, k))}" if (a.drums or a.bass) else ""))

    if a.png:
        W, H = 1600, 360
        img = np.full((H, W, 3), 250, np.uint8)
        top, bot = 20, H - 40
        lo_db, hi_db = dbs.min() - 3, dbs.max() + 1
        xs = lambda t: int(t / dur * (W - 1))
        ys = lambda d: int(bot - (d - lo_db) / (hi_db - lo_db) * (bot - top))
        colors = {"low": (170, 200, 235), "mid": (110, 160, 220), "high": (40, 90, 180)}
        for s in sections:
            img[top:bot, xs(s["start"]):xs(s["end"])] = (np.array(colors[s["level"]]) * 0.25 + 190).astype(np.uint8)
        for i, r in enumerate(rows):
            x0, x1 = xs(r["t"]), max(xs(r["t"]) + 1, xs(edges[i + 1]) - 1)
            sec = next(s for s in sections if s["start"] <= r["t"] < s["end"] + 1e-6)
            img[ys(r["db"]):bot, x0:x1] = colors[sec["level"]]
        for s in sections[1:]:
            img[top:bot + 10, xs(s["start"]):xs(s["start"]) + 2] = (30, 30, 30)
        for i in hits:
            x0 = xs(rows[i]["t"])
            img[top:top + 14, max(0, x0 - 6):x0 + 7] = (220, 60, 40)
        for m in range(0, int(dur) + 1, 15):
            img[bot:bot + (14 if m % 60 == 0 else 7), xs(m)] = (0, 0, 0)
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", f"{W}x{H}", "-i", "-", "-frames:v", "1", a.png], input=img.tobytes(), check=True)
        print(f"  plot -> {a.png} (bars = loudness per bar, shade = section level, red = hit, ticks = 15 s)")


if __name__ == "__main__":
    main()
