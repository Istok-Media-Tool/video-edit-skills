---
name: zoom
description: Plan zoom together with the user in the plan-editor tool (click-a-word, see the plan-editor skill), then add dynamic punch-in zoom crops to an already-cut talking-head video at content-driven moments, correctly centered on the subject with proper headroom - so cuts between different zoom levels read as an intentional, cinematic camera choice instead of the subject visibly jumping around the frame. Use this skill whenever the user wants "dynamics" or "zoom"/"punch-in" effects added to a video, or asks to center/recenter/fix framing on a talking-head shot - even without naming ffmpeg or any of this explicitly (e.g. "dodaj zum da bude dinamičniji", "glava mi je pomerena u kadru", "nedostaje dinamika u ovom videu"). This is normally applied AFTER a video has already been cut to its final sequence of clips (see the "basic" skill for that step) - don't assume cutting is also wanted just because this skill triggered. Rotation to a different orientation is NOT part of this skill - handle that separately, ad hoc, only when asked.
---

> `$SKILLS` below is the folder that holds this skill's folder: the parent of the base directory shown when the skill loads (the plugin's `skills/` folder).


# Dynamic zoom

## Why this skill exists

Adding "dynamic" zoom to a cut talking-head video is deceptively easy to get
wrong in ways that only show up once you actually watch the result, not from
the numbers alone. On a real case, the same video went through several
corrected rounds of feedback before it was right - each one taught something
worth not re-learning from scratch:

1. A naive zoom-at-every-cut approach looked cheap and gimmicky - real
   editing judgment is sparser and more deliberate than that.
2. A crop centered symmetrically around eye-level, instead of anchored on
   the actual head-top, left excessive empty space above the head once
   scaled back up (~17% headroom when ~9% looked right).
3. Reusing ONE segment's measured head position for crop math on OTHER
   segments of the same recording put the subject visibly off-center in
   segments where they'd shifted in their seat minutes earlier or later in
   the take - even though it's a single continuous recording.
4. Leaving the "wide"/non-zoomed shots completely uncropped, while only
   correcting the zoomed shots, meant every cut between a wide and a zoomed
   shot still visibly jumped the subject sideways - the wide shots needed
   the *same* recentering and headroom treatment, just at a much lower zoom
   level, for cuts between them to feel like one coherent camera.
5. One zoom level per clip, and then a punch-in mechanically placed at each
   sentence's midpoint, both read as RANDOM to the user. Zoom must follow
   the script: every change lands on the specific word or phrase that
   justifies it (a reveal, a key term, a personal question, the punchline),
   and pull-backs land on words about scale ("univerzum", "milijarde
   godina"). Changes happen mid-clip, sometimes more than once per clip.
6. The user wants to DECIDE the zoom plan together, word by word, using the
   plan-editor tool (Step 1). Always use it - for any script.

7. The user chose the zoom steps: 1.0x, 1.5x, 1.7x, 2.0x, 2.2x
   (plan levels 0-4). "1.0x" (level 0) is NOT the raw frame: rendered as the
   raw uncropped frame it left the subject off-center with far too much
   space above the head, and the user asked for it to be centered with the
   same headroom as every other shot. So level 0 = the `--baseline` crop
   (loosest crop meeting the 9% headroom, recentered; ~1.2x in practice) -
   `build_zoom_selections.py` does this automatically. Keep the label
   "1,0x" in the tool; it means "widest, centered".

## Step 1: Plan the zoom TOGETHER in the plan-editor tool

Mandatory for every video: load and follow the **plan-editor** skill
(`$SKILLS/plan-editor/SKILL.md`). It is the user's standard
click-a-word tool where they decide the zoom with you and, via "Izmeni
tekst", fix caption text in the same sentences. Never render zoom from a
plan the user hasn't shaped there.

Your job in that step is the starting proposal: build it from the
content's energy curve - establishing/calm = wide, a twist or punchline
earns a push-in ON ITS KEY WORD, an explanatory beat pulls back for a
breath, the climax gets the tightest frame; decisive level differences (no
subtle creep); at least one real return to wide after the opening - and
give the reason for each change. The user's reply (`PLAN_JSON`,
`SENTENCES_JSON`) is the confirmed plan; render it exactly in Step 5.

**Different shot size on every cut (the user's style, 2026-11-10).** In the
two hand-edited reference reels ("Mouse Paradise", "Johanna / Van Gogh")
the shot size changes on EVERY jump cut between clips - wide, medium,
tight - and never stays the same across a cut, so each cut reads as a
second camera instead of a glitch. This does not contradict lesson 1: the
cuts already exist (one per clip), the zoom only makes them look
intentional; punch-ins mechanically added INSIDE clips are still what
looks cheap. So in the starting proposal:
- each clip's start level (`"s"`) differs from the level the previous clip
  ends on, by 2+ steps where the content allows (e.g. 0 <-> 2/3/4);
- word-anchored changes inside a clip stay content-driven as above.
Render with `--alternate` (Step 5; `"alternate": true` in the
plan-editor's project.json): it changes any clip the final plan left at
the same size as the end of the previous clip and prints which - tell the
user. Without the flag it only reports those cuts.

Applying the plan needs word timestamps (Step 5) and per-clip subject
positions (Step 2).

`examples/sample/` holds a real confirmed set (sentences, the user's
plan, positions, cuts) for a sideways-shot video rotated with
`transpose=1` - a reference for file formats and for the kind of plan this
user picks.

## Step 2: Measure the subject's position - PER SEGMENT, every time

Never reuse one segment's measured head position for another segment's crop
math, even within the same continuous recording - someone can shift in
their seat by the time you're several minutes further into a long take, and
a crop computed from an early segment's frame can miscenter, or at tighter
zoom actually clip, the subject in a later segment that looks similar but
isn't framed quite the same.

For each segment you're about to crop (including the "wide" ones - see step
4):

```bash
ffmpeg -nostdin -y -ss <mid_timestamp_of_that_segment> -i source.mp4 -frames:v 1 ref.png
ffmpeg -nostdin -y -i ref.png -vf "drawgrid=w=54:h=96:t=1:c=red@0.6" grid.png
```

(54x96 gives a 20x20 grid on a 1080x1920 frame - scale proportionally for
other resolutions.) Look at `grid.png` and read off:
- `cx` - the x of the face/nose center
- `head_top_y` - the y of the very top of the hair (not the eyes - headroom
  is measured from the top of the head)

## Step 3: Compute the crop

```bash
python3 scripts/compute_crop.py --cx <measured_x> --head-top-y <measured_y> --zoom 1.7
python3 scripts/compute_crop.py --cx <measured_x> --head-top-y <measured_y> --baseline
```

- `--zoom Z` for an explicit punch-in level (e.g. `1.7` for a 170% shot).
- `--baseline` for the "wide" shots: it finds the LOOSEST crop that still
  satisfies the headroom target and recenters horizontally - this is what
  makes the wide shots only mildly cropped (not literally 100%/untouched)
  but share the exact same optical center and headroom as the zoomed shots,
  which is what actually prevents cuts from looking like the subject jumps.
  **Don't skip cropping the wide shots** - leaving them raw while only
  fixing the zoomed ones was the single biggest source of "something looks
  off" in testing, bigger than getting any individual zoom level wrong.

Default headroom is 9% of the cropped frame's height, which read as correct
in testing - below that looked cramped, and it's not just aesthetic: a
vertical platform (Instagram/TikTok/Shorts) overlays username/caption/fade
UI across the very top of the frame, so that margin is functional space the
platform will cover, not spare room. Override with `--headroom` if a
specific project calls for something else, but don't go much below ~9% for
anything headed to those platforms.

Full reasoning for all of the above lives in the docstring of
`scripts/compute_crop.py` - it's short, read it if anything here is unclear
on a specific case.

## Step 4: Verify the real rendered output before the full render

A crop that looks right on a single still frame can still clip or
off-center the subject once you check motion. For each segment (especially
whichever one showed the most body movement - leaning in, head tilt - when
you were picking the reference frame):

1. Render just that one segment with its crop applied.
2. Sample 3+ frames spread across its actual duration (not just the one you
   measured), e.g. `ffmpeg -i clip.mp4 -vf fps=3 check_%02d.png`.
3. Look at them. If the head is ever cut off or jammed too close to an edge,
   loosen that segment's zoom or widen its margin before moving on.

Only after this passes should you render all segments and concatenate.

## Step 5: Turn the confirmed plan into word-anchored cuts, then assemble

1. Get word timestamps from a render of the same cut (a plain cut, or a
   previous zoom render - padding must match), and note that render's
   per-clip durations (ffprobe each `clip_NNN.mp4` in its workdir):
   ```bash
   python3 scripts/word_times.py cut_render.mp4 words.json --language sr
   ```
2. Build the selections file. `cuts.txt` = the basic skill's unpadded
   `start<TAB>end` per clip; `pos.json` = `[[cx, head_top_y], ...]` per clip
   from Step 2 (measured on the rotated frame if `--pre-filter` rotates):
   ```bash
   python3 scripts/build_zoom_selections.py --cuts cuts.txt --positions pos.json \
     --plan plan.json --sentences sentences.txt --words words.json \
     --durations 6.28,6.08,... [--pre-filter transpose=1] --alternate > selections.txt
   ```
   Read the match report it prints: every planned word should say `exact`
   (or a sensible `fuzzy~` spelling variant - Whisper may spell names
   differently or in Cyrillic). Any `proportional (no match!)` line must be
   fixed by hand before rendering. The change lands 0.08s before the word
   (`--lead`). Clips with several levels are rendered as one continuous clip
   (split + timed overlay), so a mid-sentence zoom never adds a cut or an
   audio seam.
3. Spot-check frames 0.2s before and after every zoom change (Step 4 logic:
   head never clipped, change clearly visible), then render:

```bash
scripts/cut_and_concat.sh "<source_video>" selections.txt final_output.mp4 "$PWD/build"
```

Pass the workdir as an ABSOLUTE path - with a relative one the final concat
step fails to find `concat_list.txt`.

Rendered clip durations can differ from the previous render's by a few
hundredths of a second, so if captions (subtitle skill) were timed against
an earlier render, shift each caption by its clip's new start before
burning.

Read the comment block at the top of `cut_and_concat.sh` before adapting it
- it documents ffmpeg/bash gotchas (stdin theft inside loops, fade-outs
eating the last syllable of a cut, why clips need individual re-encoding
before concat) that are easy to silently reintroduce otherwise.

Example selections file mixing a baseline (wide) segment and two punch-ins:
```
63.82	69.57	crop=908:1614:152:304,scale=1080:1920
80.37	85.90	crop=636:1130:288:348,scale=1080:1920
97.25	100.81	crop=908:1614:152:304,scale=1080:1920
```

If the source also needs a rotation/orientation fix, that's handled
separately (not part of this skill, since it's not always needed) - prepend
whatever rotation filter was agreed on to each line's filter chain yourself
if it applies here.

## Delivering

If the master output exceeds a tool's file-size limit, make a secondary
compressed copy rather than compressing the master:

```bash
ffmpeg -nostdin -y -i final_output.mp4 -c:v h264_videotoolbox -q:v 65 -pix_fmt yuv420p -c:a aac -b:a 128k final_output_share.mp4 -loglevel error
```

(Apple VideoToolbox - ~4x faster than libx264 on an M-series Mac, same quality as
`-c:v libx264 -preset slow -crf 24`, which is the fallback when `h264_videotoolbox` is missing
and gives a ~40% smaller file when size matters more than time.)

## Objects the speaker shows must stay whole in every zoom

On a real reel the speaker shows photos on a tablet next to him; crops centered
on the face cut its left edge ("ne sme tablet da bude isečen ovako
nigde"). Before rendering, list everything in the frame that the video is
ABOUT (a tablet, a product, a page held up) and measure its box on the
grid. Every zoom crop must contain that box with ~30px of air: shift the
crop's x / y toward it (the face may sit off-center, up to ~70% across),
and if the face would then touch the edge, use a looser level for that
change (1.7x -> 1.6x on a real reel) rather than cutting either. Look at a
frame of every zoom range to confirm both are whole.
