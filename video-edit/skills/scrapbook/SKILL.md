---
name: scrapbook
description: TikTok "scrapbook" look around the speaker's head in a talking-head reel - ransom-note letters cut from paper, a torn notebook note with tape, white marker doodles (halo, sparkles, arrow) that stick to the tracked head and follow it through zooms. Made with HyperFrames. Use when the user wants scrapbook estetiku, elemente oko glave, nalepnice/doodle oko subjekta, "kao na TikToku oko glave", or stickers that follow the head.
---

# Scrapbook around the head

Approved on the decades reel (v18, 2026-11-05), replacing the chapter cards
("Bez kartica onda"). Same rule as chapter-cards: one planned
constellation, never random - only the text changes per part.

## The constellation (relative to the head, w = face width)
- ransom-note year LEFT of the head (right edge cx-0.62w, bottom top+0.25w),
  each character on its own paper tile (font/colour/tilt seeded), tape.
- torn notebook note RIGHT of the head (cx+0.62w, top+0.55w) with the
  part's line in Caveat (64px, 52px past 11 chars, one line); when the head
  fills the frame it moves onto the shoulder (x 1050-NW, chin+0.25w).
- white marker halo over the hair, 3 sparkles by the ear (gentle rock),
  a marker arrow from the note to the head.
- entrance: stickers slap on (back.out, 0.22s), then marker draws on.
- nothing in close-ups (the tracker would find the photo's face) and none
  over the title; parts start after the transition static (cut+0.24).

## Steps
1. Frames every 2nd frame at 360x640 of the finished video
   (`select='not(mod(n,2))'`, `-frame_pts 1`), `swiftc -O faces.swift`,
   `faces_bin dir > faces.txt` (Vision, largest face).
2. `head_track.py`: edit SEG (head-visible stretches = everything minus
   close-ups/title); median-5 + mean-3 smoothing that never crosses a
   cut-list join, so the stickers jump with the head on a zoom change.
3. `gen_scrap.py` (edit ERA texts) in a HyperFrames project whose bg is
   the finished video part (`-crf 12 -g 25`), snapshot a proposal sheet,
   then render / concat / check_video (stretch edges in `--edges`, fx
   windows in `--fx`) like the chapter-cards skill.
