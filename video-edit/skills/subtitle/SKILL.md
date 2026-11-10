---
name: subtitle
description: Burn styled, readable captions/subtitles into a video using a real ASS subtitle file and ffmpeg's libass renderer (not drawtext hacks). Use this skill whenever the user wants titlovi/subtitles/captions added or burned into a video, wants text overlay synced to speech, or asks to change subtitle font/size/position/line-breaks on an existing captioned video - even if they don't say "ASS" or "libass" explicitly (e.g. "dodaj titlove", "stavi tekst na video", "promeni font na titlovima"). Normally applied to a video already cut to its final sequence (see the "basic" skill) and optionally already reframed/zoomed (see the "zoom" skill) - don't assume those steps are also wanted just because this skill triggered.
---

# Subtitle burning

## Why this skill exists

Getting captions to actually look right took several corrected rounds on a
real project, each one worth not re-learning from scratch:

1. The system's default Homebrew `ffmpeg` has no `drawtext`/`subtitles`
   filter at all (not built with libass/freetype) - burning real styled
   subtitles needs a different ffmpeg build, not a workaround.
2. Breaking caption lines to balance character counts produces nonsense -
   a line break must fall where a person would naturally pause speaking the
   sentence, never mid-phrase.
3. Lines stretched close to the left/right frame edges can get clipped by
   Instagram's own cropping once posted - real margin is required, not just
   "fits the frame".
4. Font size and vertical position are subjective per project and worth
   confirming, but get them visually verified before a full render either
   way - a still-frame check catches overflow/clipping in seconds, a full
   re-render doesn't.
5. Captions must not move between screens. The first version anchored them
   to the BOTTOM (Alignment 2, MarginV 500), so a 3-line caption started
   higher than a 2- or 1-line one, and captions that overlapped the
   previous one by a few hundredths of a second were pushed up by libass's
   collision avoidance for their whole duration - the user saw titles
   "walking up and down". Fixed rule: anchor to the TOP (Alignment 8,
   MarginV = y of the first line; 1215 on 1080x1920 keeps the lowest line
   of a 3-line caption where the old bottom anchor had it) so every
   caption's first line sits at the same spot and extra lines grow
   downward, and never let two Dialogue events overlap in time.
   Moreover, leave a short EMPTY moment between consecutive captions: end
   each event 0.12s (3 frames at 25fps) before the next one starts. The
   user asked for this explicitly - the brief blank tells the brain the
   caption changed; back-to-back captions read as the same text
   flickering. Shorten the earlier caption's End, never delay the next
   Start (that one is synced to speech).
6. Caption text is not required to be a verbatim transcript - fix
   grammar/wording issues (a misheard word, an awkward construction) and
   drop or add words the user asks to change, same as you would when
   copy-editing text anyone will read.

## Step 1: Make sure ffmpeg can actually burn subtitles

```bash
ffmpeg -hide_banner -filters 2>&1 | grep -E "subtitles|^\s*\S*\s+ass\b"
```

If nothing matches, the regular `ffmpeg` can't do this. Install the full
build:

```bash
brew install ffmpeg-full
```

`ffmpeg-full` is keg-only (not symlinked into PATH) - use it explicitly for
the subtitle burn step: `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`.

**Gotcha that actually happened:** installing `ffmpeg-full` pulled in a
newer shared `x265` and broke the regular `ffmpeg`/`ffprobe` on PATH (dyld
"Library not loaded: libx265.*.dylib" error), because they'd been linked
against the older version. Immediately after installing `ffmpeg-full`, run:

```bash
ffmpeg -version && ffprobe -version
```

If either errors, fix it with `brew reinstall ffmpeg` (the regular formula,
not `-full`) and re-verify both commands work before continuing - don't
assume the regular ffmpeg survived the install untouched.

## Step 2: Get the exact caption text and timing

If the video came from the **basic** skill's cutting workflow, you already
know the exact kept text per segment and its original source timestamps -
but once segments are cut and concatenated, timing resets to the new
video's own timeline. Compute each segment's position in the FINAL video by
summing the actual rendered clip durations in order:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 clip_01.mp4
```
...and accumulate. Within each segment's window, inset slightly from the
clip's own start/end to match where speech actually starts/stops (if the
clips carry pre/post padding from the cut step, subtract it back out) so
captions don't appear/disappear on dead air.

## Step 3: Write the ASS file

Use this as a starting template - it's the exact style confirmed on a real
project (Inter Bold, white text, opaque black box, lower-middle
positioning, generous side margins):

```
[Script Info]
Title: <video name> - titlovi
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Inter,70,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,3,16,0,8,120,120,1215,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.15,0:00:05.93,Default,,0,0,0,,Zamisli univerzum koji postoji\Ntoliko dugo da su sve zvezde\Nodavno ugašene
```

Before burning, make every event end 0.12s before the next one starts
(set the earlier event's End to next Start - 0.12; never move a Start) -
see lesson 5.

Adjust `PlayResX`/`PlayResY` to match the actual video resolution (this
example is a 1080x1920 vertical). `WrapStyle: 2` means libass will NOT
auto-wrap text - every line break must be an explicit `\N` in the Text
field. This is intentional: it forces you to choose every break
deliberately (see Step 4) instead of letting the renderer guess, and it's
also what catches an overflowing line as a clipped edge rather than a
silently-added extra line.

Font/size/color/position are all defaults to START from, not fixed rules -
confirm with the user if this is a new project, or reuse their last
confirmed values if you already know them for this user.

### Punctuation convention confirmed on a real project

Trailing periods AND trailing commas at the end of the LAST line of a
caption screen get dropped (captions don't need a full stop the way prose
does - it reads as visual clutter at that size). This applies even when
the sentence continues onto the next caption screen: the screen change
itself already reads as the pause, so "svoje znanje kroz praksu," is shown
as "svoje znanje kroz praksu". The user asked for this explicitly
(2026-11-05, "isto kao za tačku"). Question marks and exclamation marks
stay. Commas INSIDE a screen (mid-line, or at the end of a line that is
not the screen's last line) stay. Apply it by default on every video,
including to the second-language line in bilingual captions, and to
caption text the user edits in the plan-editor.

## Step 4: Break every line where a person would actually pause speaking

This is the part most worth getting right and easiest to get lazily wrong.
Read the sentence as if saying it aloud and break at the natural breath/
phrase boundaries - clause boundaries, after a complete thought, at
commas that represent a real spoken pause. Never break because a line
"needs" to be shorter if the natural break point is somewhere else - find a
SHORTER natural break instead (there's almost always more than one valid
pause point in a longer sentence), don't force an unnatural one just to hit
a width target.

Concrete example from a real correction - wrong (balanced by character
count, breaks mid-phrase):
```
Zamisli univerzum koji postoji toliko
dugo da su sve zvezde odavno ugasene
```
Right (breaks at natural spoken pauses):
```
Zamisli univerzum koji postoji
toliko dugo da su sve zvezde
odavno ugašene
```
1, 2, or 3 lines are all fine - there's no fixed maximum. What matters is
every break being a place a speaker would actually pause, and every line
fitting inside the margins (next step).

## Step 5: Verify width against the ACTUAL side margins, not raw frame width

`MarginL`/`MarginR` in the style (120px each on a 1080-wide frame in the
template above - roughly 11% each side) exist because the platform the
video is headed to (Instagram etc.) applies its own slight crop after
upload, and text too close to the raw edge can get clipped by that, not
just by the frame boundary. Treat `PlayResX - MarginL - MarginR` as the
real usable width when judging whether a line is too long, not the full
frame width.

Since `WrapStyle: 2` disables auto-wrap, a line that's actually too wide
won't wrap itself - it will overflow past the margin, which reads as
clipped/cut-off text. Catch this in Step 6, before it ends up in a full
render.

## Step 6: Render test frames before burning the whole video

Pick a timestamp inside each of the 2-3 longest/riskiest captions and
render just that frame:

```bash
/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg -nostdin -y -i video.mp4 -ss <t> -update 1 \
  -vf "subtitles=captions.ass" -frames:v 1 check.png -loglevel error
```

Look at each one for: text overflowing past the margins, more lines than
intended (a sign a line is wider than expected and something upstream needs
rewording/re-breaking), and the vertical position actually reading as
"lower-middle" rather than too close to the very bottom edge or high enough
to cover the face. Fix and re-check before moving on - this loop is fast
(a few seconds per frame) and catches exactly the mistakes a full render
would otherwise waste minutes reproducing.

## Step 7: Burn the final video

```bash
/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg -nostdin -y -i video.mp4 \
  -vf "subtitles=captions.ass" -c:v h264_videotoolbox -q:v 75 -pix_fmt yuv420p \
  -c:a copy output_titlovi.mp4 -loglevel error
```

Audio is untouched (`-c:a copy`) since subtitles are video-only. If the
output needs to go through a tool with a file-size limit, make a secondary
compressed copy rather than compressing the master - same pattern as the
**basic** and **zoom** skills:

```bash
ffmpeg -nostdin -y -i output_titlovi.mp4 -c:v h264_videotoolbox -q:v 65 -pix_fmt yuv420p -c:a aac -b:a 128k output_titlovi_share.mp4 -loglevel error
```

(Apple VideoToolbox - ~4x faster than libx264 on an M-series Mac, same quality as
`-c:v libx264 -preset slow -crf 24`, which is the fallback when `h264_videotoolbox` is missing
and gives a ~40% smaller file when size matters more than time.)

## Iterating on feedback

Caption work tends to go through several rounds of small, specific
corrections (font size, position, a wrong word, punctuation). Each round
should only touch what changed - edit the `.ass` file directly (it's plain
text), re-run Step 6's quick frame check on whatever was affected, then
re-burn with Step 7. There's no need to redo Steps 1-2 unless the
underlying video itself changed.

### Fixing wrong words through the interactive tool

The user prefers to correct caption text themselves in the same
plan-editor tool (plan-editor skill - the user's standard editor): with the
"Izmeni tekst" toggle every sentence becomes editable in place. Whenever captions
exist, show that tool with `--ass captions.ass --durations ...` (see the
plan-editor skill) instead of asking for corrections in prose - also when only the
captions need checking and no zoom is planned (then just start every clip
wide and leave the zoom plan untouched).

The reply carries `CAPTIONS_JSON: {"<dialogue index>": "line 1\nline 2"}`
with only the changed screens. Apply it:

```bash
python3 scripts/apply_caption_edits.py captions.ass caption_edits.json captions_fixed.ass
```

It changes only the text (timing and style stay), turning each line into an
explicit `\N` break. Then re-run Step 6's frame check on the edited screens
(a longer word can overflow the margins) and re-burn with Step 7.
