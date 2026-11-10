---
name: basic
description: Cut a raw, single-take video or audio recording (a talking-head voice-over shot in one continuous take, full of retakes/false starts/flubs) down to a clean final edit that follows an intended script, using Whisper transcription cross-checked against silence detection for frame-accurate cut points, then assembled with ffmpeg. Use this skill whenever the user wants to edit raw footage against a script or scenario, mentions picking the "best take" from a recording, needs retakes/false starts removed from a single continuous take, or asks to transcribe-and-cut a video - even if they don't name Whisper or ffmpeg explicitly (e.g. "snimio sam video u jednom komadu, pomozi da ga isečem po scenariju", "imam sirov snimak sa dosta dublova, izvuci najbolje delove", "uporedi transkript sa scenariom i predloži montažu"). If the user also wants dynamic zoom/punch-ins added, see the separate "zoom" skill for that - use both together when both are asked for, but don't assume zoom is wanted just because this skill triggered.
---

# Basic video editing (cutting raw takes to match a script)

## Why this skill exists

A single continuous take full of retakes is deceptively hard to cut
correctly from a transcript alone. The first time this workflow was done by
hand, trusting Whisper's own segment *timestamps* from a single full-file
pass produced a cut plan where one sentence looked like it took 22 seconds
to say. It actually took 5.75 seconds; Whisper had merged 16 seconds of
silence and two false starts into that one segment. Trusting that
transcript for cuts would have shipped a video full of dead air.

Keep that lesson in mind: **the goal of this workflow is accurate cut
points, and Whisper alone does not reliably give you those on footage with
pauses, retakes, or repeated lines.** Everything below exists to compensate
for that.

## Workflow

### 1. Analyze the source

Probe the video for basic facts before doing anything else:

```bash
ffprobe -v error -show_entries format=duration,size -show_entries stream=width,height,codec_name,codec_type,avg_frame_rate -of default=noprint_wrappers=0 "<video>"
```

Extract mono 16kHz audio for transcription (Whisper wants this, and it's much
smaller/faster to process than the full video):

```bash
ffmpeg -y -i "<video>" -vn -ac 1 -ar 16000 audio.wav -loglevel error
```

If the user gave you a script/scenario file (txt, rtf, docx, etc.), read it
now so you have the intended content to compare against. An `.rtf` often
needs `textutil -convert txt -stdout file.rtf` (macOS) to get clean text
instead of raw RTF markup.

### Transcription keys (once per machine)

Transcription uses ElevenLabs, then Groq, then local Whisper (`scripts/stt.py`).
When the user asks to add a key, or a script reports a missing or invalid
key, open a hidden-input dialog - never ask for the key in chat, never print
it. ElevenLabs (the real key starts with `sk_`; the key ID shown in the key
list is not it):

```bash
K=$(osascript -e 'text returned of (display dialog "Nalepi ElevenLabs API ključ (počinje sa sk_):" default answer "" with hidden answer with title "ElevenLabs ključ" buttons {"Otkaži", "Sačuvaj"} default button "Sačuvaj" giving up after 280)' 2>/dev/null)
case "$K" in sk_*) mkdir -p ~/.config/elevenlabs && printf '%s' "$K" > ~/.config/elevenlabs/api_key && chmod 600 ~/.config/elevenlabs/api_key && echo saved;; *) echo "not saved: does not start with sk_";; esac; unset K
```

Groq: the same with `gsk_` and `~/.config/groq/api_key`. Then check it with
`python3 scripts/stt.py <short clip> --out /tmp/stt_check` - its first word
names the engine that answered. On Windows use a PowerShell `InputBox`.

### 2. Get a rough overview with a first-pass transcription

```bash
python3 scripts/stt.py audio.wav --language <lang> --out overview
```

This uses ElevenLabs Scribe v2, and Groq Whisper if ElevenLabs fails (keys in
`~/.config/elevenlabs/api_key` and `~/.config/groq/api_key`, never printed or
asked for in chat). Add `--terms "Name1, Name2"` when names or terms keep
coming out misspelled. Without a key or network, fall back to local Whisper
and tell the user:
`whisper audio.wav --language <lang> --model medium --output_format txt --output_format srt --output_dir .`

Use this ONLY to get a sense of overall content and roughly how far along the
recording different lines are. Do **not** use its segment start/end times as
real cut points yet - see "Why this skill exists" above. If the recording is
long, this can run in parallel with (or be skipped in favor of) step 3.

### 3. Find real speech boundaries with silence detection

This is the step that actually matters. Run:

```bash
python3 scripts/detect_bursts.py audio.wav > bursts.txt
```

This gives sample-accurate speech "bursts" (the complement of detected
silence), filtered to exclude sub-0.5s blips that are almost always breath
noise, not words. Trust these timestamps, not Whisper's.

Sanity-check scale: natural speech runs roughly 2-3 words per second. If a
burst's duration looks wildly out of proportion to how much text you'd
expect to fit in it, something is off.

### 4. Transcribe each burst in isolation

```bash
python3 scripts/transcribe_bursts.py audio.wav bursts.txt --language <lang>
```

By default each burst goes to ElevenLabs Scribe v2 as its own request, 4 at
a time; Groq Whisper takes over if ElevenLabs fails, and local Whisper
(`--model medium`, loaded once) if neither works. The script says on stderr
which engine ran - tell the user when it fell back. `--engine local` forces
local; `--terms` passes names/terms to spell correctly.

Either way it transcribes each burst as its own short clip (locally with `condition_on_previous_text=False` and `temperature=0`). That
combination is what actually surfaces hidden retakes: a burst that a
full-file pass labels as one clean line can turn out, once isolated, to
contain a false start immediately followed by the real delivery - entirely
invisible in the first-pass transcript, which had quietly merged or
suppressed the repeat.

Expect a recording with noticeable retakes to produce *more* bursts than
script lines - often several false-start fragments per line, especially on
whichever line the speaker struggled with most. That's normal; it's exactly
what this step is for.

### 5. Build the edit plan - and get it confirmed before cutting anything

Group the transcribed bursts by which line/idea of the script they belong
to. For each line, you'll typically see one of:

- **One clean, complete burst** - easy, that's the take.
- **A false start followed by a complete burst** - use the complete one,
  discard the fragment.
- **Multiple complete, full takes with the same wording** - these are
  genuine performance duplicates; you can't judge delivery/emotion from a
  transcript alone, so cut with a reasonable default (e.g. the later
  attempt, since people often settle into a take) and let the user pick in
  the Dublovi mode (below).
- **Multiple complete takes with genuinely different wording** (the speaker
  improvised differently each time) - this is a real content choice, not
  just a performance one. Present the alternatives to the user explicitly
  rather than silently picking - they may prefer their own improvised phrase
  over the scripted one, or vice versa.

For both kinds of duplicate takes, the user decides together with you, by
watching them: the takes go into the plan-editor's **Dublovi** mode (two
takes side by side, left / right, "Ovaj je bolji"), on EVERY video. Don't
describe takes in chat and don't ask "dubl 1 ili 2" there. Cut with your
default pick, list every duplicate in `takes_src.json` (plan-editor skill,
"Dublovi") and open the editor; swap the take in the cut if they pick
another one.

Then **write out the full plan as a message to the user**: the exact text
being kept for every line, its exact timestamp range, and what's being cut
and why (dead air, false starts, discarded alternate takes). Wait for
explicit confirmation before running any cutting command. This isn't a
formality - editing a video is destructive-feeling and hard to spot-check
without watching the output, so the user needs to see the plan to catch
problems (wrong take picked, a line that doesn't actually sound natural
stitched next to another) before render time is spent on it, not after.

If the user asks about total duration, just sum the kept segments' durations
- but flag that real final duration will be a bit longer once padding
between cuts is added (step 6).

### 6. Cut and assemble

Write the confirmed selections (one `start<TAB>end` pair per line, in output
order) to a file, then:

```bash
python3 scripts/guard_word_edges.py audio.wav selections.txt safe.txt --language sr --pre-pad 0.15 --post-pad 0.35
scripts/cut_and_concat.sh "<source_video>" safe.txt final_output.mp4
```

The guard keeps every cut outside words (see "Never cut inside a word"
under Tight pacing) - run it before every cut, with the pads you cut with.
For the user's videos, use the Tight pacing commands below instead.

Read the comment block at the top of `cut_and_concat.sh` before running it
manually or adapting it - it documents gotchas (ffmpeg stealing stdin from a
bash loop, fade-outs eating the last syllable of a word, why each clip needs
individual re-encoding before concat) that are easy to silently reintroduce
if rewritten from scratch instead of using the script as-is.

Defaults: 0.15s padding before each cut-in, 0.35s after each cut-out, a 5ms
fade-in only (no fade-out), re-encoded h264 (crf 18) + aac 192k per clip,
each clip cut to an exact frame count with its audio trimmed to that same
length, joined with the ffmpeg concat FILTER (never the concat demuxer -
see "Check every render" below). Override via `PRE_PAD`,
`POST_PAD`, `CRF`, `FADE_IN` environment variables if a specific cut needs
different handling (e.g. a line with a lot of trailing breath noise might
need more POST_PAD).

If a sentence's last letter still sounds clipped after a first pass, that
almost always means POST_PAD is too tight for that specific cut (the
speaker's trailing consonant extends further than the silence detector's
threshold caught) - increase it for that segment rather than reaching for a
fade, which just makes a tight cut sound worse, not better.

### Tight pacing - the user's standard

The default padding (0.15s / 0.35s) leaves a ~0.5s pause at every cut. The
user found that it broke the rhythm ("mora biti sve zbijenije i tečnije"),
so for their videos tighten every cut before assembling:

```bash
python3 scripts/tighten_cuts.py audio.wav selections.txt tight.txt --beat 1.0 --tail 2.0
python3 scripts/guard_word_edges.py audio.wav tight.txt safe.txt --language sr --pre-pad 0.04 --post-pad 0.08
PRE_PAD=0.04 POST_PAD=0.08 scripts/cut_and_concat.sh "<source_video>" safe.txt final_output.mp4 <abs workdir>
```

**Never cut inside a word - every kept word is spoken to its end (the
user's rule, 2026-11-10).** The -42 dB edges miss quiet word endings (a
soft final s / t / f, a vowel the speaker lets fade), and checking the
result by transcribing it does not catch a clipped ending - "kraj" for
"kraja" is still recognised. So `guard_word_edges.py` runs on EVERY cut,
right before cutting, with the same pads you cut with: it checks each edge
against ElevenLabs word times of the source and moves it out so the clip
ends >= 0.06s after its last word and starts >= 0.04s before its first
word - without reaching into the neighbouring word (a retake or a dropped
word right next to it). It prints every move with the word; tell the user
which edges moved. An edge it reports as `TIGHT` (the next word follows
with no gap) must be listened to, or cut somewhere else. If you cut with
other pads (the defaults 0.15 / 0.35, or a per-video change), pass those
same values as `--pre-pad` / `--post-pad`.

It moves each edge to where speech really starts / ends (-42 dB) and
splits any internal pause over 0.25s.

The numbers come from the user's two hand-edited reference reels (vodič
stila, 2026-11-10): median gap between words 0.06s, a new shot every ~3s,
cuts always between words (often mid-sentence, on a phrase boundary), and
only ONE pause left on purpose - a ~1s beat before the last line
(`--beat 1.0`) and 1.5-3s after it while the speaker silently looks into
the camera (`--tail 2.0`; music holds there, see the music skill's
`mix_bed.py`). Both extend only into real silence of the source; the script
says when there was less. If the speaker talks, laughs or reaches for the
camera right after the last line, drop `--tail` or shorten it.

On a real reel the tightening took 1:48
to 1:41 with every word intact. Afterwards, check by transcribing the
result: every word of the kept text must still be there. Timings of
anything placed on the old cut (close-ups, captions, title) must be
re-mapped through source time, not shifted by a constant.
When two separately cut parts are joined (e.g. main + outro), take the
join point from the first part's real frame count (nb_read_frames / fps),
not its container duration: on a real reel the 0.04s difference left one stray
frame of the wide shot between a close-up and the outro, and the outro's
first caption appeared a frame early. An overlay that ends at the join
must run to that frame.

### Check every render - before sending anything

On a real reel the user spotted one stray frame of the wide shot at
1:05 ("to ne sme da nam se dešava"). The real cause was bigger: the old
`cut_and_concat.sh` joined clips with the concat demuxer, which places each
clip by its container duration and AAC priming/padding, not by its real
frames. That left an 80 ms hole (2 frames) at 10 of the cuts - a frozen
frame on screen after re-encode - and the audio slowly drifted ahead of the
picture, so every overlay and caption timed from it landed a frame or two
off. The fixed script (gotcha #4 in its header) cuts each clip to an exact
frame count, pads/trims its audio to exactly that length and joins with
the concat filter.

Rules that follow from it:

- Run the checker on EVERY render (cut, zoomed, captioned, final) before
  sending it to the user:

  ```bash
  python3 scripts/check_video.py final.mp4 --ass captions.ass --edges edges.txt --cuts joins.txt
  ```

  `joins.txt` = every join of the cut list on the final timeline (running
  sums of each part's `durs.txt`, plus the part boundaries). Always pass
  it: a jump cut inside the same framing scores far below the scene
  threshold, so without it the checker missed a zoom change landing 3
  frames before a join on a real reel (1:15) - a 3-frame flash the user saw.

  It reports timestamp holes, lone frozen frames, audio vs video length,
  shots only a few frames long, captions shorter than 0.4s or starting /
  ending 1-3 frames from a picture cut, and overlay edges (`edges.txt`: one
  close-up / B-roll start or end per line, seconds) 2-5 frames from a cut.
  Exit 1 = something was found: fix it and render again; only "OK - nothing
  found" gets sent.
- Take every clip position from frame counts (`nb_frames / fps`, or the
  `durs.txt` the script writes), never from `format=duration`.
- When the cut changes, move close-ups, captions and the title through
  SOURCE time (old timeline -> source -> new timeline), never by a constant.
- An overlay that ends at a cut (a close-up before the outro) runs exactly
  to that cut's frame; a caption ends with its clip.
- Snap every zoom change, close-up end and caption edge that falls within
  6 frames of a join ONTO that join (a close-up start only when the join is
  just before it). Two picture changes a few frames apart always read as a
  glitch; on one frame they read as one cut.
- Give the very last segment a small tail (~0.5s) so the last caption and
  word aren't cut short.

### 7. Deliver

The master output from `cut_and_concat.sh` is full quality (re-encoded at
crf 18). If it needs to go through a tool with a file-size limit, make a
secondary compressed copy for that purpose rather than compressing the
master:

```bash
ffmpeg -nostdin -y -i final_output.mp4 -c:v h264_videotoolbox -q:v 65 -pix_fmt yuv420p -c:a aac -b:a 128k final_output_share.mp4 -loglevel error
```

(Apple VideoToolbox - ~4x faster than libx264 on an M-series Mac, same quality as
`-c:v libx264 -preset slow -crf 24`, which is the fallback when `h264_videotoolbox` is missing
and gives a ~40% smaller file when size matters more than time.)

If the user also wants dynamic punch-in/zoom crops for dynamics, see the
**zoom** skill - it can either take this skill's output and re-cut it, or
(more efficiently) you can combine both in one pass by writing the
per-segment filter chains from the zoom skill straight into
`selections.txt`'s third column before running `cut_and_concat.sh` once.
Rotation to vertical, if needed, is handled separately (not part of either
skill) - ask the user, since it's not always wanted.

## Instagram safe zone - for every title, graphic and caption

Instagram Reels draws its own UI over the video. Anything important under
it is unreadable: titles, words, logos, the product, doodles that carry a
joke. On a 1080x1920 frame:

- **Top - nothing above y = 260.** The "Reels / Friends" header and the
  status bar cover roughly the first 210-250 px.
- **Bottom - nothing below y = 1330.** From about y = 1380 down sit the
  avatars of friends who liked or reposted, then the username + Follow,
  the description and the progress bar.
- **Right - nothing in the button rail.** Like, comment, repost, send,
  save and the menu stack down the right side from about y = 950 to 1660,
  over x > ~860. Keep that block clear.
- **Sides - at least 150 px in from the left and right edge.** Phones
  taller than 9:16 fill the screen height and crop the sides of the video,
  centred - per side, in 1080-wide video pixels, `(1080 - 1920 / ratio) / 2`:

  | Screen | Phones | Cropped per side |
  |---|---|---|
  | 16:9 | iPhone 8 / SE | 0 |
  | ~19.5:9 | iPhone 12-16, Samsung Galaxy S | ~97 px |
  | 20:9 | Pixel, Galaxy A, many Xiaomi | ~108 px |
  | 21:9 | Sony Xperia | ~129 px |
  | 22:9 | Galaxy Z Flip (open) | ~147 px |

  So ~100 px is where the picture *ends* on the common phones, not a margin.
  150 px leaves ~50 px of air on iPhone/Samsung, ~40 on 20:9 and nothing
  cut on an Xperia. Nothing may touch or hug the visible edge. Decoration
  may come closer, never nearer than 120 px.

So every important element (captions included) sits inside x 150-930,
y 260-1330, and out of
the rail block (x > 860, y 950-1660). Below, above and beside that, only
decoration or texture that can be hidden.

Instagram crops the same video in two more places, whatever the phone: in
the main feed a Reel shows as 4:5 (about 285 px cut at the top and the
bottom) and the profile grid shows 3:4 (about 240 px top and bottom). Keep
the hook readable between y ~300 and 1330 and the cover's subject in the
middle.

Users caught every one of these on a real reel: a big opening title at
y 1300-1750 sat under the description, a halo and devil horns over the
speaker's head at y 75-230 sat under the "Reels / Friends" header, and a
"?" at x 1030 was jammed against the right edge. When a doodle belongs
above a head that sits too high in the frame, re-crop that shot from the
source with more headroom (move the person down) instead of letting the
doodle leave the safe zone.

Before showing frames for approval, draw the guide lines on a test frame
(y 260 and 1330, x 150 and 930, plus the rail block) and check the
bounding box of every graphic against them. Move it in if it crosses.

## Platform notes

- macOS has no GNU `timeout` by default - don't wrap ffmpeg calls in one;
  they're fast for short clips, and the calling tool's own
  background/timeout handling covers the long-running full-file pass in step
  2.
- Any time you write a `while read ...; done < file` loop yourself (rather
  than using the bundled scripts) and call `ffmpeg` inside it, add `-nostdin`
  to the ffmpeg call and redirect its stdin from `/dev/null` - otherwise
  ffmpeg consumes lines meant for the loop's `read`, corrupting which
  timestamp applies to which iteration with no obvious error.

## After the cut: zoom and captions go through the plan-editor

When the cut video will also get zoom/punch-ins (zoom skill) and/or
captions (subtitle skill), the user's standard is the **plan-editor**
skill: one interactive click-a-word tool where they decide the zoom with
you and fix caption text in the same sentences ("Izmeni tekst"). Keep the
kept text per clip from this skill's plan - it becomes that tool's
`sentences.txt` (one line per cut clip, same order as `selections.txt`).
