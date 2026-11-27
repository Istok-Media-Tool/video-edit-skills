---
name: istok
description: The whole ISTOK edit in one go - apply EVERY video-edit skill of this package to a raw talking-head recording, in the Istok house style, from the raw take to the delivered reel - cut by script with retakes chosen (basic), zoom (zoom), phrase captions (subtitle), one editor round where everything is decided together (plan-editor), a title behind the head (title-behind), music that hits the key words and ends on its final chord (music), chapter cards or scrapbook when the video has parts (chapter-cards / scrapbook), then render, mix, check and deliver. Use it whenever the user says "primeni istok skill", "primeni istok", "istok skill", "uradi istok", "istok montaža", "uradi sve", "odradi ceo video", "apply the istok skill", "apply istok", "do the istok edit", "full edit", or hands over a raw recording (and a script) asking for the complete edit rather than one step.
---

> `$SKILLS` below is the folder that holds this skill's folder: the parent of the base directory shown when the skill loads (the plugin's `skills/` folder).


# ISTOK - the whole edit, every skill

> **Style:** Istok house style by default (`basic/STYLE.md` in this package,
> `$SKILLS/basic/STYLE.md`). If `~/.config/video-edit/style.md` exists,
> read it first - the person's own rules there win over every house rule below.

"Primeni istok skill" means: take this recording all the way to a finished
reel with **every** skill of the package. This page is only the order and
the hand-offs - the how lives in each skill. **Read each skill's SKILL.md
when you reach its step** (they sit next to this one: `../basic/`,
`../zoom/`, ...) and follow it exactly; do not work from memory.

Every skill is applied or **explicitly** set aside with the reason, said to
the person ("no chapter cards: the video has no parts"). Nothing is
skipped silently, and nothing is decided for the person that the skills
say is decided together (takes, zoom, captions, title, music places, the
track).

## Before starting

1. Inputs: the raw recording, and the script if there is one (without a
   script, basic cuts the retakes by the transcript and shows the plan).
   Ask only for what is missing. Note B-roll / photos / music the person
   already gave.
2. First time on this machine, or a "not found": run the basic skill's
   `scripts/setup_check.py` (the `basic` folder next to this skill's folder)
   - install only what the person says yes to.
3. Make one work folder for the video next to the source (`<name>_istok/`)
   and keep every step's files there; versions are `_v1`, `_v2`, never
   overwritten.
4. Put the plan below on the task list (one item per step), so the person
   sees where the edit is.

## The order

| # | Step | Skill | Output |
|---|---|---|---|
| 1 | Cut by the script: transcription, bursts, edit plan shown and confirmed, tight pacing, word edges guarded | **basic** | cut + `selections`, word times |
| 2 | Retakes: every sentence said more than once goes to the editor's Takes mode (`make_take_clips.py`), never picked silently | **basic** + **plan-editor** | takes.json |
| 3 | Head position per clip, the wide 1.0× frame, a zoom proposal on content words, objects the speaker shows kept whole | **zoom** | pos.json, plan.json, zcrops / wide |
| 4 | First render of the cut, its word times and clip durations | **zoom** (`word_times.py`) | render, words.json |
| 5 | Phrase captions: hook card, body cards, ONE emphasis term, line breaks where a person pauses | **subtitle** | captions.ass |
| 6 | Title behind the head: propose the hook (big number / word + 1-2 lines) from the first sentence, shown in the Naslov mode | **title-behind** (plan) | title text |
| 7 | Music places: propose 1-2 poenta, 1-2 promena, 2-5 naglasak on the story | **music** step 0 | accents (proposed) |
| 8 | Music candidates: Epidemic Sound search, map, rank (closure counts), arrange the top 3, verify each - shown as A / B / C | **music** steps 1-5 | music.json, arr_*.wav |
| 9 | Parts of the video: if it moves through eras / steps / topics, propose chapter cards **or** scrapbook (one look per video, not both); otherwise set aside and say why | **chapter-cards** / **scrapbook** | parts.json (proposed) |
| 10 | ONE editor round with every mode that has material: Zoom, captions text, B-roll, caption position, Naslov, Close-up, Takes, Zoom frames, 1.0× frame, Muzika (A/B/C) | **plan-editor** | plan_reply.txt |
| 11 | If the person changed the music places: re-rank / re-arrange, show the editor again for the track choice by ear | **music** + **plan-editor** | chosen arrangement |
| 12 | Render the plan: zoom, B-roll, overlays, captions off faces; look at the check sheet | **plan-editor** (`render_from_plan.py`) | out_vN.mp4, sheet.jpg |
| 13 | Title behind the head on the wide first clip (captions that repeat it dropped), then cards / scrapbook if agreed | **title-behind**, **chapter-cards** / **scrapbook** | graphics composite |
| 14 | Sound effects where the music has nothing, then the mix: bed under the voice, closure on the final chord, Broadcast master, -14 LUFS | **music** steps 7-8 | mixed master |
| 15 | `check_video.py` on the final (cuts, edges, captions) until "OK - nothing found"; share copy; send | **basic** | `<name>_vN.mp4`, `_share.mp4` |

Steps 2-9 only PREPARE material and proposals; the person decides all of
it in step 10, in one editor, before anything final is rendered. Steps
6-9 may run while the person is still looking at earlier ones (e.g. map
music in the background), but the editor opens once, with everything.

## Rules that hold across the steps

- **Decide together, render once.** Never render zoom, captions, B-roll,
  title, graphics or music from a plan the person has not seen in the
  editor. A change asked in chat goes back into the editor before the
  render.
- **Every render is checked** (basic, "Check every render") before it is
  sent - also intermediate ones.
- **The music ends on the track's own final chord**, never a fade or a
  cut; the speaker's silent look into the camera at the end is the tail.
- **Encoder:** the hardware encoder of the machine (VideoToolbox on a Mac,
  basic "Encoder"). Masters stay full quality; the share copy is separate.
- **Captions never cover a face** (subtitle Step 6b); the title and cards
  sit in the free slot of every shot, inside Instagram's safe zone.
- **Text breaks** where a person would pause (basic, "Line breaks").
- If a step fails or a tool is missing, stop at that step, say what and
  why, fix it (or ask), and continue - do not drop the step.

## Delivering

Send the final with SendUserFile (`display: render`) and say in a few lines
what each skill did on this video (cut from X to Y, N zoom changes, title,
track and where it hits, cards or why none), plus anything set aside.
Keep every version in the work folder.
