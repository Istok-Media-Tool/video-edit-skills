#!/usr/bin/env python3
"""
Music bed + ending in the style of the user's reference reels (vodič stila,
2026-11-10), in one pass:

- the track runs under the WHOLE video, quiet: --under dB below the voice's
  own mean level (default 22, measured - the references sit 20-25 dB under,
  so no pause anywhere is dead silent)
- after the last word it comes UP (--lift dB) and holds while the speaker
  looks into the camera (the tail from basic's tighten_cuts.py --tail), then
  fades out (--fade s) and leaves --gap s of silence before the end
- a track that has its OWN ending (arrange_music.py ends every version on
  the track's final chord, right after the last word) is never faded: it
  comes up after the last word and rings out to its natural end - every
  video ends on a clear, emphasized closure (the user's rule). When the
  ring lasts past the video, the last frame is held until the music is
  gone (better: a real tail from tighten_cuts.py --tail).
- optional sting (--sting file.wav): an impact/whoosh at --sting-at seconds
  (default: right after that silence), at -5 dBFS peak like the references
- the mix is brought to -14 LUFS (Instagram) with one gain, peaks limited to -2 dB; the encoded
  file's true peak is measured and the limit lowered until it is <= -1 dBFS (AAC added 2.2 dB on a
  plosive in the Tesla reel)

- optional sound effects on the marked places (--sfx sfx.json): [{"file": "riser.wav",
  "at": 21.67, "align": "end", "peak_db": -10}, {"file": "hit.wav", "at": 30.17}] -
  "align": "start" (default) starts the sound at "at", "peak" puts its loudest
  50 ms there (a riser / whoosh into a poenta - its tail rings on after the hit),
  "end" makes the file end there; each is set to its peak_db (default -10 dBFS) - arrange_music.py
  lists where they are needed ("predlog efekta"), Epidemic / ElevenLabs make them

The voice is never touched by the bed (amix normalize=0 - see SKILL.md,
Step 4), only the final loudness pass scales everything together.

Usage:
  mix_bed.py video.mp4 track.mp3 out.mp4 --words words.json
      [--track-start 12.0] [--under 22] [--lift 8] [--fade 1.2] [--gap 0.5]
      [--sting hit.wav] [--sting-at 101.3] [--sfx sfx.json]

--words: word_times.py / stt.py output for THIS video (last word end = where
the speech stops). Without it pass --last-word <sec>.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from venc import venc


def probe_dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", path]).decode())


def mean_db(path, ss=None, to=None, stream="0:a"):
    cmd = ["ffmpeg", "-nostdin", "-hide_banner"]
    if ss is not None:
        cmd += ["-ss", str(ss)]
    if to is not None:
        cmd += ["-to", str(to)]
    cmd += ["-i", path, "-map", stream, "-af", "volumedetect", "-f", "null", "-"]
    err = subprocess.run(cmd, capture_output=True, text=True).stderr
    return float(re.search(r"mean_volume: (-?[\d.]+) dB", err).group(1))


def peak_time(path):
    """seconds from the start of a sound to its loudest 50 ms"""
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", "8000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    import array
    x = array.array("h", raw)
    w = 400
    best, at = -1, 0
    for i in range(0, max(1, len(x) - w), w // 2):
        e = sum(v * v for v in x[i:i + w])
        if e > best:
            best, at = e, i
    return (at + w / 2) / 8000


def last_word_end(path):
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, dict):
        d = d["words"]
    w = d[-1]
    return float(w["end"] if isinstance(w, dict) else w[2])


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("video")
    ap.add_argument("track")
    ap.add_argument("out")
    ap.add_argument("--words")
    ap.add_argument("--last-word", type=float)
    ap.add_argument("--track-start", type=float, default=0.0, help="where in the track the video starts")
    ap.add_argument("--under", type=float, default=22.0, help="music mean this many dB under the voice mean")
    ap.add_argument("--lift", type=float, help="dB the music comes up after the last word (default 8; with a "
                    "track that ends on its own: the final chord comes up to ~2 dB under the voice)")
    ap.add_argument("--fade", type=float, default=1.2)
    ap.add_argument("--gap", type=float, default=0.5, help="silence after the music, before the end")
    ap.add_argument("--sting")
    ap.add_argument("--sting-at", type=float)
    ap.add_argument("--sfx", help="json list of sound effects: file, at, align (start|end), peak_db")
    a = ap.parse_args()
    a.lift_auto = a.lift is None
    if a.lift is None:
        a.lift = 8.0

    dur = probe_dur(a.video)
    vdur = dur
    lw = a.last_word if a.last_word is not None else last_word_end(a.words) if a.words else None
    if lw is None:
        sys.exit("pass --words or --last-word")
    voice = mean_db(a.video, 0, lw)
    music = mean_db(a.track, max(0.0, a.track_start), max(0.0, a.track_start) + dur, stream="0:a")
    gain = voice - a.under - music
    # an arranged track ends by itself (on its final chord) within a few seconds after the video:
    # let it ring - no fade - and hold the last frame for as long as it rings
    t_len = probe_dur(a.track) - a.track_start
    ring = not a.sting and t_len <= dur + 6
    if ring:
        dur = max(dur, t_len)
        print(f"the track ends on its own at {t_len:.2f}s: rings out, no fade"
              + (f"; last frame held {dur - vdur:.2f}s" if dur > vdur + 0.02 else ""), file=sys.stderr)
    end_music = dur - a.gap if not a.sting else (a.sting_at or dur - 1.5) - a.gap
    fade_st = max(lw + 0.3, end_music - a.fade)
    ramp = 0.4
    if ring:
        end_music, fade_st = dur, dur - 0.05                  # only a click guard at the very end
        # the closure is emphasized: the final chord (right after the last word) comes up to
        # about the voice's own level (2 dB under), quickly, so it lands as a full hit
        if a.lift_auto:
            close_db = mean_db(a.track, max(0.0, a.track_start) + lw + 0.05,
                               max(0.0, a.track_start) + lw + 0.6, stream="0:a")
            a.lift = max(4.0, min(20.0, (voice - 2) - (close_db + gain)))
        ramp = 0.12
    elif end_music - lw < 1.0 and not a.sting:
        # no silent tail after the last word (tighten_cuts.py --tail not run): a lift would swell for
        # a moment and be cut off - keep the bed level and fade it out to the video's end instead
        print("no tail after the last word: no lift, music fades out to the end", file=sys.stderr)
        a.lift, end_music = 0.0, dur
        fade_st = max(0.0, dur - a.fade)
    print(f"voice {voice:.1f} dB, music {music:.1f} dB -> music gain {gain:+.1f} dB; "
          f"last word {lw:.2f}s, lift to +{a.lift:.1f} dB, fade {fade_st:.2f}-{end_music:.2f}s", file=sys.stderr)

    lift = (f"volume='if(lt(t,{lw:.3f}),1,if(lt(t,{lw + ramp:.3f}),1+({10 ** (a.lift / 20):.4f}-1)*(t-{lw:.3f})/{ramp},"
            f"{10 ** (a.lift / 20):.4f}))':eval=frame")
    # a negative start (an Epidemic edit whose regions landed early) delays the track instead
    head = (f"adelay={int(round(-a.track_start * 1000))}:all=1," if a.track_start < 0 else "")
    ts = max(0.0, a.track_start)
    fc = (f"[1:a]{head}atrim={ts}:{ts + dur},asetpts=PTS-STARTPTS,aresample=48000,"
          f"volume={gain:.2f}dB,afade=t=in:st=0:d=0.5,{lift},"
          f"afade=t=out:st={fade_st:.3f}:d={max(0.05, end_music - fade_st):.3f},"
          f"atrim=0:{dur:.3f}[m];[0:a]aresample=48000,apad=whole_dur={dur:.3f}[v]")
    ins = ["-i", a.video, "-i", a.track]
    mix = "[v][m]"
    n = 2
    if a.sting:
        at = a.sting_at if a.sting_at is not None else end_music + a.gap
        ins += ["-i", a.sting]
        peak = float(re.search(r"max_volume: (-?[\d.]+) dB", subprocess.run(
            ["ffmpeg", "-nostdin", "-i", a.sting, "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True).stderr).group(1))
        fc += (f";[2:a]aresample=48000,volume={-5 - peak:.2f}dB,adelay={int(at * 1000)}:all=1[s]")
        mix += "[s]"
        n = 3
        print(f"sting at {at:.2f}s", file=sys.stderr)
    for k, fx in enumerate(json.load(open(a.sfx)) if a.sfx else []):
        pk = float(re.search(r"max_volume: (-?[\d.]+) dB", subprocess.run(
            ["ffmpeg", "-nostdin", "-i", fx["file"], "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True).stderr).group(1))
        al = fx.get("align", "start")
        st = fx["at"] - (probe_dur(fx["file"]) if al == "end" else peak_time(fx["file"]) if al == "peak" else 0)
        cut = f"atrim={-st:.3f}," if st < 0 else ""          # starts before the video: drop its head
        ins += ["-i", fx["file"]]
        fc += (f";[{n}:a]aresample=48000,{cut}asetpts=PTS-STARTPTS,volume={fx.get('peak_db', -10) - pk:.2f}dB,"
               f"adelay={int(max(0, st) * 1000)}:all=1[x{k}]")
        mix += f"[x{k}]"
        n += 1
        print(f"sfx {fx['file']} ({al}) on {fx['at']:.2f}s, starts {st:.2f}s", file=sys.stderr)
    fc += f";{mix}amix=inputs={n}:duration=first:dropout_transition=0:normalize=0[a]"
    tmp = a.out + ".mix.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", *ins, "-filter_complex", fc,
                    "-map", "[a]", "-c:a", "pcm_s24le", tmp], check=True)
    # -14 LUFS with a linear gain + a peak limiter (loudnorm's one-pass mode
    # lands ~1 dB low and pumps). The limiter eats some loudness on an already
    # compressed voice, so the gain is measured after it and corrected twice.
    def lufs_of(af):
        err = subprocess.run(["ffmpeg", "-nostdin", "-i", tmp, "-af", f"{af}ebur128", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])

    # AAC cuts everything above ~16 kHz, which raises the peaks of noisy sounds
    # (a whoosh sting) after the limiter - so cut it first, then limit
    limit = "lowpass=f=16000,alimiter=limit=0.79:level=false"   # -2 dBFS
    gain = -14 - lufs_of("")
    for _ in range(2):
        gain += -14 - lufs_of(f"volume={gain:.2f}dB,{limit},")
    # AAC can still push a sharp plosive over the limit (+2.2 dB on the Tesla reel):
    # measure the encoded file's true peak and lower the limit by the overshoot
    lim_db = -2.0
    for _ in range(3):
        limit = f"lowpass=f=16000,alimiter=limit={10 ** (lim_db / 20):.4f}:level=false"
        held = dur > vdur + 0.02
        vargs = (["-vf", f"tpad=stop_mode=clone:stop_duration={dur - vdur + 0.05:.3f}", *venc(18),
                  "-pix_fmt", "yuv420p", "-t", f"{dur:.3f}"] if held else ["-c:v", "copy"])
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", a.video, "-i", tmp,
                        "-af", f"volume={gain:.2f}dB,{limit}",
                        "-map", "0:v", "-map", "1:a", *vargs, "-c:a", "aac", "-b:a", "192k", a.out],
                       check=True)
        err = subprocess.run(["ffmpeg", "-nostdin", "-i", a.out, "-map", "0:a", "-af", "ebur128=peak=true",
                              "-f", "null", "-"], capture_output=True, text=True).stderr
        tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)[-1])
        if tp <= -1.0:
            break
        print(f"true peak {tp:+.1f} dBFS after AAC - limiting at {lim_db - (tp + 1.2):.1f} dBFS", file=sys.stderr)
        lim_db -= tp + 1.2
    import os
    os.remove(tmp)
    print(f"loudness gain {gain:+.1f} dB -> -14 LUFS", file=sys.stderr)
    print(f"-> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
