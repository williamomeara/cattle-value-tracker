#!/usr/bin/env python3
# Minimal QR-tape SENDER. Needs only `segno` (pip install segno). No tkinter/ffmpeg.
# Usage:  python3 qrsend.py <dir>      -> writes qrtape.html
# Open qrtape.html in a browser, make it fullscreen, film the screen with a phone,
# AirDrop the video to the Mac and run:  qrtape.py receive VIDEO -o out/
import sys, os, io, tarfile, hashlib, struct, zlib
import segno

BS = 700       # bytes per QR; lower it (e.g. 400) if the phone can't read them
FPS = 8        # QR codes shown per second
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
html = """<!doctype html><meta charset=utf-8><title>qrtape</title>
<style>html,body{margin:0;height:100%%;background:#fff;font:bold 3vh sans-serif}
#w{height:100%%;display:flex;flex-direction:column;align-items:center;justify-content:center}
img{width:min(90vw,82vh);height:auto;image-rendering:pixelated}
#c{margin-top:1vh;color:#333}#d{color:#0a0}</style>
<div id=w><img id=q><div id=c></div></div>
<script>var F=%s,R=%d,i=0,loops=0,q=document.getElementById('q'),c=document.getElementById('c');
function t(){q.src=F[i];i++;if(i>=F.length){i=0;loops++;}
c.textContent=(i||F.length)+' / '+F.length+'  \\u00b7  loop '+(loops+1);
if(loops>=2){c.innerHTML="<span id=d>\\u2713 filmed 2 full loops \\u2014 you can stop</span>";}
}t();setInterval(t,R);</script>
""" % (__import__("json").dumps(frames), int(1000 / FPS))
open(OUT, "w").write(html)
print("packed %d code/text files -> %s (%d QR codes); open it in a browser,\n"
      "go fullscreen (F11 or the green button) and film ~2 full loops" % (n, OUT, K))
