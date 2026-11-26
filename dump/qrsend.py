#!/usr/bin/env python3
# Minimal QR-tape SENDER. Needs only `segno` (pip install segno). No tkinter/ffmpeg.
# Usage:  python3 qrsend.py <dir>      -> writes qrtape.html
# Open qrtape.html in a browser, make it fullscreen, film the screen with a phone,
# AirDrop the video to the Mac and run:  qrtape.py receive VIDEO -o out/
import sys, os, io, tarfile, hashlib, struct, zlib
import segno

BS = 700       # bytes per QR; lower it (e.g. 400) if the phone can't read them
FPS = 8        # flashes shown per second
COLS = 1       # QR codes per flash across (try 2); ROWS down. 1x1 = one at a time
ROWS = 1       # only raise these if the phone films in high resolution
MAXKB = 1024   # skip files bigger than this (data dumps)
OUT = "qrtape.html"
SKIP = {".git", "node_modules", ".venv", "venv", "env", "virtualenv", "site-packages",
        "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".eggs",
        "build", "dist", "target", ".dart_tool", ".pub-cache", "Pods", "Carthage",
        ".build", ".swiftpm", "DerivedData", ".gradle", ".idea", ".vs", "vendor",
        ".next", ".nuxt", ".svelte-kit", ".angular", ".vite", ".parcel-cache",
        ".turbo", ".cache", "coverage", ".expo", ".terraform", ".serverless"}

def istext(p):               # code/text has no null bytes; images/exes/zips do
    with open(p, "rb") as f:
        return b"\0" not in f.read(8192)

path = sys.argv[1]
base = os.path.basename(os.path.abspath(path))
buf = io.BytesIO()
n = 0
with tarfile.open(fileobj=buf, mode="w:xz", preset=9) as t:
    if os.path.isfile(path):                      # single file: pack it directly
        t.add(path, arcname=os.path.basename(path), recursive=False)
        n = 1
    else:
        for dp, dns, fns in os.walk(path):
            dns[:] = [d for d in dns if d not in SKIP and not d.endswith(".egg-info")]
            for f in sorted(fns):
                p = os.path.join(dp, f)
                if os.path.islink(p) or (os.path.isfile(p)
                        and os.path.getsize(p) <= MAXKB * 1024 and istext(p)):
                    t.add(p, arcname=os.path.join(base, os.path.relpath(p, path)),
                          recursive=False)
                    n += 1
data = buf.getvalue()
payload = hashlib.sha256(data).digest() + data        # same format the decoder expects
plen = len(payload)
K = -(-plen // BS)
payload = payload.ljust(K * BS, b"\0")
session = int.from_bytes(payload[:4], "big")
H = struct.Struct(">2sBIIIHI")

def symbol(seq):
    body = H.pack(b"QT", 1, session, K, plen, BS, seq) + payload[seq*BS:(seq+1)*BS]
    return body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)

frames = [segno.make_qr(symbol(i), error="m", boost_error=False).png_data_uri(scale=8, border=4)
          for i in range(K)]
PER = COLS * ROWS
FLASHES = -(-K // PER)
html = """<!doctype html><meta charset=utf-8><title>qrtape</title>
<style>html,body{margin:0;height:100%%;background:#fff;font:bold 3vh sans-serif}
#w{height:100%%;display:flex;flex-direction:column;align-items:center;justify-content:center}
#g{display:grid;grid-template-columns:repeat(%d,1fr);gap:1.5vmin;
width:min(94vw,86vh);height:min(94vw,86vh)}
#g img{width:100%%;height:100%%;object-fit:contain;image-rendering:pixelated}
#c{margin-top:1vh;color:#333}#d{color:#0a0}</style>
<div id=w><div id=g></div><div id=c></div></div>
<script>var F=%s,PER=%d,FL=%d,R=%d,f=0,loops=0,
g=document.getElementById('g'),c=document.getElementById('c');
for(var j=0;j<PER;j++)g.appendChild(document.createElement('img'));
var cells=g.children;
var B='data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACwAAAAAAQABAAACAkQBADs=';
function t(){for(var j=0;j<PER;j++){var k=f*PER+j;cells[j].src=k<F.length?F[k]:B;}
f++;if(f>=FL){f=0;loops++;}
c.textContent=Math.min(f*PER,F.length)+' / '+F.length+'  \\u00b7  loop '+(loops+1);
if(loops>=2)c.innerHTML="<span id=d>\\u2713 filmed 2 full loops \\u2014 you can stop</span>";
}t();setInterval(t,R);</script>
""" % (COLS, __import__("json").dumps(frames), PER, FLASHES, int(1000 / FPS))
open(OUT, "w").write(html)
print("packed %d code/text files -> %s (%d QR codes); open it in a browser,\n"
      "go fullscreen (F11 or the green button) and film ~2 full loops\n"
      "(%dx%d = %d codes per flash, %d flashes)" % (n, OUT, K, COLS, ROWS, PER, FLASHES))
