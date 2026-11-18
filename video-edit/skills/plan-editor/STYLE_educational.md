# Recipe: the "educational reel" look ("avocado hass", 2026-11-18)

A talking-head explainer (~2 min, 9:16) cut from a main camera + a close-up
camera + a few photos. Reverse-engineered from a finished reel the user liked
and reproduced from the raw footage: 80% of the cut used the same takes as
the reference, pacing and loudness matched. Use this recipe when the user asks
for "ovakav edit", "kao avocado", "edukativni reel", or gives the prompt
template from `prompt_stil_avocado.md`. Everything still goes through the
plan-editor before rendering (the user's rule).

## The look, in numbers

| | |
|---|---|
| Takes | the LAST full, clean take of each sentence (earlier one only if clearly better -> Dublovi) |
| Pacing | median gap between words ~0.08 s (basic: tighten_cuts.py); only 2-3 deliberate pauses (0.7-1.2 s): after a one-word answer, while the hands work, before the last line |
| Wide shot | the WHOLE main-camera frame, no crop (`"wide_zoom": 1.0`), about half the video |
| Punch-ins | hard cut to ~1.5x (level 1) for 1-3 s on a key word / number / punchline, then back to wide; ~10-12 per 2 min; once 1.7x on the strongest line |
| Push-ins | 2 slow animated zooms over a whole sentence: 1.0 -> 1.45x on the speaker (the pay-off line), and one on the close-up camera while a key step is shown (e.g. 1.75 -> 2.6x) |
| Close-up camera | in sync while the hands show something; from OTHER moments as inserts on the matching words (a label, a book, an ad, a half avocado) |
| Photos | full screen, Ken Burns ~2.5 %/s (1.0 -> 1.1x over 4 s) |
| End | ~3.5 s quiet shot after the last word (a still-life from the close-up camera) |
| Grade | none |
| Captions | phrase cards, Inter Medium 54, white on ~80% black box, no Hook card, no Emphasis, `--no-ellipsis`, numbers as digits (`--digits`), every card off the faces (check_caption_overlap.py) |
| Music | one track re-arranged to the video: a change at 2 turning points, the track's own ending under the last ~7 s; ~10 dB under the voice (`mix_bed.py --under 10 --lift 0`); master -14 LUFS, peak <= -1 dBTP |

## Steps (tools)

1. **Sync the cameras** (if there is a second one):
   `scripts/sync_cameras.py --main main/*.MP4 --second close/*.MP4 > second_camera.json`
   - It pairs files by sound and prints the offset (second = main + offset).
2. **Cut** - basic skill as always (last clean take, tighten to ~0.08 s).
   - The voice always comes from the main camera.
   - Sentences that a take does NOT contain word for word ("get rich" when only "got rich" was said): take the closest one and tell the user.
3. **Captions** - `make_phrase_captions.py words.json captions.ass --no-hook --no-ellipsis --digits [--body-y 0.40]`.
   - The reference sat at 0.49. That pushes long lines into the Instagram button rail, so keep 0.40 unless the user asks.
4. **Plan-editor** - zoom plan (level 1 on the key words, wide elsewhere) and B-roll stills. The user sends the plan.
5. **overlays.json** - push-ins, close-up inserts (synced: `"sync": true` + the `second_camera` block; other moments: `"in"`), stills and the end shot, by phrase.
   - Read `scripts/apply_overlays.py`'s header for the format.
   - Phrases must be written as the TRANSCRIPT has them (numbers spelled out).
6. **Render** - `render_from_plan.py` with `"wide_zoom": 1.0`, `"overlays": "overlays.json"` and `"kenburns": 0.025` in project.json.
   - Order: zoom -> B-roll -> overlays -> caption face check -> burn.
7. **Music** - try `arrange_music.py` first.
   - If the track ends in a fade (no closure) or the result reuses one hit, use `arrange_manual.py --at "0:0,<t>:<track t>,..." --end-on-track-end --end-from <last ~7 s>`.
   - Then `mix_bed.py ... --under 10 --lift 0 --track-start 0`.
8. **Check** - check_video.py, check_safe_zone.py, check_caption_overlap.py; look at the sheet.

## What the test taught (don't relearn)

- Synced close-ups must be split at every cut of the main camera, or they drift out of lip sync. apply_overlays.py does this itself.
- Clip positions on the timeline come from the REAL clip durations (frame-rounded, with padding), never from summing the unpadded end-start values. That drifted by 0.5 s and picked the wrong source moment.
- An overlay edge within 0.24 s of a cut snaps onto the cut. Otherwise you get 1-6 frame slivers that check_video reports.
- Seek video inserts with `-ss` slightly early plus `select`. A direct `-ss` doubled the first frame, and truncating the frame index froze every ~6th frame.
