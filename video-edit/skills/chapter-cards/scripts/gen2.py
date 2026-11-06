# One card template for all seven eras: same slot, same rows, same timing.
# Only the font, palette and one texture inside the card say which era it is.
# Rows: year / what the brows were like / the brow drawn / the decade ruler.
import math, re
from gen import brow, hairs, P   # brow shapes from the first draft
B = [0.00, 4.96, 12.56, 21.24, 27.04, 39.56, 51.56, 64.48]
START = [2.64] + [b + 0.24 for b in B[1:7]]
END = [B[i + 1] - 0.28 for i in range(6)] + [64.48]
ERAS = ["60", "70", "80", "90", "00", "10", "20"]
LAB = ["60", "70", "80", "90", "00", "10", "20"]
X, Y, W, H = 40, 136, 440, 320          # scaled .9 -> bottom at 424, above the tablet in the zoomed shots
SC = 0.9          # the slot: top-left, free in every shot
T = {  # font, year size, card, year colour/effect, text colour, accent, extra card markup, extra css
 "60": dict(f="'Josefin Sans'", ys=124, card="background:#f1e8d3;border:5px solid #111", yr="color:#111", tx="#111", ac="#e2611f",
            deco='<div class="dc"></div>', css="#dc0{}.dc{position:absolute;right:-140px;top:-140px;width:250px;height:250px;border-radius:50%;background:repeating-radial-gradient(circle,#e2611f 0 16px,#f1e8d3 16px 30px,#111 30px 36px,#f1e8d3 36px 50px)}"),
 "70": dict(f="'Shrikhand'", ys=112, card="background:#6b3416", yr="color:#fbefd5;text-shadow:4px 4px 0 #2e1206", tx="#fbefd5", ac="#f2b134",
            deco='<div class="dc"></div>', css=".dc{position:absolute;left:0;right:0;top:0;height:22px;background:linear-gradient(180deg,#e8762c 0 33%,#f2b134 33% 66%,#fbefd5 66%)}"),
 "80": dict(f="'Audiowide'", ys=112, card="background:transparent", yr="color:#fff0fb;text-shadow:0 0 6px #ff3fd0,0 0 18px #ff3fd0,0 0 40px #ff1fb5", tx="#c8fbff", ac="#22e6ff",
            deco='<div class="dc"></div>', css=".dc{position:absolute;left:-40px;right:-40px;bottom:46px;height:60px;opacity:.35;background:repeating-linear-gradient(90deg,rgba(255,60,200,.8) 0 2px,transparent 2px 44px),repeating-linear-gradient(0deg,rgba(255,60,200,.8) 0 2px,transparent 2px 26px);transform:perspective(220px) rotateX(55deg);transform-origin:bottom}"),
 "90": dict(f="'VT323'", ys=150, card="background:rgba(10,14,60,.62);border:2px solid rgba(255,255,255,.5)", yr="color:#fff;text-shadow:3px 0 0 rgba(255,0,60,.6),-3px 0 0 rgba(0,200,255,.6)", tx="#fff", ac="#ffffff",
            deco='<div class="dc">▶ PLAY</div>', css=".dc{position:absolute;right:18px;top:10px;font-size:34px;color:#fff}"),
 "00": dict(f="'Fredoka'", ys=118, card="background:linear-gradient(160deg,#ffe0f3,#d9e2ff);border:3px solid #fff;box-shadow:0 0 0 3px #ff8ad8", yr="background:linear-gradient(180deg,#fff 0%,#c9d3e6 40%,#6e7b96 52%,#eef2ff 66%,#9aa6bf 100%);-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-stroke:2.5px #ff4fae", tx="#d02f8c", ac="#ff4fae",
            deco='<div class="dc">✦</div><div class="dc d2">✧</div>', css=".dc{position:absolute;right:20px;top:10px;font-size:40px;color:#fff;text-shadow:0 0 10px #ff8ad8}.d2{right:auto;left:18px;top:auto;bottom:60px;font-size:26px}"),
 "10": dict(f="'Pacifico'", ys=96, card="background:#fff;box-shadow:0 14px 40px rgba(0,0,0,.3)", yr="background:linear-gradient(90deg,#962fbf,#d62976,#fa7e1e);-webkit-background-clip:text;background-clip:text;color:transparent", tx="#222", ac="#e0245e",
            deco='<div class="dc">♥</div>', css=".dc{position:absolute;right:22px;top:16px;font-size:46px;color:#e0245e;font-family:Inter}"),
 "20": dict(f="'Playfair Display'", ys=104, card="background:rgba(245,236,224,.6);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border:1.5px solid rgba(255,255,255,.75)", yr="color:#3b2a20;font-style:italic;font-weight:500", tx="#3b2a20", ac="#3b2a20",
            deco='', css=""),
}
DS = {"60": "blagi luk", "70": "hipi mekoća", "80": "jako i puno", "90": "tanke pincetom", "00": "Y2K linija", "10": "pune obrve", "20": "laminacija"}
YEAR = {"60": "60-e", "70": "70-e", "80": "80-e", "90": "90-e", "00": "2000-e", "10": "2010-e", "20": "2020-e"}
BROW = {"60": "#111", "70": "#f2b134", "80": "#6ff3ff", "90": "#fff", "00": "#3a2a33", "10": "url(#om)", "20": "#4a3326"}
FONTS = "https://fonts.googleapis.com/css2?family=Josefin+Sans:wght@700&family=Shrikhand&family=Audiowide&family=VT323&family=Fredoka:wght@700&family=Pacifico&family=Playfair+Display:ital,wght@1,500&family=Inter:wght@500;700&display=swap"
STEP = 380 / 7
def scope(css, e):
    return re.sub(r'([^{}]+)\{', lambda m: ','.join(f'#era{e} ' + x.strip() for x in m.group(1).split(',')) + '{', css)
def svg(e):
    if e == "20":
        return f'<svg class="br" viewBox="0 0 300 90" style="filter:drop-shadow(0 0 8px #22e6ff);stroke:{BROW[e]};stroke-width:2.6;stroke-linecap:round;fill:none">{hairs()}</svg>'
        return f'<svg class="br" viewBox="0 0 300 90" style="stroke:{BROW[e]};stroke-width:2.6;stroke-linecap:round;fill:none">{hairs()}</svg>'
    e2 = e; e = "80" if e != "20" else e
    om = ('<defs><linearGradient id="om" x1="0" x2="1"><stop offset="0" stop-color="#8a6a58"/><stop offset=".35" stop-color="#3a2418"/>'
          '<stop offset="1" stop-color="#1e120c"/></linearGradient></defs>') if e == "10" else ""
    glow = "filter:drop-shadow(0 0 8px #22e6ff);" if e == "80" else ""
    stroke = "#3a2418" if e == "10" else BROW[e]
    return f'<svg class="br" viewBox="0 0 300 90" style="{glow}">{om}<path pathLength="1" fill="{BROW[e]}" stroke="{stroke}" d="{P[e2]}"/></svg>'
hosts = []
NEON = open("compositions/lt-neon-border.html").read()
STYLE = "80"   # the user's house look for chapter cards
for e in ERAS:
    T[e] = T[STYLE]; BROW[e] = BROW[STYLE]
for i, e in enumerate(ERAS):
    t = dict(T[e]); d = round(END[i] - START[i], 2)
    if len(YEAR[e]) > 4: t["ys"] = 80          # 2000-e .. 2020-e fit the same card
    ruler = "".join(f'<span style="left:{30 + STEP * k:.1f}px">{l}</span>' for k, l in enumerate(LAB))
    css = f"""#sc{{position:absolute;left:{X}px;top:{Y}px;width:{W}px;height:{H}px;transform:scale({SC});transform-origin:0 0}}
#b{{left:0;top:0;width:{W}px;height:{H}px;border-radius:26px;overflow:hidden;{t['card']};font-family:{t['f']};color:{t['tx']}}}
.yr{{position:absolute;left:0;right:0;top:26px;text-align:center;font-weight:700;font-size:{t['ys']}px;line-height:1.1;{t['yr']}}}
.sh{{position:absolute;left:0;right:0;top:26px;text-align:center;font-weight:700;font-size:{t['ys']}px;line-height:1.1;color:transparent;background:linear-gradient(105deg,transparent 42%,rgba(255,255,255,.95) 50%,transparent 58%) no-repeat;background-size:300% 100%;-webkit-background-clip:text;background-clip:text}}
.ds{{position:absolute;left:0;right:0;top:160px;text-align:center;font-family:'Inter';font-weight:700;font-size:28px;letter-spacing:.16em;text-transform:uppercase;color:{t['tx']}}}
.br{{position:absolute;left:120px;top:196px;width:200px;overflow:visible}}
.ru{{position:absolute;left:0;right:0;top:268px;height:40px;font-family:'Inter';font-weight:700;font-size:26px;color:{t['tx']}}}
.ru span{{position:absolute;top:8px;width:{STEP:.1f}px;text-align:center;opacity:.38}}
.ru .ln{{position:absolute;left:30px;right:30px;top:2px;height:2px;background:{t['tx']};opacity:.25}}
.mk{{position:absolute;top:-3px;left:{30 + STEP * max(i - 1, 0) + STEP / 2 - 6:.1f}px;width:12px;height:12px;border-radius:50%;background:{t['ac']}}}
{t['css']}"""
    sel = f'"#era{e} '
    anim = [f'tl.fromTo({sel}#b",{{opacity:0,y:-24}},{{opacity:1,y:0,duration:.4,ease:"power3.out"}},0);',
            f'tl.fromTo({sel}.yr",{{opacity:0,y:20}},{{opacity:1,y:0,duration:.4,ease:"back.out(1.8)"}},.12);',
            f'tl.fromTo({sel}.ds",{{opacity:0}},{{opacity:1,duration:.3}},.3);',
            f'tl.fromTo({sel}.br {"line" if e == "20" else "path"}",{{strokeDasharray:1,strokeDashoffset:1,fillOpacity:0}},{{strokeDashoffset:0,duration:.6,stagger:{.012 if e == "20" else 0},ease:"sine.inOut"}},.45);',
            '' if e == "20" else f'tl.to({sel}.br path",{{fillOpacity:1,duration:.3}},.95);',
            # the ruler: the marker steps from the previous decade to this one
            f'tl.fromTo({sel}.mk",{{x:0}},{{x:{STEP if i else 0:.1f},duration:.5,ease:"power2.inOut"}},.55);',
            f'tl.to({sel}.ru span:nth-child({i + 2})",{{opacity:1,duration:.2}},.9);']
    if e == "00":
        anim.append(f'for(let t=1.2;t<D-1.2;t+=3.2)tl.fromTo({sel}.sh",{{backgroundPosition:"100% 0"}},{{backgroundPosition:"0% 0",duration:.9,ease:"sine.inOut",immediateRender:false}},t);')
    if e == "10":
        anim.append(f'tl.fromTo({sel}.dc",{{scale:0}},{{scale:1,duration:.6,ease:"back.out(1.7)"}},1.0);')
    if e == "90":
        anim.append(f'for(let t=1;t<D-.5;t+=1)tl.to({sel}.dc",{{opacity:.2,duration:.01}},t).to({sel}.dc",{{opacity:1,duration:.01}},t+.5);')
    anim.append(f'tl.to({sel}#b",{{opacity:0,duration:.2}},D-.2);')
    sh = f'<div class="sh">{YEAR[e]}</div>' if e == "00" else ""
    open(f"compositions/era{e}.html", "w").write(f"""<template>
  <link rel="stylesheet" href="{FONTS}" />
  <style>
    #era{e} {{ position:absolute; inset:0; }}
    #era{e} .clip {{ position:absolute; }}
    {scope(css, e)}
  </style>
  <div id="era{e}" data-composition-id="era{e}" data-width="1080" data-height="1920" data-layout-allow-overflow>
    <div id="sc"><div id="b" class="clip" data-start="0" data-duration="{d}">{t['deco']}<div class="yr">{YEAR[e]}</div>{sh}<div class="ds">{DS[e]}</div>{svg(e)}<div class="ru"><div class="ln"></div>{ruler}<div class="mk"></div></div></div></div>
  </div>
  <script>
    const D = {d}; const tl = gsap.timeline({{ paused: true }});
    {chr(10).join('    ' + a for a in anim).strip()}
    window.__timelines["era{e}"] = tl;
  </script>
</template>
""")
    nb = NEON.replace('"lt-neon-border"', f'"neon{e}"').replace("var DUR = 8.16;", f"var DUR = {d};").replace('data-duration="8.16"', f'data-duration="{d}"')
    open(f"compositions/neon{e}.html", "w").write(nb)
    hosts.append(f'<div id="hn{e}" data-composition-id="neon{e}" data-composition-src="compositions/neon{e}.html" data-track-kind="graphics" data-start="{START[i]:.2f}" data-duration="{d}" data-track-index="{3 + i % 2}" data-width="1080" data-height="1920"></div>')
    hosts.append(f'<div id="h{e}" data-composition-id="era{e}" data-composition-src="compositions/era{e}.html" data-track-kind="graphics" data-start="{START[i]:.2f}" data-duration="{d}" data-track-index="{1 + i % 2}" data-width="1080" data-height="1920"></div>')
idx = open("index.html").read()
idx = re.sub(r'(<video id="bg"[^\n]*\n).*?(\n    </div>\n    <script>)', lambda m: m.group(1) + "\n".join("      " + h for h in hosts) + m.group(2), idx, flags=re.S)
open("index.html", "w").write(idx)
