#!/usr/bin/env python3
"""Writes a HyperFrames scene: a huge number/word BEHIND the speaker's head,
the speaker cut out on top, and a flag + one or two lines IN FRONT on the
chest. Approved on a real reel (2026-11-05).

Layers, bottom to top: (bg video in the root) -> dim + bottom shade ->
big text -> cutout video (same frames as the bg, transparent around the
speaker) -> flag + lines.

Usage:
  make_title.py --big 500 --lines "Engleskih reči|za 30 sekundi" --flag 🇬🇧 \
      --dur 4.0 --head-top 346 --sub-top 790 --cutout assets/cut.webm \
      --out compositions/title.html

--head-top  y (px, 1080x1920 frame) of the top of the hair in the first clip.
            The big text is placed so the head covers ~30% of it (the
            bottom of the middle characters), never more than half.
--sub-top   y of the lines: on the chest, below the chin, never over the face.
"""
import argparse
from html import escape

ap = argparse.ArgumentParser()
ap.add_argument("--big", required=True)
ap.add_argument("--lines", required=True, help="lines separated by |")
ap.add_argument("--flag", default="")
ap.add_argument("--dur", type=float, required=True, help="seconds, ends on the first cut")
ap.add_argument("--head-top", type=int, required=True)
ap.add_argument("--sub-top", type=int, required=True)
ap.add_argument("--size", type=int, default=0, help="big font px (default: fits the width)")
ap.add_argument("--cutout", default="assets/cut.webm")
ap.add_argument("--out", default="compositions/title.html")
a = ap.parse_args()

# Inter 900 digit/caps are ~0.62 em wide: fill ~88% of the 1080 width, max 340
size = a.size or min(340, int(950 / (0.62 * max(len(a.big), 1))))
# calibrated on an approved title (head top 346, 340px, box top 196):
# the box sits 0.44 em above the head top, so the head hides the lower ~30%
big_top = int(a.head_top - 0.44 * size)
line_size = max(64, min(100, int(size * 0.29)))
lines = "<br>".join(escape(x) for x in a.lines.split("|"))
flag = f'<span class="flag">{a.flag}</span>' if a.flag else ""
D = a.dur

html = f"""<template>
  <style>
    #title {{ position: absolute; inset: 0; font-family: Inter, sans-serif; color: #fff; }}
    #title .clip {{ position: absolute; }}
    #dim {{ inset: 0; background: rgba(0,0,0,.42); }}
    #floor {{ left: 0; right: 0; bottom: 0; height: 620px; background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.55) 100%); }}
    #big {{ left: 0; width: 1080px; top: {big_top}px; text-align: center; }}
    #big .in {{ font-weight: 900; font-size: {size}px; line-height: 1; letter-spacing: -0.02em; white-space: nowrap; }}
    #cut {{ left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover; }}
    #sub {{ left: 0; width: 1080px; top: {a.sub_top}px; text-align: center; }}
    #sub .flag {{ display: block; width: 880px; margin: 0 auto 6px; text-align: left; font-size: {int(line_size * 0.98)}px; line-height: 1.1; padding-left: 40px; }}
    #sub .lines {{ font-weight: 700; font-size: {line_size}px; line-height: 1.12; text-shadow: 0 4px 18px rgba(0,0,0,.5); }}
  </style>
  <div id="title" data-composition-id="title" data-width="1080" data-height="1920">
    <div id="dim" class="clip" data-start="0" data-duration="{D}"></div>
    <div id="floor" class="clip" data-start="0" data-duration="{D}"></div>
    <div id="big" class="clip" data-start="0" data-duration="{D}" style="z-index:2"><div class="in" data-var-text="bigText">{escape(a.big)}</div></div>
    <video id="cut" class="clip" src="{a.cutout}" muted playsinline data-start="0" data-duration="{D}" data-layout-allow-occlusion style="z-index:3"></video>
    <div id="sub" class="clip" data-start="0" data-duration="{D}" style="z-index:4"><div class="in">{flag}<div class="lines">{lines}</div></div></div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    tl.fromTo("#big .in", {{ opacity: 0, y: 140 }}, {{ opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }}, 0);
    {'tl.fromTo("#sub .flag", { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.25, ease: "back.out(2)" }, 0.25);' if a.flag else ''}
    tl.fromTo("#sub .lines", {{ opacity: 0, y: 30 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: "power2.out" }}, 0.32);
    // slow push on the big text while it holds
    tl.to("#big .in", {{ scale: 1.04, duration: {max(D - 0.8, 0.5):.2f}, ease: "none" }}, 0.5);
    window.__timelines["title"] = tl;
  </script>
</template>
"""
open(a.out, "w").write(html)
print(f"{a.out}: big {size}px at top {big_top}, lines {line_size}px at {a.sub_top}")
