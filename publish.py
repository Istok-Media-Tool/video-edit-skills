#!/usr/bin/env python3
"""
Publish the local skills (~/.claude/skills) to this plugin repo for the course.

  python3 publish.py prepare [skill ...]
                               copy the skills in (all, or only the named ones),
                               swap personal examples for generic ones, check
                               for leaks, show what changed
  python3 publish.py push "what changed" [--major|--minor|--patch]
                               bump the version, commit and push

The repo keeps its own curated examples/ folders (never copied over), and a
leak check refuses to go on while a personal name or path is still there -
add new names to LEAKS / GENERIC in private_map.py (local, not in git)
when a new project brings them.
"""
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/.claude/skills")
DST = os.path.join(HERE, "video-edit", "skills")
SKILLS = ["basic", "plan-editor", "zoom", "subtitle", "title-behind", "music", "chapter-cards", "scrapbook"]
# The personal names live in private_map.py, next to this file and never
# committed (it would publish the very names it removes).
sys.path.insert(0, HERE)
from private_map import GENERIC, LEAKS
NOTE = "\n> `$SKILLS` below is the folder that holds this skill's folder: the parent of the base directory shown when the skill loads (the plugin's `skills/` folder).\n"

def sh(*a, **k): return subprocess.run(a, cwd=HERE, check=True, text=True, **k)

def prepare(only=None):
    for s in only or SKILLS:
        if s not in SKILLS:
            sys.exit(f"unknown skill {s} (one of {', '.join(SKILLS)})")
        # publishing only some skills: links into the others (shared scripts) become real files,
        # so a skill never points at a newer file the repo doesn't have yet
        sh("rsync", "-a", *(["--copy-links"] if only else []), "--delete", "--exclude", "__pycache__",
           "--exclude", ".DS_Store", "--exclude", "examples/", f"{SRC}/{s}/", f"{DST}/{s}/")
    bad = []
    for root, _, files in os.walk(DST):
        for f in files:
            p = os.path.join(root, f)
            try: t = open(p, encoding="utf-8").read()
            except UnicodeDecodeError: continue
            o = t
            for k in sorted(GENERIC, key=len, reverse=True): t = t.replace(k, GENERIC[k])
            if f == "SKILL.md" and "$SKILLS/" in t and NOTE.strip() not in t:
                a = t.index("---", 3) + 3; t = t[:a] + "\n" + NOTE + t[a:]
            if t != o: open(p, "w", encoding="utf-8").write(t)
            for n, line in enumerate(t.splitlines(), 1):
                if "/examples/" not in p and re.search(LEAKS, line):
                    bad.append(f"{os.path.relpath(p, HERE)}:{n}: {line.strip()[:120]}")
    sh("git", "add", "-A")
    print(subprocess.run(["git", "diff", "--cached", "--stat"], cwd=HERE, text=True, capture_output=True).stdout or "no changes")
    if bad:
        print("\nPERSONAL DATA LEFT - add a generic replacement to GENERIC, then run prepare again:")
        print("\n".join(bad)); sys.exit(1)
    print("clean - review the diff (git diff --cached), then: publish.py push \"what changed\"")

def push(msg, part):
    pj = os.path.join(HERE, "video-edit", ".claude-plugin", "plugin.json")
    sh("git", "add", "-A")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=HERE).returncode == 0:
        sys.exit("nothing changed - run prepare first (no version bump)")
    m = json.load(open(pj)); v = [int(x) for x in m["version"].split(".")]
    i = {"--major": 0, "--minor": 1, "--patch": 2}[part]; v[i] += 1; v[i + 1:] = [0] * (2 - i)
    m["version"] = ".".join(map(str, v)); open(pj, "w").write(json.dumps(m, indent=2, ensure_ascii=False) + "\n")
    sh("git", "add", "-A")
    sh("git", "-c", "user.name=vkasapic", "-c", "user.email=vkasapic@users.noreply.github.com", "commit", "-qm",
       f"{msg} ({m['version']})\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    sh("git", "push", "-q", "origin", "main")
    print("published", m["version"])

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "prepare": prepare(sys.argv[2:])
    elif len(sys.argv) > 2 and sys.argv[1] == "push": push(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "--minor")
    else: print(__doc__)
