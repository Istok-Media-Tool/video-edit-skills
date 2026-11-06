# Generates the seven era badges (one sub-composition each) and the root.
import math
B = [0.00, 4.96, 12.56, 21.24, 27.04, 39.56, 51.56, 64.48]
START = [2.72] + [b + 0.24 for b in B[1:7]]          # after the title / the TV static
END = [B[i + 1] - 0.28 for i in range(6)] + [64.40]  # before the next static
ERAS = ["60", "70", "80", "90", "00", "10", "20"]

def brow(tmax, peak, at, sharp=False, head=0.9, n=60):
    # filled eyebrow: centre line head (left) -> arch -> tail, thickness tapers to the tail
    pts_u, pts_l = [], []
    for i in range(n + 1):
        s = i / n; x = 20 + 260 * s
        if sharp:
            y = 62 - (62 - peak) * (s / at if s < at else (1 - s) / (1 - at) * 0.75 + 0.25 * 0 + (1 - (1 - s) / (1 - at)) * 0)
            y = 62 - (62 - peak) * (s / at) if s < at else peak + (66 - peak) * ((s - at) / (1 - at)) ** 1.2
        else:
            y = 62 - (62 - peak) * math.sin(min(1, s / at) * math.pi / 2) if s < at else peak + (64 - peak) * ((s - at) / (1 - at)) ** 1.6
        t = tmax * (head + (1 - head) * min(1, s / 0.15)) * (1 - 0.82 * max(0, (s - 0.35) / 0.65) ** 1.3)
        pts_u.append((x, y - t / 2)); pts_l.append((x, y + t / 2))
    pts = pts_u + pts_l[::-1]
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"

def hairs():
    out = []
    for i in range(46):
        s = i / 45; x = 22 + 255 * s
        y = 60 - 34 * math.sin(min(1, s / 0.66) * math.pi / 2) if s < 0.66 else 26 + 36 * ((s - 0.66) / 0.34) ** 1.5
        ang = -75 + 60 * s  # upward at the head, lying down at the tail
        L = 22 * (1 - 0.6 * s) + 4 * ((i * 7) % 3)
        dx = L * math.cos(math.radians(ang)); dy = L * math.sin(math.radians(ang))
        out.append(f'<line pathLength="1" x1="{x:.1f}" y1="{y+8:.1f}" x2="{x+dx:.1f}" y2="{y+8+dy:.1f}"/>')
    return "".join(out)

P = {
 "60": brow(16, 26, 0.66), "70": brow(10, 36, 0.6, head=0.7), "80": brow(30, 32, 0.62),
 "90": brow(5, 20, 0.55, head=1), "00": brow(3.2, 10, 0.62, sharp=True, head=1), "10": brow(24, 22, 0.68, sharp=True, head=0.6),
}
CSS = {
"60": """#b{right:50px;top:230px;width:400px;height:330px;background:#f1e8d3;border:6px solid #111;border-radius:150px 150px 24px 24px;overflow:hidden;color:#111;font-family:'Josefin Sans',sans-serif;text-align:center}
#op{position:absolute;left:50%;top:-210px;width:520px;height:520px;margin-left:-260px;border-radius:50%;background:repeating-radial-gradient(circle,#e2611f 0 22px,#f1e8d3 22px 44px,#111 44px 52px,#f1e8d3 52px 74px);opacity:.9}
#yr{position:absolute;left:0;right:0;top:70px;font-weight:700;font-size:128px;line-height:1;letter-spacing:-.02em;background:#f1e8d3;width:300px;margin:0 auto;border-radius:20px;padding-top:12px}
#ds{position:absolute;left:0;right:0;top:200px;font-weight:700;font-size:32px;letter-spacing:.3em;text-transform:uppercase;background:#f1e8d3;width:300px;margin:0 auto;padding:4px 0 0 .3em}
#br{position:absolute;left:100px;top:236px;width:200px;fill:#111}""",
"70": """#b{left:20px;top:120px;width:460px;height:330px;color:#fbefd5;font-family:'Shrikhand',cursive;text-align:center}
.st{position:absolute;left:50%;border-radius:50% 50% 0 0;border-bottom:0}
#s1{width:440px;height:220px;margin-left:-220px;top:20px;border:34px solid #e8762c;border-bottom:0}
#s2{width:372px;height:186px;margin-left:-186px;top:54px;border:34px solid #f2b134;border-bottom:0}
#s3{width:304px;height:152px;margin-left:-152px;top:88px;border:34px solid #8a4a22;border-bottom:0}
#yr{position:absolute;left:0;right:0;top:150px;font-size:120px;line-height:1;text-shadow:5px 5px 0 #7a3a16,9px 9px 0 rgba(0,0,0,.35)}
#ds{position:absolute;left:0;right:0;top:280px;font-family:'Josefin Sans',sans-serif;font-weight:700;font-size:34px;letter-spacing:.12em;text-shadow:0 2px 10px rgba(0,0,0,.6)}
#br{position:absolute;left:110px;top:112px;width:240px;fill:#5a2c10;filter:blur(1.2px)}""",
"80": """#b{right:44px;top:300px;width:440px;height:300px;font-family:'Audiowide',sans-serif;text-align:center;border-radius:18px;overflow:hidden}
#gr{position:absolute;left:-40px;right:-40px;bottom:-10px;height:150px;background:repeating-linear-gradient(90deg,rgba(255,60,200,.75) 0 2px,transparent 2px 44px),repeating-linear-gradient(0deg,rgba(255,60,200,.75) 0 2px,transparent 2px 30px);transform:perspective(220px) rotateX(55deg);transform-origin:bottom}
#yr{position:absolute;left:0;right:0;top:40px;font-size:122px;line-height:1;color:#fff0fb;text-shadow:0 0 6px #ff3fd0,0 0 18px #ff3fd0,0 0 42px #ff1fb5}
#ds{position:absolute;left:0;right:0;top:172px;font-size:34px;letter-spacing:.14em;color:#c8fbff;text-shadow:0 0 6px #22e6ff,0 0 18px #22e6ff}
#br{position:absolute;left:100px;top:218px;width:240px;fill:#6ff3ff;filter:drop-shadow(0 0 8px #22e6ff)}""",
"90": """#b{right:40px;top:300px;width:460px;height:380px;font-family:'VT323',monospace;color:#fff;text-shadow:3px 0 0 rgba(255,0,60,.55),-3px 0 0 rgba(0,200,255,.55),0 0 12px rgba(0,0,0,.6)}
#pl{position:absolute;right:0;top:0;font-size:64px;line-height:1}
#yr{position:absolute;right:0;top:0;font-size:170px;line-height:1}
#ds{position:absolute;right:0;top:150px;font-size:46px;letter-spacing:.06em}
#ts{position:absolute;right:0;top:252px;font-size:40px;opacity:.9}
#br{position:absolute;right:0;top:200px;width:230px;fill:#fff;filter:drop-shadow(3px 0 0 rgba(255,0,60,.6)) drop-shadow(-3px 0 0 rgba(0,200,255,.6))}""",
"00": """#b{left:20px;top:150px;width:460px;height:300px;font-family:'Fredoka',sans-serif;text-align:center}
#yr{position:absolute;left:0;right:0;top:20px;font-weight:700;font-size:136px;line-height:1;background:linear-gradient(180deg,#ffffff 0%,#d9e3f0 38%,#7d8ba3 52%,#f4f7ff 64%,#aab6cc 100%);-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-stroke:3px #ff5fb8;filter:drop-shadow(0 4px 10px rgba(255,80,180,.55))}
#sh{position:absolute;left:0;right:0;top:20px;font-weight:700;font-size:136px;line-height:1;color:transparent;background:linear-gradient(105deg,transparent 42%,rgba(255,255,255,.95) 50%,transparent 58%) no-repeat;background-size:300% 100%;-webkit-background-clip:text;background-clip:text}
#ds{position:absolute;left:50%;top:176px;transform:translateX(-50%);white-space:nowrap;font-weight:700;font-size:36px;color:#fff;background:linear-gradient(90deg,#ff6ec7,#a77bff);border-radius:40px;padding:6px 26px;box-shadow:0 0 0 3px #fff,0 6px 16px rgba(255,80,180,.5)}
.sp{position:absolute;color:#fff;font-size:44px;text-shadow:0 0 10px #ff8ad8}
#k1{left:6px;top:6px}#k2{right:4px;top:110px;font-size:30px}#k3{left:40px;top:150px;font-size:26px}
#br{position:absolute;left:110px;top:240px;width:240px;fill:#3a2a33;filter:drop-shadow(0 0 4px #fff)}""",
"10": """#b{right:40px;top:300px;width:440px;height:310px;background:#fff;border-radius:34px;box-shadow:0 14px 40px rgba(0,0,0,.35);font-family:'Inter',sans-serif;color:#111;overflow:hidden}
#av{position:absolute;left:26px;top:22px;width:62px;height:62px;border-radius:50%;background:conic-gradient(#feda75,#fa7e1e,#d62976,#962fbf,#4f5bd5,#feda75);padding:4px}
#av i{display:block;width:100%;height:100%;border-radius:50%;background:#f3d9c9;border:3px solid #fff}
#nm{position:absolute;left:104px;top:28px;font-weight:700;font-size:30px}
#sb{position:absolute;left:104px;top:62px;font-size:22px;color:#888}
#yr{position:absolute;left:26px;top:96px;font-family:'Pacifico',cursive;font-size:84px;line-height:1.25;background:linear-gradient(90deg,#962fbf,#d62976,#fa7e1e);-webkit-background-clip:text;background-clip:text;color:transparent}
#lk{position:absolute;left:26px;top:236px;font-weight:700;font-size:30px;display:flex;align-items:center;gap:12px}
#ht{color:#e0245e;font-size:40px;line-height:1}
#br{position:absolute;right:20px;top:120px;width:150px}""",
"20": """#b{right:40px;top:300px;width:440px;height:300px;border-radius:36px;background:rgba(245,236,224,.55);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border:1.5px solid rgba(255,255,255,.7);box-shadow:0 10px 40px rgba(60,40,20,.18);text-align:center;color:#3b2a20}
#yr{position:absolute;left:0;right:0;top:34px;font-family:'Playfair Display',serif;font-style:italic;font-weight:500;font-size:110px;line-height:1}
#ds{position:absolute;left:0;right:0;top:160px;font-family:'Inter',sans-serif;font-weight:500;font-size:28px;letter-spacing:.42em;text-transform:uppercase;padding-left:.42em}
#br{position:absolute;left:100px;top:196px;width:240px;stroke:#4a3326;stroke-width:2.6;stroke-linecap:round;fill:none}""",
}
def svg(e):
    if e == "20": return f'<svg id="br" viewBox="0 0 300 90">{hairs()}</svg>'
    if e == "10":
        return (f'<svg id="br" viewBox="0 0 300 90"><defs><linearGradient id="om" x1="0" x2="1"><stop offset="0" stop-color="#8a6a58"/>'
                f'<stop offset=".35" stop-color="#3a2418"/><stop offset="1" stop-color="#1e120c"/></linearGradient></defs><path fill="url(#om)" stroke="#3a2418" pathLength="1" d="{P[e]}"/></svg>')
    return f'<svg id="br" viewBox="0 0 300 90"><path pathLength="1" d="{P[e]}"/></svg>'
BODY = {
"60": '<div id="op"></div><div id="yr">60-e</div><div id="ds">blagi luk</div>',
"70": '<div class="st" id="s1"></div><div class="st" id="s2"></div><div class="st" id="s3"></div><div id="yr">70-e</div><div id="ds">hipi mekoća</div>',
"80": '<div id="gr"></div><div id="yr">80-e</div><div id="ds">jako i puno</div>',
"90": '<div id="yr">90-e</div><div id="ds">TANKE PINCETOM</div>',
"00": '<div class="sp" id="k1">✦</div><div class="sp" id="k2">✦</div><div class="sp" id="k3">✧</div><div id="yr">2000-e</div><div id="sh">2000-e</div><div id="ds">Y2K linija</div>',
"10": '<div id="av"><i></i></div><div id="nm">trend_2010</div><div id="sb">pune · popunjene</div><div id="yr">2010-e</div><div id="lk"><span id="ht">♥</span><span>12.480 sviđanja</span></div>',
"20": '<div id="yr"><span>2</span><span>0</span><span>2</span><span>0</span><span>-</span><span>e</span></div><div id="ds">laminacija</div>',
}
ANIM = {
"60": 'tl.fromTo("#b",{scale:.2,opacity:0},{scale:1,opacity:1,duration:.45,ease:"back.out(1.6)"},0);tl.fromTo("#op",{rotation:0},{rotation:90,duration:D,ease:"none"},0);',
"70": 'tl.fromTo(".st",{scale:0,opacity:0},{scale:1,opacity:1,duration:.5,stagger:.08,ease:"power3.out",transformOrigin:"50% 100%"},0);tl.fromTo("#yr",{y:40,opacity:0},{y:0,opacity:1,duration:.4,ease:"back.out(2)"},.25);tl.fromTo("#ds",{opacity:0},{opacity:1,duration:.3},.45);tl.to("#b",{rotation:2,duration:D/2,yoyo:true,repeat:1,ease:"sine.inOut"},.6);',
"80": 'tl.fromTo("#b",{opacity:0},{opacity:1,duration:.05},0);tl.fromTo("#yr",{opacity:0},{keyframes:[{opacity:1,duration:.05},{opacity:.15,duration:.05},{opacity:1,duration:.05},{opacity:.3,duration:.04},{opacity:1,duration:.1}]},0.05);tl.fromTo("#gr",{backgroundPosition:"0 0"},{backgroundPosition:"0 300px",duration:D,ease:"none"},0);tl.fromTo("#ds,#br",{opacity:0},{opacity:1,duration:.2},.3);',
"90": 'tl.fromTo("#yr",{opacity:0},{opacity:1,duration:.01},.16);tl.fromTo("#ds",{opacity:0},{opacity:1,duration:.01},.36);',
"00": 'tl.fromTo("#yr",{scale:0,rotation:-12},{scale:1,rotation:0,duration:.5,ease:"back.out(2.2)"},0);tl.fromTo("#ds",{y:30,opacity:0},{y:0,opacity:1,duration:.35,ease:"back.out(2)"},.25);tl.fromTo(".sp",{scale:0},{scale:1,duration:.3,stagger:.1,ease:"back.out(3)"},.3);tl.to(".sp",{scale:.4,opacity:.5,duration:.4,stagger:.13,yoyo:true,repeat:Math.max(1,Math.floor(D/.8)*2-1),ease:"sine.inOut"},.8);for(let t=.7;t<D-1.2;t+=3.2)tl.fromTo("#sh",{backgroundPosition:"100% 0"},{backgroundPosition:"0% 0",duration:.9,ease:"sine.inOut"},t);',
"10": 'tl.fromTo("#b",{scale:.9,opacity:0},{scale:1,opacity:1,duration:.6,ease:"back.out(1.7)"},0);tl.fromTo("#ht",{scale:0},{scale:1,duration:.35,ease:"back.out(3)"},.7);tl.to("#ht",{scale:1.25,duration:.18,yoyo:true,repeat:1},1.1);',
"20": 'tl.fromTo("#b",{opacity:0,y:24,filter:"blur(10px)"},{opacity:1,y:0,filter:"blur(0px)",duration:.7,ease:"power2.out"},0);tl.fromTo("#yr span",{opacity:0,y:8,filter:"blur(10px)"},{opacity:1,y:0,filter:"blur(0px)",duration:.36,stagger:.06,ease:"power3.out"},.2);',
}
T0 = {"60": .35, "70": .55, "80": .35, "90": .28, "00": .45, "10": .5, "20": .6}
DRAW = {e: (f'tl.fromTo("#era{e} #br line",{{strokeDasharray:1,strokeDashoffset:1}},{{strokeDashoffset:0,duration:.25,stagger:.02,ease:"power1.out"}},{T0[e]});' if e == "20" else
            f'tl.fromTo("#era{e} #br path",{{strokeDasharray:1,strokeDashoffset:1,fillOpacity:0,strokeWidth:2}},{{strokeDashoffset:0,duration:.6,ease:"sine.inOut"}},{T0[e]});tl.to("#era{e} #br path",{{fillOpacity:1,duration:.3}},{T0[e]}+.45);') for e in ERAS}
# film grain (grain-overlay recipe, stepped by the timeline instead of a CSS loop)
GRAIN = 'for(let i=0,t=0;t<D;i++,t+=.08)tl.set("#gn",{x:((i*37)%11-5)*14,y:((i*53)%13-6)*14},t);'
FONTS = "https://fonts.googleapis.com/css2?family=Josefin+Sans:wght@700&family=Shrikhand&family=Audiowide&family=VT323&family=Fredoka:wght@700&family=Pacifico&family=Playfair+Display:ital,wght@1,500&family=Inter:wght@500;700&display=swap"
def _write():
    import re
    def scope(css, e):
        return re.sub(r'([^{}]+)\{', lambda m: ','.join(f'#era{e} ' + x.strip() for x in m.group(1).split(',')) + '{', css)
    GN = '<div id="gw" class="clip" data-start="0" data-duration="{d}" style="inset:0;overflow:hidden;opacity:.16;mix-blend-mode:overlay"><div id="gn" style="position:absolute;left:-10%;top:-10%;width:120%;height:120%;background:url(&quot;data:image/svg+xml,%3Csvg viewBox=%270 0 256 256%27 xmlns=%27http://www.w3.org/2000/svg%27%3E%3Cfilter id=%27n%27%3E%3CfeTurbulence type=%27fractalNoise%27 baseFrequency=%270.65%27 numOctaves=%273%27 stitchTiles=%27stitch%27/%3E%3C/filter%3E%3Crect width=%27100%25%27 height=%27100%25%27 filter=%27url(%23n)%27/%3E%3C/svg%3E&quot;)"></div></div>'
    hosts = ['<div id="hleak" data-composition-id="organic-light-leak-overlay" data-composition-src="compositions/organic-light-leak-overlay.html" data-track-kind="graphics" data-start="5.20" data-duration="1.8" data-track-index="3" data-width="1080" data-height="1920"></div>',
             '<div id="hneon" data-composition-id="lt-neon-border" data-composition-src="compositions/lt-neon-border.html" data-track-kind="graphics" data-start="12.80" data-duration="8.16" data-track-index="4" data-width="1080" data-height="1920"></div>',
             '<div id="hhud" data-composition-id="camcorder-hud" data-composition-src="compositions/camcorder-hud.html" data-track-kind="graphics" data-start="21.48" data-duration="5.28" data-track-index="5" data-width="1080" data-height="1920"></div>']
    for i, e in enumerate(ERAS):
        d = round(END[i] - START[i], 2)
        open(f"compositions/era{e}.html", "w").write(f"""<template>
      <link rel="stylesheet" href="{FONTS}" />
      <style>
        #era{e} {{ position:absolute; inset:0; }}
        #era{e} .clip {{ position:absolute; }}
        {scope(CSS[e], e)}
      </style>
      <div id="era{e}" data-composition-id="era{e}" data-width="1080" data-height="1920" data-layout-allow-overflow>
        {GN if e in ("60", "70") else ""}<div id="b" class="clip" data-start="0" data-duration="{d}">{BODY[e]}{svg(e)}</div>
      </div>
      <script>
        const D = {d}; const tl = gsap.timeline({{ paused: true }});
        {ANIM[e].replace('"#', f'"#era{e} #').replace('".', f'"#era{e} .').replace(',#', f',#era{e} #')}
        {DRAW[e]}
        {GRAIN if e in ("60", "70") else ""}
        tl.to("#era{e} #b", {{ opacity: 0, duration: .2 }}, D - .2);
        window.__timelines["era{e}"] = tl;
      </script>
    </template>
    """)
        hosts.append(f'<div id="h{e}" data-composition-id="era{e}" data-composition-src="compositions/era{e}.html" data-track-kind="graphics" data-start="{START[i]:.2f}" data-duration="{d}" data-track-index="{1 + i % 2}" data-width="1080" data-height="1920"></div>')
    open("index.html", "w").write(f"""<!doctype html>
    <html lang="sr">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=1080, height=1920" />
        <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
        <link rel="stylesheet" href="{FONTS}" />
        <style>
          * {{ margin: 0; padding: 0; box-sizing: border-box; }}
          html, body {{ margin: 0; width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
          #root {{ position: relative; width: 1080px; height: 1920px; }}
          #bg {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }}
        </style>
      </head>
      <body>
        <div id="root" data-composition-id="main" data-start="0" data-duration="64.48" data-width="1080" data-height="1920">
          <video id="bg" class="clip" src="assets/bg.mp4" muted playsinline data-start="0" data-duration="64.48" data-track-index="0"></video>
          {chr(10).join('      ' + h for h in hosts).strip()}
        </div>
        <script>window.__timelines["main"] = gsap.timeline({{ paused: true }});</script>
      </body>
    </html>
    """)
    if __name__ == "__main__": print(list(zip(ERAS, START, END)))
if __name__ == '__main__': _write()
