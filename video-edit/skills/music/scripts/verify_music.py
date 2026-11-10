#!/usr/bin/env python3
"""
Check a re-arranged / edited music track before it goes under the video -
measured on the audio itself, not taken from the plan.

- accents: where each main accent's event REALLY landed. The source bar's
  first 0.3 s (from arrange.json) is found in the new track by
  cross-correlation around where it should be; the error is in ms.
- Epidemic Sound edits (--regions, the EditRecording input): each required
  region of the original is searched for in the edit (+-3 s) - did it land
  at offsetMsInEdit?
- seams (the joins in arrange.json, or --joins t1,t2 by hand): a click
  (the sharpest sample of a steep high-pass within +-3 ms, 6 dB over the
  loudest ones in the 300 ms around it), a level jump
  and a jump in timbre across the seam, each compared with this track's own
  natural bar lines. A seam that stands out is listed to listen to.
- gaps: a stretch over 60 ms more than 40 dB under the track's level where
  the source is NOT that quiet (with --arrange: at the mapped source time;
  without: where the 300 ms on both sides are loud) - a render hole, not a
  rest the music has anyway.
- length against the expected one.

Exit 1 when a main accent is more than 40 ms off, a region missed by more
than 40 ms, there is a gap, or a seam clicks; seams that only stand out in
level / timbre are printed as "preslušaj" (listen) without failing.

Usage:
  verify_music.py arr_A.wav --arrange arrange.json [--variant A] [--source track.wav]
  verify_music.py edit.wav --regions epidemic_request.json --source full.wav
  verify_music.py any.wav --joins 12.3,20.1 [--expect-len 47.5]
"""
import argparse
import json
import subprocess
import sys

import numpy as np

SR = 22050


def load(path):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def find(snippet, y, expect, window):
    """Where (s) the snippet best matches in y within expect +- window; and how well (0..1)."""
    a = max(0, int((expect - window) * SR))
    b = min(len(y), int((expect + window) * SR) + len(snippet))
    seg = y[a:b]
    if len(seg) < len(snippet) + 1:
        return None, 0.0
    n = 1 << int(np.ceil(np.log2(len(seg) + len(snippet))))
    c = np.fft.irfft(np.fft.rfft(seg, n) * np.conj(np.fft.rfft(snippet, n)), n)[:len(seg) - len(snippet) + 1]
    e = np.sqrt(np.convolve(seg ** 2, np.ones(len(snippet)), "valid")[:len(c)] + 1e-12)
    r = c / (e * np.linalg.norm(snippet) + 1e-12)
    k = int(np.argmax(r))
    return (a + k) / SR, float(r[k])


def hp(x):
    """first difference twice ~ a steep high-pass: what a click is made of"""
    return np.diff(x, 2, prepend=[0, 0])


def seam_stats(y, t, n_ms=100):
    i = int(t * SR)
    w = int(n_ms / 1000 * SR)
    pre, post = y[max(0, i - w):i], y[i:i + w]
    if len(pre) < w // 2 or len(post) < w // 2:
        return None
    db = lambda v: 10 * np.log10(np.mean(v ** 2) + 1e-12)
    level = abs(db(post) - db(pre))
    spec = lambda v: np.log1p(np.abs(np.fft.rfft(v * np.hanning(len(v)), 2048)))
    timbre = float(np.linalg.norm(spec(post) - spec(pre)) / np.sqrt(1025))
    h = hp(y[max(0, i - int(0.15 * SR)):i + int(0.15 * SR)])
    c = len(h) // 2
    k = int(0.003 * SR)
    around = np.abs(np.concatenate([h[:c - 4 * k], h[c + 4 * k:]]))
    # the seam's sharpest sample against the loudest ones around it (99.5th percentile)
    click = 20 * np.log10((np.abs(h[c - k:c + k]).max() + 1e-9) / (np.percentile(around, 99.5) + 1e-9)) if len(around) else 0.0
    return {"level": level, "timbre": timbre, "click": float(click)}


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("wav")
    ap.add_argument("--arrange")
    ap.add_argument("--variant", default="A")
    ap.add_argument("--source", help="the audio the arrangement was cut from (default: the map's track)")
    ap.add_argument("--regions", help="EditRecording input json (requiredRegionsAtOffsets)")
    ap.add_argument("--joins", help="seam times (s) to check by hand: 12.3,20.1")
    ap.add_argument("--expect-len", type=float)
    a = ap.parse_args()

    y = load(a.wav)
    dur = len(y) / SR
    problems, listen = [], []
    print(f"{a.wav}: {dur:.2f}s")

    P, src = None, None
    if a.arrange:
        A = json.load(open(a.arrange))
        P = next(p for p in A["plans"] if p.get("label", "A") == a.variant)
        src = load(a.source or A["track"])
        exp = a.expect_len or P["length"]
    else:
        exp = a.expect_len
    if a.regions:
        R = json.load(open(a.regions))
        R = R.get("input", R)
        src = load(a.source) if a.source else None
        if src is None:
            sys.exit("--regions needs --source (the original full track)")
        exp = exp or R["targetDurationMs"] / 1000
    if exp:
        ok = abs(dur - exp) < 0.05
        print(f"  dužina {dur:.2f}s (očekivano {exp:.2f}s) {'OK' if ok else '--'}")
        if abs(dur - exp) >= 0.5 or (not ok and not a.regions):
            problems.append(f"dužina {dur:.2f}s umesto {exp:.2f}s")
        elif not ok:
            listen.append(f"dužina {dur:.2f}s (Epidemic bez forceDuration - rep je kraći/duži)")

    # accents of an arrangement
    if P:
        segs = P["segments"]
        for x in P["accents"]:
            if x.get("src_t") is None:
                continue
            seg = next((s for s in segs if s["src"] == x["bar"] and abs(s["o0"] - (x["t"] - 0.03)) < 0.01), None)
            if seg is None:
                continue
            # 0.3 s: long enough to be unique, short enough that a 1-4 % stretch can't smear it
            snip = src[int(x["src_t"] * SR):int((x["src_t"] + 0.3) * SR)]
            at, q = find(snip, y, seg["o0"], 0.12)
            if at is None:
                problems.append(f"„{x['word']}“: nije pronađen")
                continue
            err = (at - seg["o0"]) * 1000
            ok = abs(err) <= 40 and q > 0.3          # a stretched or quiet bar matches less than 1
            print(f"  {'OK' if ok else '--'} {x['kind']:8s} „{x['word']}“ {x['lands']}: {err:+.0f} ms (sličnost {q:.2f})")
            if not ok:
                problems.append(f"„{x['word']}“ {err:+.0f} ms")
    # Epidemic edit regions
    errs = []
    if a.regions:
        for r in R.get("requiredRegionsAtOffsets") or []:
            s0 = r["startMs"] / 1000
            snip = src[int(s0 * SR):int((s0 + 1.0) * SR)]
            want = r["offsetMsInEdit"] / 1000
            at, q = find(snip, y, want, 3.0)
            err = None if at is None else (at - want) * 1000
            ok = err is not None and abs(err) <= 40 and q > 0.5
            if err is not None and q > 0.5:
                errs.append(err)
            print(f"  {'OK' if ok else '--'} deo {s0:.2f}s originala -> u verziji na "
                  f"{'?' if at is None else f'{at:.3f}s'} (traženo {want:.3f}s, {'' if err is None else f'{err:+.0f} ms, '}sličnost {q:.2f})")
            if not ok:
                problems.append(f"deo sa {s0:.2f}s nije na {want:.3f}s")
        # Epidemic places regions on its own grid: one shift of the whole edit can fix them all
        if errs:
            shift = float(np.median(errs)) / 1000
            left = [e / 1000 - shift for e in errs]
            fixed = all(abs(e) <= 0.04 for e in left)
            print(f"  pomak cele verzije: {shift * 1000:+.0f} ms -> mix_bed.py --track-start {shift:.3f}"
                  + (" (posle toga svi delovi na mestu)" if fixed else
                     f" (i posle toga: {', '.join(f'{e * 1000:+.0f} ms' for e in left)})"))
            if fixed:
                problems = [p for p in problems if not p.startswith("deo sa")]
            print(f"SHIFT {shift:.3f}")

    # seams, against the track's own bar lines
    joins = [j["t"] for j in P["joins"]] if P else []
    if a.joins:
        joins += [float(t) for t in a.joins.split(",")]
    if joins:
        bars = [s["o0"] for s in P["segments"]] if P else []
        natural = [t for t in bars if all(abs(t - j) > 0.05 for j in joins) and 0.2 < t < dur - 0.2]
        ref = [seam_stats(y, t) for t in natural]
        ref = [r for r in ref if r]
        lv = np.percentile([r["level"] for r in ref], 90) if ref else 3.0
        tb = np.percentile([r["timbre"] for r in ref], 90) if ref else 1.0
        for t in joins:
            st = seam_stats(y, t)
            if not st:
                continue
            flags = []
            if st["click"] > 6:
                flags.append(f"klik +{st['click']:.0f} dB")
            if st["level"] > max(3.0, lv * 1.5):
                flags.append(f"skok jačine {st['level']:.1f} dB")
            if st["timbre"] > tb * 1.5:
                flags.append("promena boje")
            m = int(t // 60)
            print(f"  spoj {m}:{t % 60:05.2f}: {'OK' if not flags else ', '.join(flags)}")
            if any(f.startswith("klik") for f in flags):
                problems.append(f"klik na spoju {t:.2f}s")
            elif flags:
                listen.append(t)

    # gaps inside the music
    w = int(0.02 * SR)
    fr = y[:len(y) // w * w].reshape(-1, w)
    db = 10 * np.log10((fr ** 2).mean(1) + 1e-12)
    ref_db = np.percentile(db, 60)
    quiet = db < ref_db - 40
    run, gaps = 0, []
    if P:
        s_db = lambda st: 10 * np.log10(np.mean(src[int(st * SR):int(st * SR) + 3 * w] ** 2) + 1e-12)   # the same 60 ms
    for k, qv in enumerate(quiet):
        run = run + 1 if qv else 0
        t = (k - 2) * w / SR
        if run != 3 or not (0.5 < t < dur - 3):
            continue
        if P:
            seg = [g for g in P["segments"] if g["o0"] <= t < g["o0"] + g["len"] * g["ratio"]]
            if seg:
                g = seg[-1]
                sd = s_db(g["s0"] + (t - g["o0"]) / g["ratio"])
                if sd < ref_db - 35 or db[k - 2:k + 1].mean() > sd - 12:
                    continue                      # the source rests here too (or fades into a break)
        else:
            ctx = lambda a_, b_: db[max(0, a_):max(0, b_)].mean() if b_ > a_ else -200
            if ctx(k - 17, k - 2) < ref_db - 20 or ctx(k + 1, k + 16) < ref_db - 20:
                continue
        gaps.append(t)
    for t in gaps:
        # without a map of the source a rest of the music can't be told from a hole: listen
        (problems if P else listen).append(f"rupa u muzici na {t:.2f}s" if P else t)
    print(f"  rupe: {'nema' if not gaps else ', '.join(f'{t:.2f}s' for t in gaps)}")

    if listen:
        print("  preslušaj: " + ", ".join(f"{t:.2f}s" if isinstance(t, float) else str(t) for t in listen))
    if problems:
        print("PROBLEM: " + "; ".join(problems))
        sys.exit(1)
    print("OK - nothing found")


if __name__ == "__main__":
    main()
