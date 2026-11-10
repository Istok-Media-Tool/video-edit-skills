---
name: music
description: Add background music to a video so its strongest moments land on the video's key words - finding candidate tracks on Epidemic Sound (connector), mapping each track (beats, bars, sections, hits, build-ups, stems, seamless joins), ranking them by the places marked in the plan-editor, RE-ARRANGING the chosen track bar by bar (locally, or with Epidemic's EditRecording) so poenta / promena hit exactly, adding sound effects (riser, impact) where the music has nothing, ending every video on the track's own final chord (a clear closure, never a fade), and mixing it under the voice. Use this skill whenever the user wants muzika/music/soundtrack/background track added to a video, wants the music to hit specific moments, wants to change the music bed on a video that already has one, or asks to balance music vs. voice levels - even without naming ffmpeg or a specific music service (e.g. "dodaj muziku", "stavi neku pesmu u pozadini", "neka muzika udari na poenti", "preuredi pesmu", "muzika je prejaka/preslaba"). Normally applied to a video that's already cut (**basic** skill) and may already have captions (**subtitle** skill) - don't assume those steps are also wanted just because this skill triggered.
---

# Adding background music

## Why this skill exists

Claude can't hear music, so everything that matters about it is measured:
where the beats, bars, sections and hits are, which bars can be joined
without it being heard, where a re-arranged track really put its hits, and
how loud it sits under the voice. The user's goal (2026-11-10): pick the
track that fits the video best by the criteria we set, then re-arrange its
parts so the music hits on the key moments of the video.

## The ending - a clear, emphasized closure, every video

The user's rule (2026-11-10): **at the end of every video the music has a
clear, emphasized closure** - the track's own final chord / hit, never a
fade-out, never a cut. It is built into every step:
- `track_map.py` finds the closure (the track's last loud attack, how long
  it rings, strength 0..1: "završni akord odzvoni", "utapa se");
- `rank_tracks.py` weighs it (25 of 100) - a track that fades out ranks low;
- `arrange_music.py` ends every version on it: the final chord lands right
  after the last word (`--close-at`, default last word end + 0.12 s) and
  rings out untouched; verify_music.py checks it landed ("kraj");
- `mix_bed.py` sees that the track ends by itself: no fade, the final chord
  comes up to ~2 dB under the voice in 0.12 s, and if it rings past the
  video the last frame is held (better: a real tail - basic's
  `tighten_cuts.py --tail`, the speaker looking into the camera).

## The standard flow

Scripts are in `scripts/`; every step prints what it found, in Serbian
where the user reads it.

### 0. The places the music must hit

In the plan-editor's **Muzika** mode (plan-editor skill): Claude proposes
poenta / promena / naglasak first, the user confirms or changes them, the
editor sends `ACCENTS_JSON` (→ `work/accents.json`). Every script below
takes them as `--accents accents.json --words words.json --durations ...
--sentences sentences.txt`, or by hand as `--at "21.7:poenta,38.4:promena"
--video-len 45`. Fewer is better: 1-2 promena, 1-2 poenta, 2-5 naglasak.

### 1. Candidates from Epidemic Sound (connector)

`SearchRecordings` with the story's mood and tempo, `filter: {"vocals":
false}` (and `bpm`, `duration`, `moodSlugs` when they help), 6-8 tracks.
Each result gives what the scripts need - write it into `meta.json`:

```json
{"<file name>.mp3": {"id": "<recording id>", "bpm": 120, "title": "intuition", "vocals": false,
                     "drums": "stems/<x>_drums.mp3", "bass": "stems/<x>_bass.mp3"}}
```

Download the previews with `curl` (`audioFile.lqmp3Url`, and the DRUMS /
BASS stems' `lqmp3Url` - public CDN links, no login; one folder per job).
Previews are enough to map, rank and try arrangements; download the FULL
track (`DownloadRecording`, `fileType: WAV`, `stemType: FULL`) only for the
pick, before the final render. The browser pane is the fallback (see
"Sourcing without the connector").

### 2. Map every track

```bash
python3 scripts/track_map.py track.mp3 --bpm 120 [--drums d.mp3 --bass b.mp3] --out map.json --png map.png
```

- tempo, beats, bar starts (from the drum stem when given - no melody in
  the way), sections with level / shape, **hits** (a bar ≥ 4 dB louder),
  **builds** (the rising run-up into a hit), **bass** in / out (with the
  bass stem - a change the full mix can hide), the ending;
- **joins**: for every bar, the bars the music can jump to without it
  being heard (cost 0 = the natural next bar; < 0.5 usually inaudible,
  > 1 heard; relative to this track's typical jump). This is what makes
  re-arranging possible;
- **closure**: the track's own ending (see above).

Always pass `--bpm` from Epidemic's metadata: without it a 70 BPM track
came out at 140. 0.3 s per track.

### 3. Rank the tracks

```bash
python3 scripts/rank_tracks.py music/*.mp3 --meta music/meta.json --accents ... --work music/rank --out editor/music.json
```

Every track is arranged for the marked places (score only, no audio) and
scored out of 100 - six criteria, each measured 0..1, with the weights
agreed with the user (2026-11-10) in **`scripts/rank_weights.json`**:

| criterion | weight | measures |
|---|---|---|
| main_hits | 30 | poenta / promena land on a real event after arranging |
| closure | 25 | the track's own ending - a final chord / hit, not a fade |
| natural | 20 | the arrangement still sounds like the track: few joins, clean seams, no event reused for several places, no level jumps at joins |
| voice | 10 | the music is not busy under the voice (onset density) |
| arc | 10 | the music rises with the story |
| accents | 5 | naglasak places on a beat of the arrangement |

Tracks with vocals, shorter than the video + tail, or that can't be
arranged are not scored (listed at the bottom). When the user says what
matters more, change the numbers there (or pass `--weights`), not the code;
every track's points per criterion are in `<work>/rank.json`. It prints the
table and the next commands for the top tracks. 18 tracks: ~10 s.

### 4. Re-arrange the top tracks

**Locally - `arrange_music.py`** (any track):

```bash
python3 scripts/arrange_music.py map.json --accents ... --out-dir music/arr [--audio full.wav] [--variants 3]
```

It rebuilds the track bar by bar so each main place gets a real event
(poenta → the strongest hit / a bass entry, promena → a section start / a
hit / the bass), jumping only along the map's joins, as few jumps as
possible, without spending strong hits on unmarked places and without the
same drop serving two places. The gap between two places becomes a whole
number of beats and is stretched to fit with rubberband (pitch unchanged,
typically < 1.5 %); when it isn't a whole number of bars, the bar right
before the hit is played from a later beat, so the run-up into the drop
stays natural. Joins are 20 ms crossfades ending on the new downbeat. The
version ends on the track's own final chord right after the last word
(see "The ending"; `--ending any` only for a track that has none).
Writes `arr_A.wav`, `arr_B.wav`, `arr_C.wav` (different events each),
`arrange.json` and `music.json` for the editor. naglasak places are not
forced - it says which fall on a beat and suggests a sound effect for the
rest ("predlog efekta"). Tested: "intuition" (120 BPM), 3 main places on a
45 s and an 84 s video - all three on real hits, verified at -0 / +1 ms.

**Epidemic Sound - `epidemic_edit.py`** (Epidemic tracks):

```bash
python3 scripts/epidemic_edit.py request map.json --id <recording id> --accents ... --out music/ep/req.json
```

then the `EditRecording` tool with the printed `{"id", "input"}`,
`PollEditRecordingJob` until COMPLETED, and the edit's preview (or
`DownloadRecordingEdit` for the full WAV) with curl, then:

```bash
python3 scripts/epidemic_edit.py collect music/ep/edit1.wav --request music/ep/req.json \
  --source <full original> --bpm 120 --merge music/arr/music.json --out editor/music.json
```

What its editor can do - measured 2026-11-10, keep it in mind:
- it cuts on its own bar grid: two required regions only work when they
  are a whole number of bars apart in the edit (8 bars: made; 5.4 s /
  8.7 s apart: "COMPLETED" with no edit). `request` keeps only the places
  that fit the grid of the best one and says which are left for
  arrange_music.py;
- every region landed ~0.29-0.30 s LATER than asked, the same for all
  regions of one edit; `collect` measures it and shifts the whole edit
  (`--track-start <shift>` in mix_bed; the editor plays it shifted) -
  after that the regions sat within ±8 ms;
- the poll shows one edit per job; forceDuration and AVOID regions are
  untested on a successful edit (`--force-duration`, `--avoid`).
So for one or two places on a bar grid Epidemic's own joins; for more,
arrange_music.py. Both go into the editor side by side.

### 5. Verify every version - before the user hears it

```bash
python3 scripts/verify_music.py music/arr/arr_A.wav --arrange music/arr/arrange.json --variant A [--source full.wav]
```

Measured on the audio, not taken from the plan: where each place's event
really landed (cross-correlation with the source bar, ms), every join
(a click, a level jump, a timbre jump against the track's own bar lines),
holes in the music (against the source at the same place - a rest the
track has anyway is fine), length. Epidemic edits: `--regions req.json
--source full.wav` (collect runs it). Only "OK - nothing found" goes to
the editor; "preslušaj" lists the seams to listen to. Tested: a 120 ms
hole and a 3-sample click at a join were caught; the real joins were not
flagged.

### 6. The user picks by ear in the editor

`make_plan_widget.py ... --music editor/music.json`, and
`serve_plan_editor.py ... --music-file arr_A.wav arr_B.wav ...`. Buttons
A / B / C (D... for Epidemic edits) switch the version; on the words: ♪ a
hit, ♩ a new section, ✂ a join of the arrangement (listen to those). The
sent plan's `MUSIC_JSON` names the pick.

### 7. Sound effects where the music has nothing

From arrange_music's "predlog efekta" (impact on a poenta with no real
hit, hit on a naglasak with no beat, riser into a hit with no build-up):
- **Epidemic** (tested): `SearchSoundEffects` ("riser cinematic short",
  "impact hit punchy", duration filter), `DownloadSoundEffect`
  (`fileType: WAV`) → curl;
- **ElevenLabs** when a specific sound is needed (`creative_generate_in_flow`,
  `node_type: "sfx"`, model `eleven_text_to_sound_v2`; the file from
  `creative_get_generations`' `full_res_url`) - not tried yet: check that
  the file downloads before relying on it. ElevenLabs does not re-arrange
  an existing track; with `eleven_music_*` it can compose a NEW one from a
  description of the video's structure - only when no candidate fits, and
  map it like any other track.

`sfx.json`: `[{"file": "sfx/riser.wav", "at": 21.67, "align": "peak"},
{"file": "sfx/hit.wav", "at": 30.17, "align": "peak", "peak_db": -12}]` -
`peak` puts the sound's loudest 50 ms on `at` (a riser's tail rings on
after the hit; measured ±5 ms), `start` / `end` align the file's edges.

### 8. Mix

```bash
python3 scripts/mix_bed.py video.mp4 music/arr/arr_A.wav out.mp4 --words words.json \
  [--track-start 0 | <shift of an Epidemic edit>] [--sfx sfx.json] [--sting hit.wav --sting-at 101.3]
```

The user's reference style (vodič stila, 2026-11-10): quiet music under
the WHOLE video, `--under 22` dB under the voice's mean, so no pause is
dead silent; after the last word the track's final chord comes up and
rings out while the speaker silently looks into the camera (basic's
`tighten_cuts.py --tail`) - no fade (see "The ending"). Only a track that
runs on past the video (not arranged) is lifted `--lift 8`, faded, ~0.5 s
of silence, then an optional sting (~-5 dBFS).
The voice is never touched (amix `normalize=0`); the whole mix goes to
-14 LUFS with the true peak ≤ -1 dBFS after AAC. Check: `ebur128=peak=true`
on the output, then listen to the last word, the final chord and the ✂ seams.
A negative `--track-start` delays the track (an edit whose regions landed
early).

## Doing it by hand (no accents, or a quick bed)

- Measure the voice: `ffmpeg -nostdin -i video.mp4 -af volumedetect -f null -`.
- Mix with `amix=...:normalize=0`. **The gotcha that happened:** amix's
  default `normalize=1` scales the SUM down - it pulled the voice's peak
  down 6 dB (-10.6 → -16.5 dB) while the music was already 24 dB under.
- Verify: the output's `max_volume` within ~1 dB of the voice-only one.
- Start the window on a downbeat (track_map), never mid-bar; a video that
  opens calm and climbs wants a window that starts low and reaches a hit
  near the last sentence.

## Sourcing without the connector

The built-in browser pane has its own login (not the user's Chrome);
download links are session-bound (curl of them gets a login page); the
pane can't reach local files for "search by video". Claude narrows the
candidates (names, moods, BPM, durations - it can't listen), the user
previews and picks by ear, then the file comes from the user's download
folder.

## Delivering

The mix is full quality; make a compressed copy for size-limited tools
instead of compressing the master:

```bash
ffmpeg -nostdin -y -i output.mp4 -c:v h264_videotoolbox -q:v 65 -pix_fmt yuv420p -c:a aac -b:a 128k output_share.mp4 -loglevel error
```

(VideoToolbox is ~4x faster than libx264 on an M-series Mac at the same
quality as `-c:v libx264 -preset slow -crf 24`, the fallback.)

## Different track per section (era / chapter) - decades reel, 2026-11-05

A soft 0.3 s crossfade between tracks read as "konfuzno, nema jasnih prelaza".
What fixed it (a project script, not in this skill yet):
- **Hard switch on the cut**: each track starts at a section boundary from
  its own first strong downbeat; the old track fades out in 0.3 s ending
  exactly at the cut.
- **A short transition sound** between sections (radio tuning for eras):
  a different 0.4 s slice of the SFX each time, ending ~0.04 s after the
  cut, at about -27 LUFS.
- **Each segment gain-matched** to the same LUFS (-30), then
  `sidechaincompress` keyed by the voice (threshold 0.02, ratio 5, attack
  15, release 350) - music comes up in pauses and on the switches.
- **The picture follows the sound** (user: "menjanje stanica mora da prati i
  slika"): `scripts/tv_channel_fx.py video.mp4 out.mp4` (reads `eras.txt`)
  puts a TV channel change on each section cut, 13 frames (cut-7 .. cut+5).
  Run `check_video.py` with `--fx fx_vN.txt` - the static would otherwise
  count as many cuts.

## Files

- `scripts/track_map.py` - the map of a track (step 2).
- `scripts/align_music.py` - the best start with no editing (used by rank).
- `scripts/rank_tracks.py` + `scripts/rank_weights.json` - the ranking (step 3).
- `scripts/arrange_music.py` - local re-arrangement (step 4).
- `scripts/epidemic_edit.py` - Epidemic EditRecording request / collect (step 4).
- `scripts/verify_music.py` - the check of every version (step 5).
- `scripts/mix_bed.py` - the mix with lift, sting and sound effects (step 8).
- `scripts/tv_channel_fx.py` - the per-section TV effect (decades reel).
- `scripts/venc.py` - link to `basic/scripts/venc.py` (video encoder args).
