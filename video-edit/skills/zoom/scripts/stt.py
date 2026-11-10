#!/usr/bin/env python3
"""
Speech-to-text for the editing skills: ElevenLabs Scribe v2 first, Groq
Whisper (groq_stt.py) as the fallback. Standard library only.

Why ElevenLabs first: on Serbian it splits words more correctly than Whisper
("Kurs se zove" vs Whisper's "Kurse zove"), answers in Latin script, its word
times start where the voice really starts, it bills per second (no 10 s
minimum per request, which matters when every burst is its own request) and
it takes 8+ requests at once with no per-minute cap.

Keys are read from files (or env vars) and never printed:
  ElevenLabs: ELEVENLABS_API_KEY or ~/.config/elevenlabs/api_key
  Groq:       GROQ_API_KEY or ~/.config/groq/api_key
When neither works the caller falls back to local Whisper (see available()).

transcribe() always returns the same shape, whichever engine answered:
  {"engine": "elevenlabs"|"groq", "text": str,
   "segments": [{"start", "end", "text"}], "words": [{"word", "start", "end"}]}

CLI (whole-file transcript):
  python3 stt.py audio_or_video --language sr [--terms "Masterbox, Claude"] [--out name]
  writes name.txt, name.srt and name.json (default name: the input's basename)
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import groq_stt

EL_URL = "https://api.elevenlabs.io/v1/speech-to-text"
EL_KEY_FILE = os.path.expanduser("~/.config/elevenlabs/api_key")
EL_MODEL = "scribe_v2"


class STTError(Exception):
    pass


def el_key():
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key and os.path.exists(EL_KEY_FILE):
        with open(EL_KEY_FILE, encoding="utf-8") as f:
            key = f.read().strip()
    return key


def available():
    """Which cloud engines have a key, in the order they are tried."""
    return [name for name, ok in (("elevenlabs", bool(el_key())), ("groq", groq_stt.available())) if ok]


def _multipart(fields, path):
    boundary = uuid.uuid4().hex
    body = b"".join(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
                    for k, v in fields)
    with open(path, "rb") as f:
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                 f"filename=\"{os.path.basename(path)}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
        body += f.read() + f"\r\n--{boundary}--\r\n".encode()
    return body, boundary


def segments_from_words(words, gap=0.6):
    """ElevenLabs returns words only; group them into caption-sized segments,
    breaking after sentence punctuation or a pause longer than `gap`."""
    segs, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is None or re.search(r"[.!?…]$", w["word"]) or nxt["start"] - w["end"] > gap:
            segs.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                         "text": " ".join(x["word"] for x in cur)})
            cur = []
    return segs


def elevenlabs(path, language=None, terms=None):
    key = el_key()
    if not key:
        raise STTError("no ElevenLabs API key")
    fields = [("model_id", EL_MODEL), ("timestamps_granularity", "word"), ("tag_audio_events", "false")]
    if language:
        fields.append(("language_code", language))
    for t in terms or []:   # keyterms cost ~20% extra, so only when asked for
        fields.append(("keyterms", t))
    body, boundary = _multipart(fields, path)
    req = urllib.request.Request(EL_URL, data=body, method="POST", headers={
        "xi-api-key": key, "Content-Type": f"multipart/form-data; boundary={boundary}",
        "User-Agent": "video-edit-skills/stt"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise STTError(f"ElevenLabs HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as e:
        raise STTError(f"ElevenLabs unreachable: {e.reason}")
    words = [{"word": w["text"].strip(), "start": float(w["start"]), "end": float(w["end"])}
             for w in d.get("words", []) if w.get("type") == "word" and w["text"].strip()]
    if language == "sr":
        for w in words:
            w["word"] = groq_stt.latin(w["word"])
    text = " ".join(w["word"] for w in words) or d.get("text", "").strip()
    return {"engine": "elevenlabs", "text": text, "segments": segments_from_words(words), "words": words}


def groq(path, language=None, terms=None, words=False):
    try:
        r = groq_stt.transcribe(path, language=language, words=words,
                                prompt=", ".join(terms) if terms else None)
    except groq_stt.GroqError as e:
        raise STTError(str(e))
    return {"engine": "groq", "text": r.get("text", "").strip(),
            "segments": [{"start": s["start"], "end": s["end"], "text": s["text"].strip()}
                         for s in r.get("segments", [])],
            "words": [{"word": w["word"].strip(), "start": w["start"], "end": w["end"]}
                      for w in r.get("words", [])]}


def transcribe(path, language=None, terms=None, words=False, engines=None):
    """Try ElevenLabs, then Groq. Raises STTError (with every engine's reason)
    when none works - the caller then uses local Whisper and tells the user."""
    errors = []
    for name in engines or available():
        try:
            if name == "elevenlabs":
                return elevenlabs(path, language, terms)
            if name == "groq":
                return groq(path, language, terms, words)
        except STTError as e:
            errors.append(str(e))
            print(f"{e} - trying the next engine.", file=sys.stderr)
    raise STTError("; ".join(errors) or "no ElevenLabs or Groq key")


def to_flac(src, dst):
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
                    dst, "-loglevel", "error"], check=True, stdin=subprocess.DEVNULL)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--language", default="sr")
    ap.add_argument("--terms", default="", help="comma-separated names/terms spelled as they should be")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    out = a.out or os.path.splitext(a.input)[0]
    terms = [t.strip() for t in a.terms.split(",") if t.strip()]
    with tempfile.TemporaryDirectory() as d:
        flac = os.path.join(d, "a.flac")
        to_flac(a.input, flac)
        engines = available()
        if "groq" in engines and os.path.getsize(flac) > 24 * 1024 * 1024:
            engines.remove("groq")   # over Groq's 25 MB upload limit
        try:
            r = transcribe(flac, a.language, terms, words=True, engines=engines)
        except STTError as e:
            sys.exit(f"{e}\nUse local whisper instead (and tell the user).")
    open(out + ".txt", "w", encoding="utf-8").write(r["text"] + "\n")
    with open(out + ".srt", "w", encoding="utf-8") as f:
        for i, s in enumerate(r["segments"], 1):
            f.write(f"{i}\n{groq_stt.srt_time(s['start'])} --> {groq_stt.srt_time(s['end'])}\n{s['text']}\n\n")
    json.dump({"engine": r["engine"], "segments": r["segments"], "words": r["words"]},
              open(out + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{r['engine']}: {out}.txt, {out}.srt, {out}.json")
