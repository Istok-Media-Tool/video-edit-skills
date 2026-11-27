# ISTOK video-edit skills

Claude Code skills for editing talking-head reels (Instagram / TikTok / Shorts).
Record everything in one take, with mistakes and retakes. Claude cuts it by your
script, then adds zoom, captions, B-roll, close-ups, a title behind your head,
music that hits your key words, and chapter graphics, all in the **Istok
house style**.

> **For ISTOK course students only.** The repository is public so installing
> and updating is one command, but the skills are licensed only to people
> enrolled in the ISTOK course. See [LICENSE](LICENSE).

## Install

In Claude Code:

```
/plugin marketplace add Istok-Media-Tool/video-edit-skills
/plugin install video-edit@video-edit-skills
```

Then ask Claude: **"Check my setup for the video-edit skills."** It runs
`setup_check.py` and tells you what is missing and how to install it. It
installs nothing without your OK.

### Turn on auto-update (once)

1. In Claude Code type `/plugin`
2. Marketplaces → `video-edit-skills` → **Enable auto-update**

New versions then download when Claude Code starts. To update by hand:
`/plugin marketplace update video-edit-skills`

## What you need

- **macOS** (Apple Silicon or Intel). Captions are checked against faces with
  Apple Vision and video is encoded with Apple VideoToolbox, so Windows and
  Linux are not supported yet.
- [Homebrew](https://brew.sh), then:
  `brew install ffmpeg ffmpeg-full rubberband node` and `brew install --cask font-inter`
- Xcode Command Line Tools: `xcode-select --install`
- Python 3.9+ with `numpy`, `scipy`, `opencv-python`
- For the title behind the head, chapter cards and scrapbook: the HyperFrames
  skills and CLI (`npx hyperframes`)

## Transcription (recommended: an ElevenLabs key)

Speech is transcribed in this order: **ElevenLabs** Scribe v2, then **Groq**
Whisper, then local Whisper. With a key, a transcript takes seconds instead of
minutes. One of the two keys is enough, and the free plans are fine.

The language is detected automatically. Any language works, and Serbian always
comes out in Latin script.

1. Create a key:
   - ElevenLabs: [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys)
     → Create API Key, enable Speech to Text. Copy the key that starts with `sk_`
     (it is shown only once).
   - Groq: [console.groq.com/keys](https://console.groq.com/keys) → Create API Key
     (starts with `gsk_`).
2. Tell Claude: **"Open a window so I can enter my ElevenLabs key"** (or Groq key).
   Paste the key into that window, **never into the chat**. It is stored only on
   your computer (`~/.config/elevenlabs/api_key` or `~/.config/groq/api_key`).

Without a key everything still works, only slower, through local
[Whisper](https://github.com/openai/whisper): `pip install -U openai-whisper`.

## What's inside

| Skill | What it does |
|---|---|
| `istok` | **the whole edit in one go** - say "apply the istok skill" (or "primeni istok skill") and Claude runs every skill below in order, with one editor round where you decide everything |
| `basic` | cuts a raw take by the script (transcription + silence detection), picks takes with you, tight pacing, checks every render |
| `plan-editor` | interactive editor in the browser: zoom by word, caption fixes, B-roll, close-up sliders, takes side by side, title, music places |
| `zoom` | content-driven punch-in zoom, centred on the face, never cutting off what you show |
| `subtitle` | phrase captions (ASS + libass) that break where you pause and never cover a face |
| `title-behind` | a huge title behind your head (you are cut out in front of it) |
| `music` | finds tracks, rearranges them so the strongest moments land on your key words, ends on the track's own final chord, mixes under the voice |
| `chapter-cards` | one planned card system for the parts of the video, with a timeline |
| `scrapbook` | TikTok "scrapbook" look around the head: cut-out letters, a paper note, marker doodles that follow the head through zooms |

## Your own style

The skills follow the Istok house style (summary: `video-edit/skills/basic/STYLE.md`). When
you tell Claude a lasting preference ("always bigger captions", "no music on my
videos"), it writes it to `~/.config/video-edit/style.md`, and from then on your
rules win over the house style.

The plan editor is in English. For Serbian, put `{"ui_language": "sr"}` in
`~/.config/video-edit/settings.json`.

## How to use it

Just talk to Claude, in any language. The fastest way: give it the raw
video and the script and say **"apply the istok skill"** - it does the
whole edit, step by step, and asks you only what is yours to decide. Or ask
for one step at a time:

- "I recorded the video in one take, cut it by the script" (attach the video and script)
- "Open the editor", "add zoom", "add captions", "put B-roll here"
- "Put the title MODA behind my head"
- "Add music that hits the punchline"
- "Make a card for each part"
