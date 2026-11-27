#!/usr/bin/env python3
"""
Check that this machine has everything the video-edit skills use.

  python3 setup_check.py            # table: OK / MISSING / optional, with the fix
  python3 setup_check.py --json     # the same as JSON (for Claude)

It installs nothing and never prints an API key - only whether one is there
and looks right. Run it once after installing the plugin, and again when a
script fails with "not found". Exit code 1 when something required is missing.

Platform: macOS (Apple Silicon or Intel). Captions are checked against faces
with Apple Vision and video is encoded with Apple VideoToolbox, so Windows and
Linux are not supported yet.
"""
import glob
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
rows = []


def add(name, ok, need, fix="", note="", used_by=""):
    rows.append({"name": name, "ok": bool(ok), "required": need == "required",
                 "fix": "" if ok else fix, "note": note, "used_by": used_by})


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def key_state(path, prefix):
    try:
        k = open(path).read().strip()
    except OSError:
        return False, "no key file"
    if not k.startswith(prefix):
        return False, f"key does not start with {prefix}"
    return True, "key present"


def main():
    mac = platform.system() == "Darwin"
    add("macOS", mac, "required", "these skills run on macOS for now",
        platform.platform(), "all")
    add("Python 3.9+", sys.version_info >= (3, 9), "required",
        "brew install python", platform.python_version(), "all")

    brew = shutil.which("brew")
    add("Homebrew", brew, "optional",
        '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
        "used for the install commands below", "setup")

    ff = shutil.which("ffmpeg")
    add("ffmpeg", ff, "required", "brew install ffmpeg", ff or "", "all")
    add("ffprobe", shutil.which("ffprobe"), "required", "brew install ffmpeg", "", "all")
    if ff:
        enc = run([ff, "-hide_banner", "-encoders"])
        flt = run([ff, "-hide_banner", "-filters"])
        add("ffmpeg: h264_videotoolbox", "h264_videotoolbox" in enc, "required",
            "brew reinstall ffmpeg (a macOS build has VideoToolbox)", "hardware H.264", "all")
        add("ffmpeg: ebur128 / loudnorm", "ebur128" in flt and "loudnorm" in flt, "required",
            "brew install ffmpeg", "loudness of the mix", "music")

    full = next((p for p in ("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg",
                             "/usr/local/opt/ffmpeg-full/bin/ffmpeg") if os.path.exists(p)), None)
    fflt = run([full, "-hide_banner", "-filters"]) if full else ""
    add("ffmpeg-full (libass, burns captions)", full and " subtitles " in fflt, "required",
        "brew install ffmpeg-full", full or "", "subtitle, plan-editor")
    add("rubberband", shutil.which("rubberband"), "required",
        "brew install rubberband", "time-stretch without pitch change", "music")
    add("swiftc (Xcode Command Line Tools)", shutil.which("swiftc"), "required",
        "xcode-select --install", "Apple Vision: faces / hands under captions", "subtitle, plan-editor")

    node = shutil.which("node")
    ver = run([node, "--version"]).strip() if node else ""
    major = int(ver.lstrip("v").split(".")[0]) if ver[1:2].isdigit() else 0
    add("Node.js 18+ (npx)", node and major >= 18 and shutil.which("npx"), "required",
        "brew install node", ver, "title-behind, chapter-cards, scrapbook (HyperFrames)")

    for mod, pip, need, use in [("numpy", "numpy", "required", "music, plan-editor, subtitle"),
                                ("scipy", "scipy", "required", "plan-editor"),
                                ("cv2", "opencv-python", "required", "plan-editor, subtitle"),
                                ("whisper", "openai-whisper", "optional",
                                 "local fallback when ElevenLabs and Groq both fail")]:
        add(f"Python: {pip}", importlib.util.find_spec(mod), need,
            f"python3 -m pip install --user {pip}", "", use)

    fonts = [p for d in (f"{HOME}/Library/Fonts", "/Library/Fonts", "/System/Library/Fonts")
             for p in glob.glob(f"{d}/Inter*")]
    add("font: Inter", fonts, "required",
        "brew install --cask font-inter (or download from rsms.me/inter)",
        f"{len(fonts)} files", "subtitle, title-behind")

    el = key_state(f"{HOME}/.config/elevenlabs/api_key", "sk_")
    gq = key_state(f"{HOME}/.config/groq/api_key", "gsk_")
    if os.environ.get("GROQ_API_KEY", "").startswith("gsk_"):
        gq = (True, "key in GROQ_API_KEY")
    add("ElevenLabs key (~/.config/elevenlabs/api_key)", el[0], "optional",
        "ask Claude to add the ElevenLabs key (a hidden input window opens)", el[1],
        "transcription, first choice")
    add("Groq key (~/.config/groq/api_key)", gq[0], "optional",
        "ask Claude to add the Groq key (a hidden input window opens)", gq[1],
        "transcription, second choice")
    if not el[0] and not gq[0]:
        rows.append({"name": "transcription engine", "ok": False, "required": True,
                     "fix": "add an ElevenLabs or a Groq key - without one, only slow local whisper is left",
                     "note": "", "used_by": "basic, zoom, plan-editor"})

    st = f"{HOME}/.config/video-edit/style.md"
    add("personal style (~/.config/video-edit/style.md)", True, "optional",
        note="present - its rules win over the house style" if os.path.exists(st)
        else "none - the Istok house style is used", used_by="all")

    if "--json" in sys.argv:
        print(json.dumps(rows, indent=1))
    else:
        w = max(len(r["name"]) for r in rows)
        for r in rows:
            mark = "OK " if r["ok"] else ("MISSING" if r["required"] else "-- optional")
            line = f"{mark:12s} {r['name']:{w}s}  {r['note']}"
            if not r["ok"] and r["fix"]:
                line += f"\n{'':12s} {'':{w}s}  fix: {r['fix']}"
            print(line)
    missing = [r for r in rows if r["required"] and not r["ok"]]
    if "--json" not in sys.argv:
        print("\n" + ("Everything required is installed." if not missing
                      else f"{len(missing)} required item(s) missing - see 'fix' above."))
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
