---
name: chapter-cards
description: Chapter / era / section cards over a talking-head reel made with HyperFrames - one card per part of the video (decades, steps, topics), each in its own style but built as ONE planned system. Use when the user wants grafike po epohama/delovima/poglavljima, "kartice za svaki period", "oznaka za svaku deceniju", "grafika koja pokazuje gde smo u priči", or wants such graphics to look less random. Builds on hyperframes, hyperframes-registry and the music skill's per-section transitions.
---

> `$SKILLS` below is the folder that holds this skill's folder: the parent of the base directory shown when the skill loads (the plugin's `skills/` folder).


# Chapter cards

> **Style:** Istok house style by default (`basic/STYLE.md` in this package,
> `$SKILLS/basic/STYLE.md`). If `~/.config/video-edit/style.md` exists,
> read it first - the person's own rules there win over every house rule below.

## The rule the user set (decades reel, 2026-11-05)

"Važno je da bude planski jedno u odnosu na drugo, a ne ovako random
nabacano." The first draft (each era its own shape, size and corner) was
rejected. Approved: ONE template, the era only changes the skin.

- **Same slot every card**: the one place free in EVERY shot (wide, zoomed
  and close-up), measured on frames, never covering the face or the
  tablet/object the speaker shows (zoom skill rule). Example: top-left,
  x 40, y 136, 440x320 scaled 0.9 (bottom at 424, above the tablet in
  the zoomed shots).
- **Same rows**: label (era) / one line of what it was / a small drawn
  illustration of the topic (the eyebrow shape of that era) / a ruler of
  all chapters with the current one lit.
- **Same motion and timing**: drop in 0.4s, label pops, line fades, the
  illustration draws (stroke, then fill), the ruler marker slides from the
  previous chapter to this one - that slide is what ties the cards
  together. Cards start right after the transition effect (cut+0.24) and
  end before the next (next cut-0.28); the first/last ones snap exactly
  to a cut (check_video flags edges 2-5 frames off a cut).
- **The skin**: font, palette and ONE texture inside the card per chapter.
  No frame-wide extras (HUDs, light leaks) - they broke the system.
- Show a proposal sheet of stills over real frames first (crop of the
  cards + one full frame per chapter), then render.

## House look: the 80s neon card, always (user, 2026-11-05)

"Uzmi ovu estetiku za 80-e, i to koristi uvek, samo menjaj godine." Every
chapter card on every video uses the neon skin (`"style": "80"`, the
default in make_cards.py): dark violet glass panel, the `lt-neon-border` light running
round its edge (one copy per card, `neon<e>.html`, its own id and DUR),
Audiowide label in pink glow (80px for 6-character labels, 112px for 4),
Inter caps line in pale cyan, the illustration in glowing cyan, the
synthwave grid behind the ruler. Only the label, the line and the
illustration change per chapter. Do not propose other skins unless asked.

## Making the cards for a new video

Nothing about the video lives in the code - write a `parts.json` and run
the template inside the HyperFrames project (an `index.html` with
`<video id="bg">` in the root):

```bash
python3 $SKILLS/chapter-cards/scripts/make_cards.py parts.json
```

```json
{"slot":  {"x": 40, "y": 136, "w": 440, "h": 320, "scale": 0.9},
 "ruler": ["60", "70", "80", "90", "00", "10", "20"],
 "parts": [{"id": "60", "label": "60-e", "line": "blagi luk", "start": 2.64, "end": 4.68, "art": "60"},
           {"id": "00", "label": "2000-e", "line": "Y2K linija", "start": 27.28, "end": 39.28, "art": "00", "fx": ["shimmer"]}]}
```

- `slot`: measure the free spot on frames of THIS video (rule above);
  leave it out only when the example values fit.
- `ruler`: one short label per chapter (the ruler fits ~7); a part's
  place on it is its index, or `"mark"`.
- `start` / `end`: cut+0.24 .. next cut−0.28, first/last exactly on a cut.
- `label`: 4 characters at 112px, longer ones drop to 80px.
- `art`: the illustration of that chapter's topic - a brow shape from
  `gen.py` (`"60"`..`"10"`), `"hairs"` (laminated brow strokes),
  `{"d": "<one closed path in a 300x90 viewBox>"}` for any other topic
  (draw it, show it on the proposal sheet), or `null`.
- `fx` (optional): `shimmer` (chrome sweep over the label), `pop`
  (texture pops in), `blink` (texture blinks) - a real reel used one each on
  the 90s / 2000s / 2010s cards.

`examples/obrve_parts.json` is the approved decades reel; it gives exactly
the cards that shipped. Rerunning replaces the hosts in `index.html`.

## Files

`scripts/make_cards.py` (template; brow shapes from `gen.py`, the first
draft) writes `compositions/era<id>.html` + `neon<id>.html` and the hosts
into `index.html`.
`scripts/lt-neon-border_card.html`: the registry's `lt-neon-border`
retargeted to the card slot (W/H/position set as numbers - a CSS
transform on its wrap is ignored). Used when the project has no
`compositions/lt-neon-border.html` of its own.
Library recipes used inside the cards: text-shimmer (chrome sweep),
spring-pop (heart), blur-in (letters), svg-stroke-trace (draw-on).

## Render

Background = the finished video (captions, TV fx) cut to the cards'
part, re-encoded `-c:v h264_videotoolbox -q:v 85 -g 25`; `render --fps 25 --gpu --quality delivery
--video-frame-format png`; concat with the rest of the video by frame
(`trim=start_frame=`), audio copied; check_video with the card edges in
`--edges` and the transition windows in `--fx`. Share copy needs
`-maxrate 2.2M -bufsize 4M` to stay under 30 MB.
