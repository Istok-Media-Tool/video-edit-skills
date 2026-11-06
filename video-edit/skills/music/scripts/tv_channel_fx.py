# TV channel-change effect on the era cuts: the old picture loses vertical
# hold and tears, turns into static on the cut, the new channel settles in.
import subprocess, sys, numpy as np
SRC, OUT = sys.argv[1], sys.argv[2]
W, H, FPS = 1080, 1920, 25
B = [float(x) for x in open("eras.txt").read().split()][1:]
ENV = [0.15, 0.3, 0.5, 0.7, 0.9, 1.0, 1.0, 1.0, 0.85, 0.6, 0.4, 0.22, 0.1]  # frames cut-7 .. cut+5
PRE = 7
rng = np.random.default_rng(7)
rows = np.arange(H)
def fx(img, k, seed):
    r = np.random.default_rng(seed)
    f = img.astype(np.float32)
    # vertical hold slips: picture rolls, a black sync bar runs through it
    roll = int(k * k * H * r.uniform(0.15, 0.6))
    f = np.roll(f, roll, axis=0)
    bar = (rows - roll) % H < int(60 * k)
    f[bar] *= 0.05
    # horizontal tearing, stronger in a few bands
    off = (np.sin(rows / r.uniform(20, 60) + r.uniform(0, 6)) * 25 * k
           + (r.random(H) < 0.03 * k) * r.uniform(-120, 120, H) * k).astype(int)
    idx = (np.arange(W)[None, :] - off[:, None]) % W
    f = f[rows[:, None], idx]
    # colour fringes
    s = int(22 * k)
    if s:
        f[..., 0] = np.roll(f[..., 0], s, axis=1)
        f[..., 2] = np.roll(f[..., 2], -s, axis=1)
    # snow (in 2x2 grains) and scanlines
    n = r.random((H // 2, W // 2), dtype=np.float32).repeat(2, 0).repeat(2, 1)[..., None] * 255
    a = min(1.0, k ** 1.6 * 0.95)
    f = f * (1 - a) + n * a
    f[::3] *= 1 - 0.35 * k
    f *= 1 + 0.25 * k * r.uniform(-1, 1)
    return np.clip(f, 0, 255).astype(np.uint8)
starts = []
for j, b in enumerate(B):
    c = round(b * FPS); s = c - PRE; starts.append(s)
    raw = subprocess.run(["ffmpeg", "-nostdin", "-i", SRC, "-vf", f"trim=start_frame={s}:end_frame={s+len(ENV)}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-loglevel", "error", "-"], capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    out = b"".join(fx(fr[i], ENV[i], j * 100 + i).tobytes() for i in range(len(ENV)))
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                    "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", f"tv_{j}.mp4", "-loglevel", "error"], input=out, check=True)
    print(f"cut {b:.2f}: frames {s}-{s+len(ENV)-1}")
args = ["ffmpeg", "-nostdin", "-y", "-i", SRC]; fc = []; last = "0:v"
for j, s in enumerate(starts):
    args += ["-i", f"tv_{j}.mp4"]
    fc.append(f"[{j+1}:v]setpts=PTS-STARTPTS+{s}/{FPS}/TB[t{j}]")
    fc.append(f"[{last}][t{j}]overlay=eof_action=pass[o{j}]"); last = f"o{j}"
open("fx_v15.txt", "w").write("".join(f"{s/FPS:.2f} {(s+len(ENV))/FPS:.2f}\n" for s in starts))
args += ["-filter_complex", ";".join(fc), "-map", f"[{last}]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium",
         "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy", OUT, "-loglevel", "error"]
subprocess.run(args, check=True)
