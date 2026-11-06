---
name: title-behind
description: Opening title with a huge number or word BEHIND the speaker's head (the speaker is cut out and stands in front of it), plus a flag/emoji and one or two lines on the chest in front - the "text behind subject" hook used on Instagram/TikTok reels. Use whenever the user wants a title, naslov or hook at the start of a talking-head video with letters, a number or a word behind the person, e.g. "stavi 500 iza glave", "tekst iza osobe", "naslov iza nje kao na TikToku", "broj iza subjekta", "uradi naslov kao na ovoj slici" (with a photo of such a title). Builds on hyperframes (render), zoom (wide shot) and subtitle (captions).
---

> `$SKILLS` below is the folder that holds this skill's folder: the parent of the base directory shown when the skill loads (the plugin's `skills/` folder).


# Title behind the speaker

## Why this exists

Approved on a real reel (2026-11-05) after the user sent
a photo of the look. What the user cares about, in order:

1. The big text is BEHIND the head - the head covers the lower part of the
   middle characters (~30%), the text still reads at a glance. Without
   "behind" it's just text over video.
2. Clear size order: the big text is huge (fills ~90% of the width), the
   lines are ~1/3 of it, the flag is small.
3. The lines sit on the chest, below the chin, never over the face.
4. The background is darkened, the speaker stays bright (the cutout is on
   top of the dim) - that gives depth.
5. The top ~280px get cropped by Instagram's grid/4:5 preview - keep the
   big text's top below ~150px and anything important lower.

A short request ("500 iza glave, ispod 'Engleskih reči za 30 sekundi'
🇮🇹") is enough; derive the rest from these rules and show a snapshot.

## Steps

1. **Wide shot for the title clip.** The big text needs room above the
   head: render the first clip (up to the first cut) at the widest level
   (`wide_zoom` 1.3 on that reel - never one that shows the desk edge). In the
   plan-editor plan that's clip 1 = `{"s": 0, "m": {}}`.
2. **No duplicate captions.** Drop the caption screens that say the same as
   the title (e.g. "Naučiću te 500 reči…", "za trideset sekundi") and
   re-burn the captions; the title covers 0 → first cut. Tell the user.
3. **Cutout of the speaker** from the video WITHOUT captions (the zoom
   render), frame-identical to the bg, title length only:
   ```bash
   ffmpeg -nostdin -y -i zoom.mp4 -t <first cut> -an -c:v libx264 -crf 14 assets/title_src.mp4
   npx hyperframes remove-background assets/title_src.mp4 -o assets/cut.webm --quality best
   ```
   `--quality best` so the cutout's colours match the bg (no visible edge).
4. **Head top.** Measure it on the first clip with Vision (zoom skill /
   `faces.swift`): hair top ≈ face top − 0.37·face width, in 1080×1920
   px. Chin ≈ face bottom; `--sub-top` ≈ chin + 20..60.
5. **Write the scene:**
   ```bash
   python3 $SKILLS/title-behind/scripts/make_title.py --big 500 \
     --lines "Engleskih reči|za 30 sekundi" --flag 🇬🇧 --dur 4.0 \
     --head-top 346 --sub-top 790 --cutout assets/cut.webm --out compositions/title.html
   ```
   and mount it in the root `index.html` (graphics track, above the bg,
   `data-start="0" data-duration="<first cut>"`). Other overlays (headers,
   top scrim) start at the first cut, not at 0.
6. **Check and look:** `npx hyperframes check`, then
   `npx hyperframes snapshot --at 0.3,1.5,<dur-0.5>`. Verify: head covers
   ~30% (max 50%) of the big text, nothing of it is cut off left/right,
   the lines don't touch the face. Adjust with `--size`, or move the text
   by changing `--head-top` by ±40px, and look again.
7. Render, mix voice + music (music skill), `check_video.py` with the
   title end (= first cut) in `--edges`, `_share` copy, send with
   SendUserFile `display: render`.

## Readability first (decades reel, 2026-11-05)

On a word (not a number) over a LIGHT, busy background (white shelves), 30%
coverage read as "nečitljivo" twice. What the user approved:
- the head covers only the very bottom of the middle letter (~10%) - pass
  `--head-top` ≈ real head top − 0.18·size so the box sits 0.62 em above it;
- the word at ~250px with ~100px free on each side ("da ne udara u ivice");
- a dark text-shadow on the big text (`0 6px 34px rgba(0,0,0,.6)`) to lift
  it off light backgrounds;
- the second line may go ABOVE the big word instead of on the chest when
  the user asks (`--sub-top` above the big text, ~84px).
Example values: head top 524, `--head-top 490 --size 250 --sub-top 285`.

## Example values (for reference)

1.3× wide, head top 346 → big "500" Inter 900 340px at top 196,
lines 98px at 790, flag 96px above the first line on its left, dim
rgba(0,0,0,.42) + bottom shade 620px, title 0–4.00s.
