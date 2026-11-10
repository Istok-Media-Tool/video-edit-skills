#!/usr/bin/env python3
"""
Minimal Groq Whisper client (speech-to-text), standard library only.

Groq runs whisper-large-v3 ~190x faster than real time, so a burst or a whole
cut reel comes back in about a second - versus minutes for a local `medium`.

The API key is read from GROQ_API_KEY or ~/.config/groq/api_key. It is never
printed. available() tells the caller whether to use Groq or fall back to
local Whisper (no key, no network).

Limits worth knowing (console.groq.com/docs, checked 2026-11):
- 25 MB per file on the free plan (send 16 kHz mono FLAC, ~1 MB/min of speech)
- free plan: 20 requests/min - a 429 is retried after its retry-after
- each request is billed as at least 10 s of audio
"""
import json
import os
import time
import urllib.error
import urllib.request
import uuid

API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
KEY_FILE = os.path.expanduser("~/.config/groq/api_key")
MODEL = "whisper-large-v3"


class GroqError(Exception):
    pass


CYR = dict(zip("абвгдђежзијклљмнњопрстћуфхцчџш",
               ["a", "b", "v", "g", "d", "đ", "e", "ž", "z", "i", "j", "k", "l", "lj", "m",
                "n", "nj", "o", "p", "r", "s", "t", "ć", "u", "f", "h", "c", "č", "dž", "š"]))


def latin(text):
    """Serbian Cyrillic -> Latin, other characters untouched."""
    out = []
    for ch in text:
        lat = CYR.get(ch.lower())
        out.append(ch if lat is None else (lat[0].upper() + lat[1:] if ch.isupper() else lat))
    return "".join(out)


def api_key():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key and os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8") as f:
            key = f.read().strip()
    return key


def available():
    return bool(api_key())


def transcribe(path, language=None, prompt=None, words=False, model=MODEL, tries=6):
    """Transcribe one audio file. Returns Groq's verbose_json dict:
    text, segments[{start,end,text}], and words[{word,start,end}] if words=True."""
    key = api_key()
    if not key:
        raise GroqError("no Groq API key (GROQ_API_KEY or ~/.config/groq/api_key)")
    fields = [("model", model), ("response_format", "verbose_json"), ("temperature", "0"),
              ("timestamp_granularities[]", "segment")]
    if words:
        fields.append(("timestamp_granularities[]", "word"))
    if language:
        fields.append(("language", language))
    if prompt:
        fields.append(("prompt", prompt))

    boundary = uuid.uuid4().hex
    body = b"".join(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
                    for k, v in fields)
    with open(path, "rb") as f:
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                 f"filename=\"{os.path.basename(path)}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
        body += f.read() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "User-Agent": "video-edit-skills/groq",   # without one Groq's edge answers 403
    })
    for _ in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                res = json.loads(r.read().decode("utf-8"))
            if language == "sr":   # whisper often answers Serbian in Cyrillic; the reels use Latin
                res["text"] = latin(res.get("text", ""))
                for item in res.get("segments", []):
                    item["text"] = latin(item["text"])
                for item in res.get("words", []):
                    item["word"] = latin(item["word"])
            return res
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(e.headers.get("retry-after") or 20) + 0.5)
                continue
            msg = e.read().decode("utf-8", "replace")[:300]
            raise GroqError(f"Groq HTTP {e.code}: {msg}")
        except urllib.error.URLError as e:
            raise GroqError(f"Groq unreachable: {e.reason}")
    raise GroqError("Groq rate limit (429) did not clear")


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


if __name__ == "__main__":
    # Whole-file overview: python3 groq_stt.py audio.wav --language sr [--out overview]
    # writes <out>.txt and <out>.srt. For a first look only - cut points come from bursts.
    import argparse, subprocess, sys, tempfile
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--language", default="sr")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--out", default="overview")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as d:
        flac = os.path.join(d, "a.flac")
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-i", a.audio, "-vn", "-ac", "1", "-ar", "16000",
                        flac, "-loglevel", "error"], check=True, stdin=subprocess.DEVNULL)
        if os.path.getsize(flac) > 24 * 1024 * 1024:
            sys.exit("Audio is over Groq's 25 MB limit - skip the overview and go straight to bursts.")
        try:
            r = transcribe(flac, language=a.language, prompt=a.prompt or None)
        except GroqError as err:
            sys.exit(f"{err}\nUse local whisper for the overview instead (and tell the user).")
    open(a.out + ".txt", "w", encoding="utf-8").write(r["text"].strip() + "\n")
    with open(a.out + ".srt", "w", encoding="utf-8") as f:
        for i, s in enumerate(r.get("segments", []), 1):
            f.write(f"{i}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{s['text'].strip()}\n\n")
    print(f"{a.out}.txt, {a.out}.srt")
