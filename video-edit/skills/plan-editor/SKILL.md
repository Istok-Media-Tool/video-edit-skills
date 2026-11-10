---
name: plan-editor
description: The user's STANDARD, complete editing workflow for every talking-head video after the cut - one interactive editor (browser pane, with the video and sound) where the user decides TOGETHER with Claude, word by word, where zoom changes land, fixes caption text, marks B-roll (video or image) from one word to another, and moves each caption screen up or down so it never covers the face; then one command renders the final video from what they sent. Use it EVERY time a video gets zoom/punch-ins, captions or B-roll, before rendering - and whenever the user wants to review or change the plan (e.g. "otvori plan", "otvori editor", "plan zuma", "hajde zajedno da odlučimo zum", "da ispravim titl", "pomeri titl", "titl prekriva lice", "ubaci b roll", "stavi sliku preko", "pomeri close up", "close up ranije / kasnije", "preslušaj", "poslao sam"). Works for any script and any language. Builds on the basic (cut), zoom (crop math) and subtitle (caption style) skills.
---

> `$SKILLS` below is the folder that holds this skill's folder: the parent of the base directory shown when the skill loads (the plugin's `skills/` folder).


# Plan editor - the complete edit after the cut

## Why this exists

Every rule here came from the user rejecting something:

- Zoom decided by Claude alone (one level per clip, or a punch-in at each
  sentence's midpoint) read as random. Zoom follows the script and is
  decided TOGETHER, on the actual words.
- Wrong caption words are fixed by the user in the same text, not in
  separate fields or by dictating corrections.
- They want to hear the video while deciding, so the editor runs in the
  browser pane with the render playing.
- The widest shot ("1,0×") must be centered with headroom like every other
  shot, not the raw frame.
- Captions must never move between screens, and must leave a brief empty
  moment between screens so the eye notices the change.
- Any caption screen can be moved up or down so it never covers the face.

Never render zoom, B-roll or captions from a plan the user hasn't seen in
this editor. Their "Pošalji plan" counts as approval to render.

## The look - approved by the user, keep it

The user confirmed this exact editor (reel "Moda nekad i sad",
2026-11-03) and wants it used the same way on EVERY video. New features
are ADDED to it as another mode or control in the same style; never
redesign, restyle or replace it with a different page.

- Same page as the Bočmanov mozak editor: player top-left with the caption
  drawn over it, under it one row per clip (number, ▶, zoom dropdown, text).
- Modes are pill buttons with icons in one row (the checked one filled in
  the accent color), not bare checkboxes.
- Next to the player (sticky): the current mode's help in a card with an
  accent rule, "Rečenica N  0:04 / 1:47" (live), a color legend (zum,
  B-roll, naslov) and the ▶ hint. Player ~300px high.
- The title range is a soft amber background on its words; "Pošalji plan"
  is the one filled (primary) button.
- Text reads like the caption on screen: one block per caption screen
  (thin rule on the left), one line per caption line, with the real line
  breaks - never one run-on sentence per row.
- Words at 20px, line-height 1.35, normal word spacing (each word is a
  clickable chip, but its padding is only 1px 3px - wider chips read as
  big gaps between words, which the user rejected).
- Dublovi: takes side by side, left / right, green frame on the one in
  the cut, "Ovaj je bolji" under each.
- Close-up (added 2026-11-04, approved for every video with inserts): one
  card per close-up, Početak / Kraj sliders with ‹ › one-frame buttons, the
  word the edge lands on, ▶ per transition, "Pogledaj" for the whole one;
  the close-up is previewed over the player. See "Close-up" below.
- To extend it: change `assets/plan_editor_widget.html` (and the scripts),
  regenerate, check one screenshot in the browser pane, and add the rule
  here.

## The flow

1. Cut the video (basic skill) and, if the footage is sideways, agree the
   rotation. Measure the head position per clip (zoom skill Step 2 ->
   `pos.json`).
2. Make a first render of the cut (plain or with a proposed zoom), its
   word times (`zoom/scripts/word_times.py render.mp4 words.json`) and the
   per-clip durations (ffprobe `build/clips/*.mp4`).
3. Captions (subtitle skill) timed against that render -> `captions.ass`.
   Every caption screen must START inside its own clip (at or after the
   clip's start in the render): a screen that starts in the previous
   clip's tail padding is assigned to that clip and the editor shows wrong
   rows. Snap such starts to clip start + 0.02s.
4. Write `sentences.txt` (one line per clip, the caption words) and your
   zoom proposal `plan.json`, then open the editor in the browser pane.
5. The user plans and clicks "Pošalji plan", then writes "poslao sam".
6. Render everything with `render_from_plan.py`, look at the check sheet,
   deliver as a new version (`..._v2.mp4`, `..._v3.mp4`; keep the old ones).

## What the editor does

Mode checkboxes at the top (Zum, Izmeni tekst, B-roll, Pozicija titla,
Naslov, Close-up, Dublovi, Muzika), one active at a time (the user asked to
choose up front). ALL modes are ALWAYS shown (the user, 2026-11-10:
"daj mi sve da vidim uvek"): one with nothing to work on yet (no captions
for Pozicija titla, no `--takes` for Dublovi, no `--closeups` for
Close-up) is dimmed, and clicking it says what it needs - never hide a mode. With none checked the plan is only shown; clicking a word
then plays the video from that word. Zoom marks (blue) and B-roll ranges
(green underline) stay visible in every mode.

- Text is shown as it will stand on screen: one block per caption screen,
  one line per caption line (the user asked for this; a run-on sentence
  per row was hard to read).
- Player (browser version): the render with captions drawn over it as
  they'll be burned. A play/stop button under each sentence number plays
  exactly that clip.
- **Zum**: a start-frame dropdown per sentence; clicking a word cycles a
  zoom change at that word: none -> 1,0× -> 1,5× -> 1,7× -> 2,0× -> 2,2×.
  Levels 0-4; "1,0×" = widest, rendered as the centered `--baseline` crop
  (~1.2×).
- **Izmeni tekst**: each sentence becomes an editable caption text (new
  line = new line on screen, blank line = next screen; the number of
  screens is locked because each has its own timing). Zoom marks and
  B-roll ends follow their word when words are added/removed.
- **B-roll**: click the start word, then the end word (may be in a later
  sentence; overlaps refused). Under the row: a field for a path, a bare
  file name or a description, an "Izaberi" button (file picker - only the
  file NAME comes through, never the folder) and remove.
- **Pozicija titla**: "Svi titlovi" at the top moves every caption screen
  at once to the same height (↺ sve = all back to default); below each
  sentence one slider per screen for exceptions (left = higher, right =
  lower, ↺ = default). Moving a slider jumps the player to that caption
  and shows it at the new height over the video.
- **Naslov**: the title / hook on top of the video (e.g. "MODA NEKAD I
  SAD"). A text box (new line = new line on screen), then click the word
  it starts on and the word it lasts until; the player shows it at its
  real place and "Pogledaj" plays that stretch; "Ukloni naslov" removes
  it. It reads the existing title from `--ass` (the first Dialogue whose
  Style isn't Default) - so put the title in captions.ass with its own
  style, never burn it separately.
- **Dublovi** (only when `--takes` is given): every sentence recorded more
  than once shows its takes side by side, left / right, each with its own
  player and an "Ovaj je bolji" button; the take in the cut has a green
  frame. The user asked for this instead of picking takes in chat - see
  "Dublovi" below.
- **Muzika**: the user and Claude decide TOGETHER where the music must
  hit, so the track's strongest beats are saved for those places and the
  sound follows the story and the picture (the user's request,
  2026-11-10). Clicking a word cycles: poenta (the track's strongest hit -
  punchline, key line, last sentence) -> naglasak (a strong bar start -
  an emphasised term, a number) -> promena (the track moves into a new
  section - a big turn in the story) -> none; each click also plays the
  word ±1.2 s. With `--music` the aligned track plays under the video
  from its chosen start ("Muzika u pregledu" toggles it), and grey ♪
  (hit) / ♩ (new section) marks show where the track's strong moments
  fall now - an unmarked ♪ is a wasted hit. Accents follow their word in
  Izmeni tekst.
- **Pošalji plan** sends a readable summary plus `PLAN_JSON`,
  `SENTENCES_JSON`, and when used `CAPTIONS_JSON` (`{"<dialogue idx>":
  text}`), `POS_JSON` (`{"<dialogue idx>": y}`), `BROLL_JSON`
  (`[{"from": [clip, word], "to": [clip, word], "media": "..."}]`),
  `TAKES_JSON` (`{"<clip>": <take index>}`, only clips whose take changed),
  `TITLE_JSON` (`{"text", "from": [clip, word], "to": [clip, word]}`, or
  `{"text": ""}` = remove; only when changed), `ACCENTS_JSON`
  (`[{"at": [clip, word], "kind": "poenta|naglasak|promena", "word"}]`,
  with a readable "Muzički akcenti" list; render_from_plan writes it to
  `work/accents.json`).

## Muzika - where the strongest beats go

ALWAYS propose the places yourself first (the user asked: "ti možeš dati
preporuku gde su ta mesta u videu"), then open the editor with them
pre-marked so the user only confirms or changes them. Read the sentences
and pick:
- **promena** (1-2): where the story turns - "Then something strange
  happened", the jump from the example to the viewer ("Since 2010...",
  "A danas..."), the start of the payoff. On the turn's FIRST word.
- **poenta** (1-2): the shock line and the last line - the word that
  lands it ("extinct", the final "can"). On that word, not the sentence start.
- **naglasak** (2-5): numbers, names, the key term ("overload",
  "Thirty percent").
Fewer is better: one start in a track can rarely serve more than 3-4
accents (align_music.py prints what landed). In chat: list each proposal
(word -> kind -> why) in one short line.

```bash
# accents.json = [{"at": [clip, word index in the shown sentence], "kind", "word"}]
python3 $SKILLS/music/scripts/track_map.py track.mp3 --bpm 120 --out map.json
python3 $SKILLS/music/scripts/align_music.py map.json --accents accents.json \
  --words words.json --durations 6.28,... --sentences sentences.txt --out editor/music.json
make_plan_widget.py ... --accents accents.json --music editor/music.json > editor/widget.html
serve_plan_editor.py editor/widget.html --media render.mp4 --music-file track.mp3 ...
```

Word indices: count the words of the sentence as shown (split on spaces,
punctuation stays on its word) - look them up by word, don't count by eye.
When the user sends ACCENTS_JSON, re-run align_music.py with
`work/accents.json`, regenerate the widget so they hear the new alignment,
and mix with `mix_bed.py --track-start <start>` (music skill).

## Dublovi - choosing between takes

Whenever the basic skill finds a sentence with more than one usable take
(two full deliveries, or different wording), don't describe them in chat
and don't ask "dubl 1 ili 2": put them in the editor. Cut with your default
pick, then:

```bash
python3 $SKILLS/plan-editor/scripts/make_take_clips.py <source> takes_src.json editor/takes \
  --pre-filter transpose=1
```

`takes_src.json`: `{"<clip, 0-based>": {"current": <take in the cut>,
"takes": [{"label": "Dubl 1", "start": s, "end": e, "text": "..."}, ...]}}`
with unpadded source times (as in cuts.txt). Add `--takes
editor/takes/takes.json` to `make_plan_widget.py` and `--takes-dir
editor/takes` to the server's runtimeArgs.

If `TAKES_JSON` comes back, `render_from_plan.py` stops on purpose: a
different take changes that clip's length, words and caption timing. Put
the chosen take's start/end into cuts.txt, re-cut, redo words.json /
durations / captions, set `current` to the new pick, and reopen the editor
before rendering zoom/captions.

## Close-up - moving inserts earlier / later

When the video has close-ups (full-frame inserts over the speaker, e.g. the
tablet photo while a name is spoken on a real reel), the user adjusts their
timing themself in the editor's **Close-up** mode ("da mogu da pomerim malo
napred ili nazad početak i kraj"). One card per close-up: a Početak and a
Kraj slider (1-frame steps, ‹ › = exactly one frame, ↺ back), the word the
edge now lands on, ▶ that plays just that transition, "Pogledaj" for the
whole close-up. Near a caption-screen or sentence edge (2 frames) a slider
snaps onto it, so a move never creates a 1-3 frame flash. Limits: no
overlap with the neighbours, at least 0.4s on screen, what the source file
allows (±1.5s).

```bash
python3 scripts/make_closeup_clips.py closeups.txt <srcdir> editor/closeups --pre-filter transpose=1
# media = a render WITHOUT the close-ups (they are previewed over it, locked to the timeline)
make_plan_widget.py ... --media base_nocu.mp4 --closeups editor/closeups/closeups.json > editor/widget.html
serve_plan_editor.py editor/widget.html --media base_nocu.mp4 --closeups-dir editor/closeups ...
```

The reply carries `CLOSEUPS_JSON` (all close-ups, new start/end, `off`
moved with the start). `apply_closeups.py plan_reply.txt old.txt new.txt
edges.txt` writes the new closeups file (+ edges for check_video.py); then
rebuild with it, burn the captions and run check_video.py as always.

## Opening the editor (browser pane - default)

```bash
python3 $SKILLS/plan-editor/scripts/make_plan_widget.py sentences.txt plan.json \
  --ass captions.ass --durations 6.28,6.04,... --media render.mp4 --words words.json \
  [--broll broll.json] [--takes editor/takes/takes.json] [--write-sentences sentences.txt] > editor/widget.html
```

- `sentences.txt` must be the caption words (the script refuses a word
  count mismatch, since plan indices refer to shown words;
  `--write-sentences` writes it from the captions).
- `plan.json`: `[{"s": <start level>, "m": {"<word index>": <level>}}]`.
  Propose zoom ON words that justify it (reveal, key term, personal
  question, punchline), pull back on words about scale, tightest at the
  climax, decisive jumps, at least one return to 1,0× after the opening.
- `--ass` = the captions as they will be burned, so the preview shows real
  timing and positions. `--broll` = a previous `BROLL_JSON` to show again.

Then a `.claude/launch.json` at the session root and `preview_start`:

```json
{"version": "0.0.1", "configurations": [{"name": "plan-editor", "runtimeExecutable": "python3",
 "runtimeArgs": ["<abs>/.claude/skills/plan-editor/scripts/serve_plan_editor.py",
                 "editor/widget.html", "--media", "render.mp4", "--port", "8765"], "port": 8765}]}
```

The server can't read files on an external drive (/Volumes/...: macOS
refuses the browser-pane process) - copy widget.html, the media and the
takes folder into the session folder and point launch.json there. The
server reads widget.html at start, so restart it (preview_stop /
preview_start) after regenerating.

The server writes the sent plan to `editor/plan_reply.txt`. When the user
writes "poslao sam", read that file. The "Plan je poslat" note clears on
any click, so a stale note never means an old plan - if the file is
missing, the plan wasn't sent; ask again. If the server had to restart,
don't lose unsent work: before restarting, read the page state from the
open tab (javascript_tool: `JSON.stringify({pos: Y, broll: B.map(x =>
({from: x.a, to: x.b, media: x.media}))})`, plus `T` if text was edited)
and regenerate with `--pos keep_pos.json --broll keep_broll.json` so it
comes back as unsent changes. Test new tool features in a SEPARATE tab
(tabs_create), never in the one the user is working in.

In chat: list your zoom proposals with the reason for each (word -> level
-> why), your music accent proposals when music is planned, and the modes. Don't restate the sentences.

Inline fallback (no render yet, or no browser pane): same command without
`--media/--words`, load the visualize read_me (interactive) once, and pass
the file VERBATIM as `widget_code` to show_widget. No playback there - the
chat widget can't carry the video's sound. The reply then arrives as the
user's chat message instead of a file.

## Rendering what they sent

```bash
python3 $SKILLS/plan-editor/scripts/render_from_plan.py project.json plan_reply.txt work/vN out_vN.mp4
```

`project.json` (paths relative to it; example in `examples/project.json`):
source, cuts, positions, pre_filter, ass, words, durations - the files from
"The flow". The script, in the only order that works:

1. writes plan.json / sentences.txt from the reply;
2. zoom: `build_zoom_selections.py` (each change 0.08s before its word; it
   STOPS if a word isn't found in the speech - fix by hand) ->
   `cut_and_concat.sh`;
3. B-roll on the zoom render (`apply_broll.py`: from-word start - 0.08s to
   to-word end + 0.10s, media covers the frame, short video holds its last
   frame, speaker audio stays). It STOPS if a `media` isn't a real file:
   find a bare name with
   `find /Volumes ~/Movies ~/Desktop ~/Downloads ~/Pictures -name '<name>' 2>/dev/null`
   (ask if several match), ask for / source a described one, put the path
   in the reply's BROLL_JSON and rerun;
4. captions: shifted to the new clip starts if durations changed, forced
   to the agreed rules (top anchor Alignment 8 / MarginV 1215; every
   screen ends 0.12s before the next starts), text fixes, then per-screen
   positions (event MarginV), burned with ffmpeg-full;
5. `work/vN/sheet.jpg`: frames before/after each zoom change, inside each
   B-roll range and on each moved caption. LOOK at it before delivering.
6. then run `$SKILLS/basic/scripts/check_video.py out_vN.mp4
   --ass <captions> --edges <overlay edges> --cuts <joins>` and send only when it prints
   "OK - nothing found" (basic skill, "Check every render").

If the user describes a change in chat instead, edit the files (or the
reply) and reopen the editor so they see it before rendering.

## Files

- `assets/plan_editor_widget.html` - the tool (placeholders `__SENTENCES__`,
  `__PLAN__`, `__CAPTIONS__`, `__BROLL__`, `__MEDIA__`, `__CAPSTYLE__`, `__POS__`, `__TAKES__`, `__TITLE__`, `__CLOSEUPS__`, `__ACCENTS__`, `__MUSIC__`).
  Change the tool only here; always generate, never hand-edit output.
- `scripts/make_plan_widget.py` - fills the template (caption screens with
  timing and position, word times for playback, caption style for preview).
- `scripts/serve_plan_editor.py` - local server for the browser pane
  (media with seeking, plan saved to a file).
- `scripts/render_from_plan.py` - the whole render from a sent plan.
- `scripts/apply_broll.py` - B-roll overlay (used by the render script).
- `scripts/make_take_clips.py` - preview clips + takes.json for the Dublovi mode.
- `scripts/make_closeup_clips.py` - close-up previews + closeups.json for the Close-up mode;
  `scripts/apply_closeups.py` - CLOSEUPS_JSON back into the closeups file.
- `scripts/apply_title.py` - TITLE_JSON into captions.ass (used by the render
  script, after text and position fixes, since it shifts Dialogue indices).
- `$SKILLS/subtitle/scripts/apply_caption_edits.py`,
  `apply_caption_positions.py` - caption text / position fixes.
- `$SKILLS/zoom/scripts/` - word_times, build_zoom_selections,
  compute_crop, cut_and_concat.
- Examples: `examples/project.json`, `$SKILLS/zoom/examples/sample/`.
