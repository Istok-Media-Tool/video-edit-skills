#!/usr/bin/env python3
"""
Compute an ffmpeg crop+scale filter for a punch-in/zoom shot, anchored on a
subject's actual measured position, with a controlled headroom margin.

This exists because two naive approaches both produce visibly wrong results:

  - Cropping symmetrically around an eye-level point (rather than anchoring
    on the actual head-top) tends to leave WAY too much empty space above
    the head once you scale back up - on one real case this left ~17%
    headroom when ~9% looked right.
  - Reusing one segment's measured subject position for other segments in
    the same recording can be wrong even in a single continuous take: a
    person shifts in their seat over the course of several minutes, so a
    crop that's perfectly centered on segment 2 may run the head off-center
    (or, at tighter zoom, even clip it) in segment 9. ALWAYS measure the
    segment you're actually about to crop - see "How to measure cx/head_top_y"
    below - don't assume a global anchor holds for the whole recording.

Two modes:
  --zoom Z          crop at exactly Z times zoom (e.g. 1.7 for a 170% punch-in)
  --baseline        find the LOOSEST crop (least zoom) that still satisfies
                     the requested headroom within frame bounds - use this for
                     the "wide"/establishing shots so they're recentered and
                     headroom-corrected WITHOUT being zoomed in more than
                     necessary. Shots built with --baseline and shots built
                     with --zoom share the same cx/head_top_y anchor, so cuts
                     between them don't visibly jump the subject around -
                     that consistency is the actual point of this script.

How to measure cx/head_top_y for a segment (do this per segment you intend to
crop, not once for the whole video):
  1. Extract a representative mid-point frame of that segment:
     ffmpeg -nostdin -y -ss <mid_timestamp> -i source.mp4 -frames:v 1 ref.png
  2. Overlay a fine grid to read off pixel coordinates:
     ffmpeg -nostdin -y -i ref.png -vf "drawgrid=w=54:h=96:t=1:c=red@0.6" grid.png
     (54x96 gives a 20x20 grid on a 1080x1920 frame - adjust w/h for other sizes)
  3. View grid.png and read off: cx = x of the face/nose center,
     head_top_y = y of the top of the hair (not the eyes - headroom is
     measured from the very top of the head).
  4. Run this script with those numbers, then render a SINGLE test crop and
     look at it before committing to a full multi-clip render - do this even
     if it feels repetitive, because step 3's eyeballing is the one part of
     this whole pipeline that isn't sample-accurate.
  5. For a punch-in that spans several seconds, also spot check 2-3 more
     frames spread across the segment's duration (not just the one you
     measured) - the segment with the most body movement is the one most
     likely to reveal a margin that's too tight once the person leans in or
     tilts their head.

Headroom guidance: 0.09 (9%) read as correct in testing, with the specific
reasoning that vertical social platforms (Instagram/TikTok/Shorts) overlay
username/caption/fade UI across the top of the frame, so that margin is
functional space, not just aesthetic - don't go much below that for content
headed there. Pass --headroom to override per shot.

Usage:
    python3 compute_crop.py --cx 605 --head-top-y 450 --zoom 1.7
    python3 compute_crop.py --cx 605 --head-top-y 450 --baseline
    python3 compute_crop.py --cx 605 --head-top-y 450 --zoom 2.0 --headroom 0.12 \\
        --width 1080 --height 1920

Output (stdout): the filter chain, e.g.
    crop=636:1130:288:348,scale=1080:1920
If the source also needs a rotation fix (handled outside this skill), prepend
your own transpose/rotate filter to the output before using it.
"""
import argparse


def even(n):
    return int(round(n / 2) * 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cx", type=float, required=True, help="measured horizontal center of the subject's face")
    ap.add_argument("--head-top-y", type=float, required=True, help="measured y of the top of the subject's hair")
    ap.add_argument("--width", type=float, default=1080)
    ap.add_argument("--height", type=float, default=1920)
    ap.add_argument("--headroom", type=float, default=0.09, help="fraction of the CROPPED frame height to leave above the head")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--zoom", type=float, help="explicit zoom factor, e.g. 1.7 for a 170% punch-in")
    group.add_argument("--baseline", action="store_true", help="find the loosest crop that still satisfies --headroom (for recentered 'wide' shots)")
    args = ap.parse_args()

    W, H = args.width, args.height
    aspect = W / H

    if args.zoom:
        ch = even(H / args.zoom)
    else:
        # Loosest ch such that: y0 = head_top_y - headroom*ch >= 0
        # and y0 + ch <= H  =>  ch <= (H - head_top_y) / (1 - headroom)
        ch_max = (H - args.head_top_y) / (1 - args.headroom)
        ch = even(ch_max) if even(ch_max) <= ch_max else even(ch_max) - 2

    cw = even(ch * aspect)
    margin = args.headroom * ch
    y0 = even(args.head_top_y - margin)
    y0 = max(0, min(y0, int(H - ch)))
    x0 = even(args.cx - cw / 2)
    x0 = max(0, min(x0, int(W - cw)))

    zoom_equiv = H / ch
    print(f"crop={cw}:{ch}:{x0}:{y0},scale={int(W)}:{int(H)}")
    print(f"# equiv zoom {zoom_equiv:.2f}x, headroom margin {round(margin)}px ({args.headroom*100:.0f}% of crop height)", flush=True)


if __name__ == "__main__":
    main()
