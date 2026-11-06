---
name: chapter-cards
description: Chapter / era / section cards over a talking-head reel made with HyperFrames - one card per part of the video (decades, steps, topics), each in its own style but built as ONE planned system. Use when the user wants grafike po epohama/delovima/poglavljima, "kartice za svaki period", "oznaka za svaku deceniju", "grafika koja pokazuje gde smo u priči", or wants such graphics to look less random. Builds on hyperframes, hyperframes-registry and the music skill's per-section transitions.
---

# Chapter cards

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
chapter card on every video uses the neon skin (`STYLE = "80"` in
gen2.py): dark violet glass panel, the `lt-neon-border` light running
round its edge (one copy per card, `neon<e>.html`, its own id and DUR),
Audiowide label in pink glow (80px for 6-character labels, 112px for 4),
Inter caps line in pale cyan, the illustration in glowing cyan, the
synthwave grid behind the ruler. Only the label, the line and the
illustration change per chapter. Do not propose other skins unless asked.

## Files

`scripts/gen2.py` (template; brow shapes from `gen.py`) writes
`compositions/era*.html` and the hosts into `index.html`.
`scripts/lt-neon-border_card.html`: the registry's `lt-neon-border`
retargeted to the card slot (W/H/position set as numbers - a CSS
transform on its wrap is ignored).
Library recipes used inside the cards: text-shimmer (chrome sweep),
spring-pop (heart), blur-in (letters), svg-stroke-trace (draw-on).

## Render

Background = the finished video (captions, TV fx) cut to the cards'
part, re-encoded `-crf 12 -g 25`; `render --fps 25 --quality delivery
--video-frame-format png`; concat with the rest of the video by frame
(`trim=start_frame=`), audio copied; check_video with the card edges in
`--edges` and the transition windows in `--fx`. Share copy needs
`-maxrate 2.2M -bufsize 4M` to stay under 30 MB.
