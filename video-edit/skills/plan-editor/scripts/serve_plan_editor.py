#!/usr/bin/env python3
"""
Serve the plan editor as a local page for the browser pane, with playback.

The inline chat widget (show_widget) can't carry the video's sound - it would
have to be written out inside the widget - so when the user wants to listen
while planning, the same tool runs here instead: a local page with the cut
render playing from each sentence / word.

"Pošalji plan" can't reach the chat from this page, so it POSTs the plan
message (same text the widget would send: PLAN_JSON, SENTENCES_JSON, ...)
to this server, which writes it to --reply. The page tells the user to
write "poslao sam" in the chat; then read that file.

Inputs:
  widget        output of make_plan_widget.py ... --media cut.mp4 --words words.json
  --media       the same media file (served at media/<name>, with Range support
                so the player can seek)
  --takes-dir   folder of take clips from make_take_clips.py (served at takes/<name>)
  --closeups-dir  folder of close-up previews from make_closeup_clips.py (served at closeups/<name>)
  --reply       where to write the sent plan (default: plan_reply.txt next to widget)
  --port        default 8765

Start it through the browser pane (preview_start with a .claude/launch.json
entry: runtimeExecutable python3, runtimeArgs [this script, ...], port), not
in a plain shell, so the user sees the page.
"""
import argparse
import os
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SHELL = """<!doctype html><html lang="sr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Plan editor</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.19.0/dist/tabler-icons.min.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@700&display=swap">
<style>
:root{--text-primary:#1f1e1d;--text-secondary:#5f5e5a;--text-muted:#888780;--text-danger:#a32d2d;--text-success:#3b6d11;--text-accent:#0c447c;
--bg-accent:#e6f1fb;--border:rgba(0,0,0,.12);--border-strong:rgba(0,0,0,.25);--border-accent:#378add;--border-success:#639922;--border-warning:#ba7517;
--surface-0:#faf9f5;--surface-1:#f1efe8;--surface-2:#fff;--radius:8px;--font-sans:system-ui,-apple-system,sans-serif}
@media (prefers-color-scheme:dark){:root{--text-primary:#f1efe8;--text-secondary:#b4b2a9;--text-muted:#888780;--text-danger:#f09595;--text-success:#97c459;
--text-accent:#b5d4f4;--bg-accent:#0c447c;--border:rgba(255,255,255,.14);--border-strong:rgba(255,255,255,.3);--border-accent:#85b7eb;
--border-success:#97c459;--border-warning:#ef9f27;--surface-0:#1f1e1d;--surface-1:#2c2c2a;--surface-2:#262624}}
body{margin:0 auto;max-width:760px;padding:16px;background:var(--surface-0);color:var(--text-primary);font-family:var(--font-sans);font-size:15px}
.sr-only{position:absolute;left:-9999px}
button,select,input[type=text]{font:inherit;font-size:13px;color:var(--text-primary);background:var(--surface-2);border:0.5px solid var(--border-strong);border-radius:var(--radius);padding:4px 10px;cursor:pointer}
button:hover{background:var(--surface-1)} select:disabled{opacity:.55;cursor:default} input[type=text]{cursor:text}
#sent{font-size:14px;color:var(--text-success);margin-top:10px}
</style>
<script>
function sendPrompt(t){fetch("/plan",{method:"POST",headers:{"Content-Type":"text/plain; charset=utf-8"},body:t})
 .then(r=>{if(!r.ok)throw 0;document.getElementById("sent").textContent="Plan je poslat. Napiši u četu „poslao sam“."})
 .catch(()=>{document.getElementById("sent").textContent="";document.getElementById("senderr").textContent="Slanje nije uspelo. Javi mi u četu."})}
// a stale "poslat" note must not make a later, unsent change look sent
document.addEventListener("click",e=>{if(!e.target.closest("#send"))document.getElementById("sent").textContent=""},true);
document.addEventListener("input",()=>{document.getElementById("sent").textContent=""},true);
</script></head><body>
__WIDGET__
<div id="sent"></div>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("widget")
    ap.add_argument("--media", required=True)
    ap.add_argument("--takes-dir")
    ap.add_argument("--closeups-dir")
    ap.add_argument("--reply")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    page = SHELL.replace("__WIDGET__", Path(a.widget).read_text(encoding="utf-8")).encode("utf-8")
    media = Path(a.media).resolve()
    takes_dir = Path(a.takes_dir).resolve() if a.takes_dir else None
    cu_dir = Path(a.closeups_dir).resolve() if a.closeups_dir else None
    reply = Path(a.reply or Path(a.widget).resolve().parent / "plan_reply.txt")

    class H(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                return self._send(200, "text/html; charset=utf-8", page)
            if self.path == "/media/" + media.name:
                return self._media(media)
            if takes_dir and self.path.startswith("/takes/"):
                f = takes_dir / Path(self.path[len("/takes/"):]).name
                if f.is_file():
                    return self._media(f)
            if cu_dir and self.path.startswith("/closeups/"):
                f = cu_dir / Path(self.path[len("/closeups/"):]).name
                if f.is_file():
                    return self._media(f)
            self.send_error(404)

        def do_POST(self):
            if self.path != "/plan":
                return self.send_error(404)
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            reply.write_bytes(body)
            print(f"plan saved -> {reply}", flush=True)
            self._send(200, "text/plain", b"ok")

        def _send(self, code, ctype, data):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _media(self, media):
            # Range requests, or the player can't seek to a sentence
            size = media.stat().st_size
            ctype = self.guess_type(str(media))
            m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
            start, end = 0, size - 1
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    if m.group(2):
                        end = min(int(m.group(2)), size - 1)
                elif m.group(2):
                    start = max(0, size - int(m.group(2)))
            self.send_response(206 if m else 200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if m:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            with open(media, "rb") as f:
                f.seek(start)
                left = end - start + 1
                try:
                    while left > 0:
                        chunk = f.read(min(1 << 16, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        left -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def log_message(self, *args):
            pass

    print(f"plan editor on http://localhost:{a.port}  (reply -> {reply})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
