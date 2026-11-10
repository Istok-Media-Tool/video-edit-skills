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
- optional sting (--sting file.wav): an impact/whoosh at --sting-at seconds
  (default: right after that silence), at -5 dBFS peak like the references
- the mix is brought to -14 LUFS (Instagram) with one gain, peaks limited to -2 dB (AAC adds ~1 dB)

The voice is never touched by the bed (amix normalize=0 - see SKILL.md,
Step 4), only the final loudness pass scales everything together.

Usage:
  mix_bed.py video.mp4 track.mp3 out.mp4 --words words.json
      [--track-start 12.0] [--under 22] [--lift 8] [--fade 1.2] [--gap 0.5]
      [--sting hit.wav] [--sting-at 101.3]

--words: word_times.py / stt.py output for THIS video (last word end = where
the speech stops). Without it pass --last-word <sec>.
"""
import argparse
import json
import re
import subprocess
import sys


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
    ap.add_argument("--lift", type=float, default=8.0, help="dB the music comes up after the last word")
    ap.add_argument("--fade", type=float, default=1.2)
    ap.add_argument("--gap", type=float, default=0.5, help="silence after the music, before the end")
    ap.add_argument("--sting")
    ap.add_argument("--sting-at", type=float)
    a = ap.parse_args()

    dur = probe_dur(a.video)
    lw = a.last_word if a.last_word is not None else last_word_end(a.words) if a.words else None
    if lw is None:
        sys.exit("pass --words or --last-word")
    voice = mean_db(a.video, 0, lw)
    music = mean_db(a.track, a.track_start, a.track_start + dur, stream="0:a")
    gain = voice - a.under - music
    end_music = dur - a.gap if not a.sting else (a.sting_at or dur - 1.5) - a.gap
    fade_st = max(lw + 0.3, end_music - a.fade)
    print(f"voice {voice:.1f} dB, music {music:.1f} dB -> music gain {gain:+.1f} dB; "
          f"last word {lw:.2f}s, lift to +{a.lift} dB, fade {fade_st:.2f}-{end_music:.2f}s", file=sys.stderr)

    lift = (f"volume='if(lt(t,{lw:.3f}),1,if(lt(t,{lw + 0.4:.3f}),1+({10 ** (a.lift / 20):.4f}-1)*(t-{lw:.3f})/0.4,"
            f"{10 ** (a.lift / 20):.4f}))':eval=frame")
    fc = (f"[1:a]atrim={a.track_start}:{a.track_start + dur},asetpts=PTS-STARTPTS,aresample=48000,"
          f"volume={gain:.2f}dB,afade=t=in:st=0:d=0.5,{lift},"
          f"afade=t=out:st={fade_st:.3f}:d={max(0.1, end_music - fade_st):.3f},"
          f"atrim=0:{dur:.3f}[m];[0:a]aresample=48000[v]")
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
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", a.video, "-i", tmp,
                    "-af", f"volume={gain:.2f}dB,{limit}",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", a.out],
                   check=True)
    import os
    os.remove(tmp)
    print(f"loudness gain {gain:+.1f} dB -> -14 LUFS", file=sys.stderr)
    print(f"-> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
