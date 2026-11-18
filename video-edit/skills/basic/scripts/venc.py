"""
Video encoder arguments for ffmpeg: ALWAYS Apple VideoToolbox (the user's rule,
2026-11-15: "za apsolutno sve ... uvek"). libx264 only on a machine without it
(Intel, Windows, Linux) - never by choice on this Mac.

VideoToolbox (h264_videotoolbox) runs on the M-series media engine: on a real
reel it encoded ~4x faster than libx264 -preset medium (3 s vs 13 s for 30 s
of 1080x1920). Its -q:v values below were picked to match libx264's SSIM at
the same CRF (CRF 18 -> q 75, 24 -> 65, 14 -> 85). On REKLAMA 1 (164 s,
1080x1920, graphics overlay) q 75 took 14 s vs ~2 min for libx264 -preset slow
-crf 15, SSIM 0.996 between the two, and check_video passed on the near-still
tail. VENC=x264 exists only for debugging; don't use it for delivery.

    from venc import venc
    cmd = ["ffmpeg", ..., *venc(18), "-pix_fmt", "yuv420p", out]
"""
import functools
import os
import subprocess


@functools.lru_cache(maxsize=1)
def has_videotoolbox():
    if os.environ.get("VENC") == "x264":
        return False
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=s=64x64:d=0.1", "-c:v", "h264_videotoolbox", "-q:v", "70", "-f", "null", "-"],
                       stdin=subprocess.DEVNULL, capture_output=True)
    return r.returncode == 0


def venc(crf=18, preset="medium"):
    """ffmpeg video-codec args for a libx264-style CRF."""
    if has_videotoolbox():
        q = 75 - (crf - 18) * 1.6 if crf >= 18 else 75 + (18 - crf) * 2.5
        return ["-c:v", "h264_videotoolbox", "-q:v", str(round(q))]
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf)]
