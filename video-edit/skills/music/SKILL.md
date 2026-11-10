---
name: music
description: Add background music to a video - sourcing a track (e.g. from Epidemic Sound), picking the segment whose energy arc matches the video's content, and mixing it under the existing voice/audio so the music never competes with speech. Use this skill whenever the user wants muzika/music/soundtrack/background track added to a video, wants to change the music bed on a video that already has one, or asks to balance music vs. voice levels - even without naming ffmpeg or a specific music service (e.g. "dodaj muziku", "stavi neku pesmu u pozadini", "muzika je prejaka/preslaba"). Normally applied to a video that's already cut (**basic** skill) and may already have captions (**subtitle** skill) - don't assume those steps are also wanted just because this skill triggered.
---

# Adding background music

## Why this skill exists

Two things about this are easy to get wrong without checking: picking a
stretch of the track that actually matches how the video's own energy
moves, and mixing it so it sits under the voice rather than competing with
it. Both are checkable with plain `ffmpeg` loudness analysis instead of
guessing - this skill exists to make that the default instead of an
afterthought.

## Step 1: Get the music file

If the user wants to source from a licensed library (Epidemic Sound, etc.):

- The built-in browser pane has its own separate login/session from the
  user's regular browser (Chrome, Safari) - sign-ins don't carry over. If
  the user says they're "already logged in", that's almost always their
  regular browser, not this pane; open the site in the built-in browser
  pane and check whether it actually shows as logged in before assuming it
  does.
- Download links on these sites are session-authenticated - a direct
  `curl`/`wget` of the download URL from the shell (outside the browser's
  session) will just redirect to a login page, even with the right-looking
  URL and query params. Don't waste time trying to replicate the
  browser's auth in the shell.
- The built-in browser pane cannot reach the local filesystem for
  uploads (e.g. a "search by video" / "match my video" feature that wants
  you to drop a video file in) - it runs in a different environment than
  the shell. For that kind of feature, ask the user to do the upload
  themselves; Claude can drive everything else (search, browse, click
  download) up to that point.
- The simplest reliable path in practice: Claude searches/browses and
  narrows down candidates in the browser pane (reading track names,
  artists, genres/moods, durations - Claude cannot listen to audio to
  judge it), the user previews and picks one by ear, then either the user
  clicks Download themselves and sends Claude the resulting file, or
  Claude clicks Download and then checks common local download locations
  (`~/Downloads`, or wherever the user says their downloads land - it may
  not be the default folder) for the new file afterward.

If the user already has a file or sends one directly, skip straight to
Step 2 with that path.

## Step 2: Pick the segment that matches the video's arc

Don't default to "just use the first N seconds" or silently loop/trim
without checking what's actually in that window. A track - especially
anything cinematic/EDM-adjacent - usually has real dynamic movement
(quiet intro, a build, a drop, a plateau), and a video with its own arc
(calm open, rising tension, a climax) deserves a music window whose energy
curve actually tracks that, not a flat or mismatched one.

Measure it rather than guessing, in chunks across the track:

```bash
for t in 0 10 20 30 40 50 60 70 80 90 100; do
  vol=$(ffmpeg -nostdin -i track.mp3 -ss $t -t 10 -af volumedetect -f null - 2>&1 | grep mean_volume)
  echo "t=${t}s: $vol"
done
```

Look for a window matching the video's own shape - e.g. a steadily
climbing mean_volume across the window usually means the video's own build
(if it has one, such as punch-in zooms escalating toward a climax - see
the **zoom** skill) will land on a genuinely building section of the
track, not an arbitrary one. The track's intro is often naturally the
right choice for a short-form video that itself opens calm and escalates -
check before assuming so, but don't automatically skip it either.

## Step 3: Measure the voice level before mixing

```bash
ffmpeg -nostdin -i video.mp4 -af volumedetect -f null - 2>&1 | grep -E "mean_volume|max_volume"
```

Note the `max_volume` (peak) - this is the reference the music needs to
stay well under. For voice-over content, background music sitting roughly
15-20dB below the voice's peak reads as a clear, professional "bed" that
never competes with speech; much closer than that and it starts fighting
the dialogue for attention.

## Step 4: Mix - and watch for `amix`'s hidden level change

```bash
ffmpeg -nostdin -y -i video.mp4 -i track.mp3 \
  -filter_complex "[1:a]atrim=<start>:<end>,volume=<reduction>dB,afade=t=in:st=0:d=1,afade=t=out:st=<fadeout_start>:d=1.5[music];[0:a][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]" \
  -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k output.mp4 -loglevel error
```

**The gotcha that actually happened:** `amix` defaults to `normalize=1`,
which scales down the SUM of all inputs to prevent clipping - this quietly
pulls the voice down too (not just the music), even though the voice was
never the problem. On a real mix this dropped the voice's own peak by 6dB
(from -10.6dB to -16.5dB) despite the music already being reduced by
24dB - the relative balance between voice and music was technically still
right, but the whole video got noticeably quieter than the original cut.
Pass `normalize=0` explicitly so only the music's own `volume=` filter
controls its level and the voice stays exactly as loud as it already was.

Pick the `volume=<reduction>dB` value empirically: start around -20 to
-25dB off the music's own peak (check the music segment's `max_volume`
first, same command as Step 3, to know what you're reducing from) and
adjust from there.

## Step 5: Verify the result, don't assume the filter graph did what you meant

```bash
ffmpeg -nostdin -i output.mp4 -af volumedetect -f null - 2>&1 | grep -E "mean_volume|max_volume"
```

The output's `max_volume` should land close to the original voice-only
`max_volume` from Step 3 (within ~1dB) - if it's dropped noticeably more
than that, something (usually `amix` normalization) is quietly attenuating
the voice and needs fixing before calling the mix done, not after the user
reports it sounds too quiet or the music sounds too loud.

## Delivering

Same pattern as the other video skills - the mix output is full quality;
make a secondary compressed copy for any tool with a file-size limit
rather than compressing the master:

```bash
ffmpeg -nostdin -y -i output.mp4 -c:v h264_videotoolbox -q:v 65 -pix_fmt yuv420p -c:a aac -b:a 128k output_share.mp4 -loglevel error
```

(Apple VideoToolbox - ~4x faster than libx264 on an M-series Mac, same quality as
`-c:v libx264 -preset slow -crf 24`, which is the fallback when `h264_videotoolbox` is missing
and gives a ~40% smaller file when size matters more than time.)

## Different track per section (era / chapter) - decades reel, 2026-11-05

A soft 0.3s crossfade between tracks read as "konfuzno, nema jasnih prelaza".
What fixed it:
- **Hard switch on the cut**: each track starts at a section boundary from
  its own first strong downbeat (numpy: lowpass ~150Hz onset energy, beat
  phase with max energy at the known BPM, strongest of 4 = downbeat); the
  old track fades out in 0.3s ending exactly at the cut.
- **A short transition sound** between sections (radio tuning for eras):
  a different 0.4s slice of the SFX each time, ending ~0.04s after the cut,
  at about -27 LUFS.
- **Each segment gain-matched** to the same LUFS (-30) so no track jumps out,
  then `sidechaincompress` keyed by the voice (threshold 0.02, ratio 5,
  attack 15, release 350) - music comes up in pauses and on the switches.
- Voice peak/LUFS unchanged after mixing (amix normalize=0) - verify it.
- **The picture follows the sound** (user: "menjanje stanica mora da prati i
  slika"): `scripts/tv_channel_fx.py video.mp4 out.mp4` (reads `eras.txt`,
  writes `fx_vN.txt`) puts a TV channel change on each section cut, 13
  frames (cut-7 .. cut+5): vertical-hold roll with a sync bar, tearing,
  colour fringes, snow peaking on the cut, scanlines. The transition sound
  then spans the same window (0.52s from cut-0.28). Run `check_video.py`
  with `--fx fx_vN.txt` - the static would otherwise count as many cuts.
