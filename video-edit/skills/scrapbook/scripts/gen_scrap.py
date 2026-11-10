# Scrapbook around the speaker's head: the same constellation every time,
# pinned to the tracked head. Only the year and the note change per era.
#   year  - ransom-note letters cut from paper, taped, left of the head
#   note  - torn notebook scrap with the era line, right of the head
#           (below the shoulder line when the head fills the frame)
#   halo  - a white marker scribble over the head, 3 sparkles by the ear
import json, math, random
TR = json.load(open("../head_track.json"))
ERA = {5.20: ("1970-e", "hipi mekoća"), 12.80: ("1980-e", "jako i puno"), 21.48: ("1990-e", "tanke pincetom"),
       27.28: ("2000-e", "Y2K linija"), 35.79: ("2000-e", "Y2K linija"), 39.80: ("2010-e", "pune obrve"), 51.80: ("2020-e", "laminacija")}
TILE_BG = ["#fbfaf5", "#f4e04d", "#151515", "#e94f37", "#9ad1d4", "#f6c1cc", "#e9e4d8"]
TILE_FG = {"#151515": "#fbfaf5", "#e94f37": "#fff"}
TILE_FONT = ["'Anton'", "'Abril Fatface'", "'Courier Prime'", "'Archivo Black'", "'Playfair Display'", "'Bebas Neue'"]
YW, YH, NW, NH = 500, 140, 380, 150          # year block, note block
FONTS = ("https://fonts.googleapis.com/css2?family=Anton&family=Abril+Fatface&family=Courier+Prime:wght@700&family=Archivo+Black"
         "&family=Playfair+Display:wght@900&family=Bebas+Neue&family=Caveat:wght@700&display=swap")
def clamp(v, lo, hi): return max(lo, min(hi, v))
def place(p):
    t, cx, top, w, chin = p
    yx = clamp(cx - 0.62 * w - YW, 30, 1050 - YW); yy = clamp(top + 0.25 * w - YH, 130, 1700)
    nx = cx + 0.62 * w
    if nx + NW <= 1060:
        ny = top + 0.55 * w
    else:                        # head fills the frame: the note goes on the shoulder
        nx = 1050 - NW; ny = chin + 0.25 * w
    hx, hy, hs = cx, top - 0.06 * w, w / 270
    sx, sy = clamp(cx + 0.55 * w, 40, 1000), top + 0.15 * w
    return dict(year=(yx, yy), note=(nx, clamp(ny, 140, 1080)), halo=(hx, hy, hs), spark=(sx, sy))
def tiles(txt, seed):
    r = random.Random(seed); out = []
    for i, ch in enumerate(txt):
        bg = TILE_BG[(i * 3 + seed) % len(TILE_BG)]; fg = TILE_FG.get(bg, "#151515")
        f = TILE_FONT[(i * 5 + seed) % len(TILE_FONT)]; rot = r.uniform(-9, 9); dy = r.uniform(-8, 8); fs = r.choice([88, 96, 106])
        out.append(f'<span class="tl" style="background:{bg};color:{fg};font-family:{f};font-size:{fs}px;transform:translateY({dy:.0f}px) rotate({rot:.1f}deg)">{ch}</span>')
    return "".join(out)
HALO = "M -150 18 C -110 -30, -40 -48, 0 -50 C 50 -52, 120 -32, 152 14 M -138 26 C -96 -18, -30 -38, 8 -40 C 60 -40, 118 -20, 140 22"
STAR = "M 0 -22 C 3 -6, 6 -3, 22 0 C 6 3, 3 6, 0 22 C -3 6, -6 3, -22 0 C -6 -3, -3 -6, 0 -22 Z"
css = """
#scrap { position:absolute; inset:0; }
#scrap .clip { position:absolute; inset:0; }
#scrap .el { position:absolute; left:0; top:0; }
#scrap .yr { width:%dpx; height:%dpx; display:flex; align-items:center; justify-content:center; gap:4px; filter:drop-shadow(0 6px 10px rgba(0,0,0,.35)); }
#scrap .tl { display:inline-block; padding:4px 10px 2px; line-height:1; font-weight:900; box-shadow:0 0 0 3px #fff; }
#scrap .tape { position:absolute; width:140px; height:40px; background:rgba(240,228,190,.72); box-shadow:0 1px 3px rgba(0,0,0,.15); }
#scrap .yr .tape { left:-26px; top:-14px; transform:rotate(-24deg); }
#scrap .nt { width:%dpx; height:%dpx; padding:34px 18px 0 48px; font-family:'Caveat',cursive; font-weight:700; font-size:64px; line-height:1; color:#1d2a6b;
  background:repeating-linear-gradient(180deg,#fffdf6 0 46px,#b9cde8 46px 48px); background-position:0 16px;
  clip-path:polygon(0 0,100%% 0,100%% 88%%,94%% 100%%,86%% 90%%,76%% 99%%,64%% 91%%,52%% 100%%,40%% 90%%,28%% 99%%,16%% 91%%,6%% 100%%,0 92%%);
  filter:drop-shadow(0 6px 10px rgba(0,0,0,.3)); }
#scrap .nt::before { content:""; position:absolute; left:34px; top:0; bottom:0; width:2px; background:#e88; }
#scrap .nw { position:absolute; left:0; top:0; }
#scrap .nw .tape { right:-30px; top:-12px; transform:rotate(28deg); width:110px; }
#scrap svg.dd { position:absolute; left:-170px; top:-80px; width:340px; height:140px; overflow:visible; }
#scrap svg.dd path, #scrap svg.sp path { fill:none; stroke:#fff; stroke-width:7; stroke-linecap:round; stroke-linejoin:round; filter:drop-shadow(0 2px 3px rgba(0,0,0,.45)); }
#scrap svg.sp { position:absolute; left:-40px; top:-60px; width:120px; height:160px; overflow:visible; }
""" % (YW, YH, NW, NH)
body, js = [], []
for si, seg in enumerate(TR):
    a, b = seg["a"], seg["b"]
    if a not in ERA: continue                 # the 60s part is a close-up of the photo: no head
    yr, note = ERA[a]; d = round(b - a, 2); g = f"s{si}"
    body.append(f'''<div id="{g}" class="clip" data-start="{a}" data-duration="{d}">
  <div class="el" id="{g}h"><svg class="dd" viewBox="-170 -80 340 140"><path pathLength="1" d="{HALO}"/></svg></div>
  <div class="el" id="{g}s"><svg class="sp" viewBox="-40 -60 120 160"><path pathLength="1" d="{STAR}"/><path pathLength="1" transform="translate(48 34) scale(.6)" d="{STAR}"/><path pathLength="1" transform="translate(6 78) scale(.42)" d="{STAR}"/></svg></div>
  <div class="el" id="{g}y"><div class="yr" id="{g}yi"><span class="tape"></span>{tiles(yr, si)}</div></div>
  <div class="el" id="{g}a"><svg class="sp" viewBox="-40 -60 120 160"><path pathLength="1" d="M 60 70 C 30 60, 6 34, 0 0 M -14 18 L 0 0 L 16 14"/></svg></div>
  <div class="el" id="{g}n"><div class="nw" id="{g}ni" style="transform:rotate(4deg)"><div class="nt" style="white-space:nowrap;font-size:{64 if len(note) <= 11 else 52}px">{note}</div><span class="tape"></span></div></div>
</div>''')
    pts = seg["pts"]; P = [place(p) for p in pts]
    def path(key, fn):
        q = f"#{g}{key}"; js.append(f'tl.set("{q}",{fn(P[0])},{a});')
        for k in range(1, len(pts)):
            t0 = round(pts[k - 1][0], 2); dt = round(pts[k][0] - pts[k - 1][0], 2)
            # a jump between clips (zoom change): move in one frame, else glide
            js.append(f'tl.to("{q}",{{...{fn(P[k])},duration:{min(dt, .08) if dt < .3 else .04},ease:"none"}},{max(t0, a)});')
    path("y", lambda p: f'{{x:{p["year"][0]:.0f},y:{p["year"][1]:.0f}}}')
    path("n", lambda p: f'{{x:{p["note"][0]:.0f},y:{p["note"][1]:.0f}}}')
    path("h", lambda p: f'{{x:{p["halo"][0]:.0f},y:{p["halo"][1]:.0f},scale:{p["halo"][2]:.2f}}}')
    path("a", lambda p: f'{{x:{p["note"][0] - 30:.0f},y:{p["note"][1] - 70:.0f}}}')
    path("s", lambda p: f'{{x:{p["spark"][0]:.0f},y:{p["spark"][1]:.0f}}}')
    # entrance: stickers slap on, then the marker draws
    js.append(f'tl.fromTo("#{g}yi",{{scale:1.25,rotation:-10,opacity:0}},{{scale:1,rotation:-4,opacity:1,duration:.22,ease:"back.out(2.4)"}},{a + .0:.2f});')
    js.append(f'tl.fromTo("#{g}ni",{{scale:1.25,opacity:0,rotation:10}},{{scale:1,opacity:1,rotation:4,duration:.22,ease:"back.out(2.4)"}},{a + .12:.2f});')
    js.append(f'tl.fromTo("#{g}h path",{{strokeDasharray:1,strokeDashoffset:1}},{{strokeDashoffset:0,duration:.45,ease:"power1.inOut"}},{a + .25:.2f});')
    js.append(f'tl.fromTo("#{g}s path",{{strokeDasharray:1,strokeDashoffset:1}},{{strokeDashoffset:0,duration:.2,stagger:.1,ease:"power1.out"}},{a + .45:.2f});')
    js.append(f'tl.fromTo("#{g}a path",{{strokeDasharray:1,strokeDashoffset:1}},{{strokeDashoffset:0,duration:.3,ease:"power1.out"}},{a + .55:.2f});')
    js.append(f'tl.to("#{g}s svg",{{rotation:12,duration:.6,yoyo:true,repeat:{max(1, int(d / .6) - 1)},ease:"sine.inOut",transformOrigin:"0px 0px"}},{a + .8:.2f});')
# the timeline lives in the root's seconds: segment tweens are offset by their start
open("compositions/scrap.html", "w").write(f"""<template>
  <link rel="stylesheet" href="{FONTS}" />
  <style>{css}</style>
  <div id="scrap" data-composition-id="scrap" data-width="1080" data-height="1920" data-layout-allow-overflow data-layout-allow-overlap>
{chr(10).join(body)}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    const seg = [];
    {chr(10).join("    " + s for s in js)}
    window.__timelines["scrap"] = tl;
  </script>
</template>
""")
