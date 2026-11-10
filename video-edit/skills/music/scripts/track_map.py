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
- ending: "hard" (stops on a hit / held chord) or "fade".

Usage:
  track_map.py track.mp3 [--bpm 120] [--out map.json] [--png map.png]
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


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("track")
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--out")
    ap.add_argument("--png")
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

    bpm = tempo(onset, fps, a.bpm)
    beats = track_beats(onset, fps, bpm)
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
    tail = frame_db[int(max(0, dur - 6) * fps):]
    t_sl = np.polyfit(np.arange(len(tail)) / fps, tail, 1)[0] if len(tail) > 10 else 0
    ending = "fade" if t_sl < -3 else "hard"

    out = {"track": a.track, "duration": round(dur, 2), "bpm": round(bpm, 1),
           "bar_seconds": round(240 / bpm, 3), "beats": [round(float(b), 3) for b in beats],
           "downbeats": [round(float(b), 3) for b in bars], "bars": rows, "sections": sections,
           "hits": [rows[i]["t"] for i in hits], "ending": ending}
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)

    mmss = lambda t: f"{int(t // 60)}:{t % 60:05.2f}"
    print(f"{a.track}: {mmss(dur)}, {bpm:.1f} BPM (bar {240 / bpm:.2f}s), {len(rows)} bars, ending: {ending}")
    if not a.bpm:
        print(f"  (half/double tempo would be {bpm / 2:.1f} / {bpm * 2:.1f} - pass --bpm if the metadata says so)")
    print("  section          bars  level  shape    dB")
    for s in sections:
        print(f"  {mmss(s['start'])}-{mmss(s['end'])}  {s['bars']:4d}  {s['level']:5s}  {s['shape']:7s} {s['db']:6.1f}")
    print("  hits (>= +4 dB from the bar before):", ", ".join(mmss(rows[i]["t"]) for i in hits) or "none")

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
