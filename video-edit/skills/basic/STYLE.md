# Istok house style - the default profile

Every skill in this package (basic, plan-editor, zoom, subtitle, title-behind,
music, chapter-cards, scrapbook) edits in the **Istok house style** unless the
person using it wants something else. This page is the summary; the numbers
and the reasons live in each skill.

## Personal profile - it wins

Before editing, read `~/.config/video-edit/style.md` if it exists. Its rules
override this page and every "Istok house style" rule in the skills.

When the person states a lasting preference that differs from the house style
("always bigger captions", "I never want music", "leave more pauses"), add one
line to that file (create it if missing), with the date:

```
- 2026-12-01 captions: Inter Bold 64, white, no box
```

One-off requests for a single video do not go in the file.

Machine settings go in `~/.config/video-edit/settings.json`, for example
`{"ui_language": "en"}` (the plan editor's language, `en` or `sr`).

## The house style in short

| Area | Default | Where |
|---|---|---|
| Pacing | tight: ~0.06 s between words, a new shot every ~3 s, one ~1 s beat before the last line, 1.5-3 s tail of the speaker looking into the camera | basic, "Tight pacing" |
| Cuts | never inside a word; every edge checked with `guard_word_edges.py` | basic |
| Takes | the person picks retakes with Claude (plan editor "Takes"), never silently | basic, plan-editor |
| Planning | every zoom / caption / B-roll / music place is decided together in the plan editor before rendering | plan-editor |
| Zoom | content-driven punch-ins, face centred with proper headroom, 1.0× shots framed too | zoom |
| Captions | phrase cards: hook card (Inter Bold 68, black box), body Inter Medium 54 on a ~85% black box, 3-8 words, one emphasis word per video, never over a face | subtitle |
| Title | big number / word behind the head, one or two lines on the chest | title-behind |
| Music | quiet bed ~22 dB under the voice for the whole video; its strongest moments land on the marked words; the video ends on the track's own final chord (never a fade) | music |
| Loudness | voice untouched, mix at -14 LUFS, true peak ≤ -1 dBFS | music |
| Format | 1080×1920 vertical reel, H.264 + AAC | all |
| Encoder | the hardware encoder of the machine: Apple VideoToolbox on a Mac (`-q:v 75` master, 85 intermediate, 65 share copy) | basic, "Encoder" |
| Transcription | ElevenLabs Scribe v2, then Groq Whisper, local Whisper only as a last resort; the language is detected | basic |

## What is NOT the house style

Examples in the skills name real reels (a real reel, "3000 reči", "REKLAMA 1").
They show where a rule came from; they are not content to reuse. Quotes in
Serbian are the original feedback behind a rule - the rule itself is what
counts.
