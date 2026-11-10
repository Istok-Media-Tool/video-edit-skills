# Smoothed head anchor (centre x, hair top, face width, chin) per 0.08s, in 1080x1920 px,
# split into the stretches where the speaker's head is on screen (no close-up).
import json, statistics as st
F = {}
for l in open("faces.txt"):
    p = l.split()
    if p[1] == "none": continue
    n = int(p[0][2:7]); x, y, w, h = map(float, p[1:5])
    F[n] = (x * 1080, y * 1920, w * 1080, h * 1920)
J = [float(l) for l in open("joins_v12.txt") if l.strip()]
SEG = [(2.64, 4.96), (5.20, 8.40), (12.80, 18.22), (21.48, 24.45), (27.28, 31.59), (35.79, 39.28), (39.80, 45.54), (51.80, 59.19)]
def piece(t):  # which cut-list clip a time falls in, so smoothing never crosses a jump cut
    return sum(1 for j in J if j <= t + 1e-6)
out = []
for a, b in SEG:
    pts = []
    n = int(round(a * 25)) // 2 * 2
    while n / 25 < b:
        if n in F:
            x, y, w, h = F[n]; pts.append([n / 25, x + w / 2, y - 0.37 * w, w, y + h])
        n += 2
    # median of 5 inside the same clip, then a 3-tap average
    sm = []
    for i, p in enumerate(pts):
        nb = [q for q in pts[max(0, i - 2): i + 3] if piece(q[0]) == piece(p[0])]
        sm.append([p[0]] + [st.median(q[k] for q in nb) for k in (1, 2, 3, 4)])
    sm2 = []
    for i, p in enumerate(sm):
        nb = [q for q in sm[max(0, i - 1): i + 2] if piece(q[0]) == piece(p[0])]
        sm2.append([round(p[0], 2)] + [round(sum(q[k] for q in nb) / len(nb), 1) for k in (1, 2, 3, 4)])
    out.append({"a": a, "b": b, "pts": sm2})
    ws = [p[3] for p in sm2]
    print(f"{a:6.2f}-{b:6.2f}  n={len(sm2):3d}  cx {min(p[1] for p in sm2):.0f}-{max(p[1] for p in sm2):.0f}  top {min(p[2] for p in sm2):.0f}-{max(p[2] for p in sm2):.0f}  w {min(ws):.0f}-{max(ws):.0f}")
json.dump(out, open("head_track.json", "w"))
