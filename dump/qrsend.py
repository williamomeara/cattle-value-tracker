#!/usr/bin/env python3
# Minimal QR-tape SENDER. Hand-typeable. Needs only `segno` (pip install segno).
# Usage:  python3 qrsend.py <dir>       then film the screen with a phone,
# AirDrop the video to the Mac and run:  qrtape.py receive VIDEO -o out/
import sys, os, io, tarfile, hashlib, struct, zlib, tkinter as tk
import segno

BS = 700       # bytes per QR; lower it (e.g. 400) if the phone can't read them
FPS = 8        # QR codes shown per second
MAXKB = 1024   # skip files bigger than this (data dumps)
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
print("packed %d code/text files (images, binaries, %s skipped)" % (n, SKIP))
data = buf.getvalue()
payload = hashlib.sha256(data).digest() + data        # same format the decoder expects
plen = len(payload)
K = -(-plen // BS)
payload = payload.ljust(K * BS, b"\0")
session = int.from_bytes(payload[:4], "big")
H = struct.Struct(">2sBIIIHI")
print("%s -> %d bytes, %d QR codes; film ~2 full loops" % (path, plen, K))

def symbol(seq):
    body = H.pack(b"QT", 1, session, K, plen, BS, seq) + payload[seq*BS:(seq+1)*BS]
    return body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)

root = tk.Tk()
root.attributes("-fullscreen", True)
root.configure(bg="white")
lbl = tk.Label(root, bg="white")
lbl.pack(expand=True)
root.bind("<Escape>", lambda e: root.destroy())
state = {"seq": 0}

def tick():
    png = io.BytesIO()
    segno.make_qr(symbol(state["seq"]), error="m", boost_error=False).save(
        png, kind="png", scale=10, border=4, dark="black", light="white")
    lbl.img = tk.PhotoImage(data=png.getvalue())   # keep a ref so it isn't GC'd
    lbl.configure(image=lbl.img)
    state["seq"] = (state["seq"] + 1) % K
    root.after(int(1000 / FPS), tick)

tick()
root.mainloop()
