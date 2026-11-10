#!/usr/bin/env bash
# Cut a list of (start,end[,vf]) segments out of a source video and
# concatenate them into one final video, in the order given.
#
# This script exists because non-obvious ffmpeg/bash gotchas bit us the
# first few times this was done by hand - bake the fixes in so they don't
# need rediscovering:
#
#   1. ffmpeg reads stdin by default (for interactive 'q to quit' etc.), even
#      when run non-interactively. A `while read ...; done < file` loop that
#      calls ffmpeg will have its OWN input lines silently stolen by ffmpeg,
#      corrupting which timestamp gets applied to which clip. Fix: every
#      ffmpeg call here uses -nostdin AND redirects stdin from /dev/null.
#
#   2. A hard cut right at the detected end of speech, combined with ANY
#      audio fade-out, audibly eats the last letter/syllable of a sentence.
#      Fix: generous trailing padding (default 0.35s) and NO fade-out at all -
#      only a tiny (5ms) fade-IN, just enough to prevent a click/pop at the
#      start of the clip.
#
#   4. Joining clips with the concat DEMUXER (-c copy) placed each clip by
#      its container duration, not its frames. AAC audio is a few ms shorter
#      or longer than the video, so joins got 2-frame timestamp holes (a held
#      / stray frame at the cut) and audio drifted ~20ms per clip - 0.4s over
#      22 clips, which also put close-ups and captions timed from summed
#      durations visibly off. Fix: every clip is cut to a WHOLE number of
#      frames with its audio padded/trimmed to exactly that length, and the
#      clips are joined with the concat FILTER (re-encode), so clip k starts
#      exactly at sum(frames before k) / fps. Use frame counts, never
#      container durations, for any timing built on this cut.
#
#   3. Stream-copying a cut (-c copy) only snaps to the nearest keyframe, which
#      is nowhere near accurate enough for word-level cuts. Fix: re-encode
#      every individual clip (libx264/aac), THEN concat those with -c copy
#      (safe once all clips share the same codec/parameters).
#
# Usage:
#   cut_and_concat.sh <source_video> <selections_file> <output.mp4> [workdir]
#
# selections_file: tab-separated per line, in the exact order they should
# appear in the final video (seconds, may have decimals):
#   start<TAB>end                  - plain cut, no extra video filter
#   start<TAB>end<TAB><vf-filter>  - cut with a video filter chain applied
#     (e.g. a crop/scale filter for a punch-in zoom - see the "zoom" skill)
#
# Env overrides: PRE_PAD (default 0.15), POST_PAD (default 0.35),
# CRF (default 18), FADE_IN (default 0.005)

set -euo pipefail

SRC="$1"
SELECTIONS="$2"
OUT="$3"
WORKDIR="${4:-$(mktemp -d)}"

PRE_PAD="${PRE_PAD:-0.15}"
POST_PAD="${POST_PAD:-0.35}"
CRF="${CRF:-18}"
FADE_IN="${FADE_IN:-0.005}"

mkdir -p "$WORKDIR/clips"
FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$SRC" | head -1 | cut -d, -f1)
: > "$WORKDIR/concat_list.txt"

i=0
while IFS=$'\t' read -r s e vf; do
  i=$((i + 1))
  n=$(printf "%03d" "$i")
  cs=$(python3 -c "print(max(0,$s-$PRE_PAD))")
  ce=$(python3 -c "print($e+$POST_PAD)")
  clip="$WORKDIR/clips/clip_${n}.mp4"

  vf_args=()
  if [ -n "${vf:-}" ] && [ "$vf" != "-" ]; then
    vf_args=(-vf "$vf")
  fi

  # whole frames; audio exactly as long as the video (see 4.)
  nfr=$(python3 -c "from fractions import Fraction as F; print(max(1, round(($ce-$cs)*F('$FPS'))))")
  dur=$(python3 -c "from fractions import Fraction as F; print(float($nfr/F('$FPS')))")
  ffmpeg -nostdin -y -ss "$cs" -i "$SRC" \
    ${vf_args[@]+"${vf_args[@]}"} -frames:v "$nfr" \
    -af "afade=t=in:st=0:d=${FADE_IN},apad,atrim=0:${dur},asetpts=PTS-STARTPTS" -t "$dur" \
    -c:v libx264 -preset medium -crf "$CRF" -pix_fmt yuv420p \
    -c:a aac -b:a 192k \
    "$clip" -loglevel error < /dev/null

  echo "file '$clip'" >> "$WORKDIR/concat_list.txt"
  echo "clip_${n}.mp4: ${cs} -> ${ce}${vf:+ (vf: $vf)}" >&2
done < "$SELECTIONS"

# Join with the concat FILTER (see 4.): frame-exact, no holes, no drift.
inputs=(); graph=""; k=0
while read -r _ f; do
  f="${f#\'}"; f="${f%\'}"
  inputs+=(-i "$f")
  # AAC adds up to 1024 samples of padding when decoded; trim to the
  # video's exact length or the concat filter holds frames to cover it
  vd=$(ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames -of csv=p=0 "$f" | head -1 | cut -d, -f1)
  vd=$(python3 -c "from fractions import Fraction as F; print(float($vd/F('$FPS')))")
  graph+="[$k:v]setpts=PTS-STARTPTS[v$k];[$k:a]atrim=0:$vd,asetpts=PTS-STARTPTS[a$k];"
  k=$((k + 1))
done < "$WORKDIR/concat_list.txt"
for ((j = 0; j < k; j++)); do graph+="[v$j][a$j]"; done
graph+="concat=n=$k:v=1:a=1[v][a]"
ffmpeg -nostdin -y "${inputs[@]}" -filter_complex "$graph" -map "[v]" -map "[a]" \
  -c:v libx264 -preset medium -crf "$CRF" -pix_fmt yuv420p -r "$FPS" -c:a aac -b:a 192k \
  "$OUT" -loglevel error < /dev/null

echo "Final video: $OUT" >&2
ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT" >&2
