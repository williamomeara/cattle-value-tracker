#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["segno", "zxing-cpp", "numpy"]
# ///
"""qrtape: move a directory across an air gap as a video of QR codes.

  send DIR -o tape.mp4      pack DIR into a fountain-coded QR video
  receive VIDEO... -o OUT   decode one or more phone recordings, rebuild DIR
  calibrate -o cal.mp4      density sweep clip; film it, then `calibrate-read`

The stream is a fountain code (LT): any ~K*(1.05..1.2) distinct symbols
rebuild the data, so dropped/blurred frames and starting mid-loop don't matter.
"""
import argparse, codecs, hashlib, io, json, math, os, struct, subprocess, sys, tarfile, zlib
from bisect import bisect_left

import numpy as np
import segno
import zxingcpp

MAGIC, VERSION = b"QT", 1
HDR = struct.Struct(">2sBIIIHI")  # magic ver session K payload_len block_size seq
CRC = struct.Struct(">I")
OVERHEAD = HDR.size + CRC.size
M64 = (1 << 64) - 1
DENSE_MAX_K = 2500


# ---------------------------------------------------------------- fountain code
def _splitmix(seed):
    x = seed & M64
    while True:
        x = (x + 0x9E3779B97F4A7C15) & M64
        z = x
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
        yield z ^ (z >> 31)


def _soliton_cdf(k, c=0.1, delta=0.05):
    if k <= 2:
        return [1.0] * k
    rho = [0.0, 1 / k] + [1 / (d * (d - 1)) for d in range(2, k + 1)]
    r = c * math.log(k / delta) * math.sqrt(k)
    spike = max(1, min(k, int(round(k / r))))
    tau = [0.0] * (k + 1)
    for d in range(1, spike):
        tau[d] = r / (d * k)
    tau[spike] = r * math.log(r / delta) / k
    w = [rho[d] + tau[d] for d in range(k + 1)]
    total, acc, cdf = sum(w), 0.0, []
    for d in range(1, k + 1):
        acc += w[d]
        cdf.append(acc / total)
    return cdf


def neighbours(seq, k, session, cdf):
    """Block indices XORed into symbol `seq`. First k symbols are systematic."""
    if seq < k:
        return [seq]
    rng = _splitmix((session << 32) ^ seq)
    d = bisect_left(cdf, next(rng) / 2**64) + 1
    if k <= DENSE_MAX_K:  # dense enough that elimination always has full coverage
        d = max(d, min(int(3 * math.log2(k)), k // 2))
    d = min(k, d)
    picked = set()
    while len(picked) < d:
        picked.add(next(rng) % k)
    return sorted(picked)


class Encoder:
    def __init__(self, payload, block_size):
        self.payload, self.bs = payload, block_size
        self.session = int.from_bytes(payload[:4], "big")  # payload starts with sha256
        self.k = max(1, -(-len(payload) // block_size))
        padded = payload.ljust(self.k * block_size, b"\0")
        self.blocks = np.frombuffer(padded, np.uint8).reshape(self.k, block_size)
        self.cdf = _soliton_cdf(self.k)

    def symbol(self, seq):
        idx = neighbours(seq, self.k, self.session, self.cdf)
        data = np.bitwise_xor.reduce(self.blocks[idx], axis=0).tobytes()
        head = HDR.pack(MAGIC, VERSION, self.session, self.k, len(self.payload), self.bs, seq)
        return head + data + CRC.pack(zlib.crc32(head + data))


class Decoder:
    def __init__(self):
        self.session = None
        self.seen = set()
        self.rejected = 0

    def _init(self, session, k, plen, bs):
        self.session, self.k, self.plen, self.bs = session, k, plen, bs
        self.cdf = _soliton_cdf(k)
        self.blocks = [None] * k
        self.known = 0
        self.next_solve = k
        self.waiting = [[] for _ in range(k)]  # block -> pending symbols

    def add(self, raw):
        """Feed one decoded QR payload. Returns True if it was new and valid."""
        if len(raw) < OVERHEAD or raw[:2] != MAGIC:
            return False
        body, crc = raw[:-CRC.size], CRC.unpack(raw[-CRC.size:])[0]
        if zlib.crc32(body) != crc:
            self.rejected += 1
            return False
        magic, ver, session, k, plen, bs, seq = HDR.unpack(body[:HDR.size])
        if ver != VERSION or len(body) - HDR.size != bs:
            return False
        if self.session is None:
            self._init(session, k, plen, bs)
        elif (session, k, plen, bs) != (self.session, self.k, self.plen, self.bs):
            self.rejected += 1  # a different tape
            return False
        if seq in self.seen:
            return False
        self.seen.add(seq)
        idx = set(neighbours(seq, k, session, self.cdf))
        data = np.frombuffer(body[HDR.size:], np.uint8).copy()
        for i in list(idx):
            if self.blocks[i] is not None:
                data ^= self.blocks[i]
                idx.discard(i)
        if len(idx) == 1:
            self._resolve(idx.pop(), data)
        elif idx:
            sym = [idx, data]
            for i in idx:
                self.waiting[i].append(sym)
        if not self.done and len(self.seen) >= self.next_solve:
            self._solve()
        return True

    def _solve(self, max_unknown=2500):
        """Peeling stalled: finish with Gauss-Jordan over GF(2) on what's left."""
        self.next_solve = len(self.seen) + max(4, self.k // 50)
        unknown = [i for i, b in enumerate(self.blocks) if b is None]
        if len(unknown) > max_unknown:
            return
        syms = {id(s): s for i in unknown for s in self.waiting[i] if len(s[0]) > 1}
        if len(syms) < len(unknown):
            return
        col = {b: j for j, b in enumerate(unknown)}
        u = len(unknown)
        m = np.zeros((len(syms), u + self.bs), np.uint8)
        for r, (idx, data) in enumerate(syms.values()):
            m[r, [col[i] for i in idx]] = 1
            m[r, u:] = data
        row = 0
        for c in range(u):
            hits = np.flatnonzero(m[row:, c]) + row
            if not len(hits):
                return  # rank-deficient; wait for more symbols
            m[[row, hits[0]]] = m[[hits[0], row]]
            others = np.flatnonzero(m[:, c])
            others = others[others != row]
            m[others] ^= m[row]
            row += 1
        for j, b in enumerate(unknown):
            self._resolve(b, m[j, u:])

    def _resolve(self, i, data):
        stack = [(i, data)]
        while stack:
            i, data = stack.pop()
            if self.blocks[i] is not None:
                continue
            self.blocks[i] = data = data.copy()  # symbol buffers keep mutating
            self.known += 1
            for sym in self.waiting[i]:
                if i in sym[0]:
                    sym[0].discard(i)
                    sym[1] ^= data
                    if len(sym[0]) == 1:
                        stack.append((next(iter(sym[0])), sym[1]))
            self.waiting[i] = []

    @property
    def done(self):
        return self.session is not None and self.known == self.k

    def payload(self):
        return b"".join(b.tobytes() for b in self.blocks)[: self.plen]


# ---------------------------------------------------------------- packing
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "env", "virtualenv", "site-packages",
             "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".eggs",
             "build", "dist", "target", ".dart_tool", ".pub-cache", "Pods", "Carthage",
             ".build", ".swiftpm", "DerivedData", ".gradle", ".idea", ".vs", "vendor",
             ".next", ".nuxt", ".svelte-kit", ".angular", ".vite", ".parcel-cache",
             ".turbo", ".cache", "coverage", ".expo", ".terraform", ".serverless"}


def is_text(path):
    with open(path, "rb") as f:
        chunk = f.read(8192)
    if b"\0" in chunk:
        return False
    try:
        codecs.getincrementaldecoder("utf-8")().decode(chunk, final=False)
        return True
    except UnicodeDecodeError:
        return False


def select_code(root, max_size):
    """Code-only file list: git-visible (respects .gitignore) or walked, text only."""
    git = subprocess.run(["git", "-C", root, "ls-files", "-co", "--exclude-standard", "-z"],
                         capture_output=True)
    if git.returncode == 0:
        candidates = [p for p in git.stdout.decode().split("\0") if p]
    else:
        candidates = []
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            candidates += [os.path.relpath(os.path.join(dp, f), root) for f in fns]
    keep, skipped = [], {"binary": [], "too big": []}
    for rel in sorted(set(candidates)):
        if SKIP_DIRS.intersection(rel.split(os.sep)[:-1]):
            continue
        p = os.path.join(root, rel)
        if os.path.islink(p):
            keep.append(rel)
        elif not os.path.isfile(p):
            continue
        elif os.path.getsize(p) > max_size:
            skipped["too big"].append(rel)
        elif not is_text(p):
            skipped["binary"].append(rel)
        else:
            keep.append(rel)
    return keep, skipped


def pack_dir(path, files=None):
    """files=None packs everything; otherwise only these paths (relative to path)."""
    base = os.path.basename(os.path.abspath(path))
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:xz", preset=9) as tf:
        if files is None:
            tf.add(path, arcname=base)
        else:
            for rel in files:
                tf.add(os.path.join(path, rel), arcname=os.path.join(base, rel), recursive=False)
    data = buf.getvalue()
    return hashlib.sha256(data).digest() + data


def unpack(payload, out):
    digest, data = payload[:32], payload[32:]
    if hashlib.sha256(data).digest() != digest:
        sys.exit("checksum mismatch: decoded data is corrupt")
    os.makedirs(out, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as tf:
        tf.extractall(out, filter="data")


# ---------------------------------------------------------------- rendering
def qr_capacity(version, ecc):
    lo, hi = 1, 3000
    while lo < hi:
        mid = (lo + hi + 1) // 2
        try:
            segno.make_qr(b"\0" * mid, version=version, error=ecc, mode="byte", boost_error=False)
            lo = mid
        except segno.DataOverflowError:
            hi = mid - 1
    return lo


def render_qr(data, version, ecc, px):
    q = segno.make_qr(data, version=version, error=ecc, mode="byte", boost_error=False)
    m = np.pad(np.array(q.matrix, np.uint8), 4)  # 4-module quiet zone
    return np.kron(255 - 255 * m, np.ones((px, px), np.uint8)).astype(np.uint8)


def module_px(version, cols, rows, w, h):
    n = 17 + 4 * version + 8
    px = min(w // cols, h // rows) // n
    if px < 2:
        sys.exit(f"QR v{version} in a {cols}x{rows} grid doesn't fit {w}x{h}; lower --version or grid")
    return px


def compose(tiles, cols, rows, w, h):
    frame = np.full((h, w), 255, np.uint8)
    cw, ch = w // cols, h // rows
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        y = r * ch + (ch - t.shape[0]) // 2
        x = c * cw + (cw - t.shape[1]) // 2
        frame[y : y + t.shape[0], x : x + t.shape[1]] = t
    return frame


def open_writer(path, w, h, rate):
    return subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "gray",
         "-s", f"{w}x{h}", "-r", str(rate), "-i", "-", "-vf", "fps=30",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", path],
        stdin=subprocess.PIPE)


def parse_grid(s):
    c, r = s.lower().split("x")
    return int(c), int(r)


# ---------------------------------------------------------------- commands
def cmd_send(a):
    if not os.path.isdir(a.dir):
        sys.exit(f"not a directory: {a.dir}")
    cols, rows = parse_grid(a.grid)
    bs = qr_capacity(a.version, a.ecc) - OVERHEAD
    files = None
    if not a.all:
        files, skipped = select_code(a.dir, a.max_file_kb * 1024)
        print(f"code only: {len(files)} files; skipped {len(skipped['binary'])} binary, "
              f"{len(skipped['too big'])} over {a.max_file_kb} KB (--all to include everything)")
        if a.list_skipped:
            for why, paths in skipped.items():
                for p in paths:
                    print(f"  skip ({why}): {p}")
        if not files:
            sys.exit("no code files found")
    payload = pack_dir(a.dir, files)
    enc = Encoder(payload, bs)
    per_frame = cols * rows
    n_sym = math.ceil(enc.k * a.redundancy) + per_frame
    n_frames = -(-n_sym // per_frame)
    secs = n_frames / a.rate
    print(f"packed {a.dir}: {len(payload):,} bytes (xz) -> {enc.k} blocks of {bs} B")
    print(f"QR v{a.version}-{a.ecc.upper()} grid {cols}x{rows} @ {a.rate}/s "
          f"= {bs * per_frame * a.rate / 1024:.1f} KiB/s; tape {n_frames} frames, {secs:.0f}s "
          f"(min. ~{enc.k * 1.1 / per_frame / a.rate:.0f}s of clean capture)")
    if secs > 600:
        print("warning: over 10 minutes of video; consider a bigger --version/--grid")
    if a.dry_run:
        return
    px = module_px(a.version, cols, rows, a.width, a.height)
    w = open_writer(a.output, a.width, a.height, a.rate)
    seq = 0
    for _ in range(n_frames):
        tiles = [render_qr(enc.symbol(seq + i), a.version, a.ecc, px) for i in range(per_frame)]
        seq += per_frame
        w.stdin.write(compose(tiles, cols, rows, a.width, a.height).tobytes())
    w.stdin.close()
    if w.wait():
        sys.exit("ffmpeg failed")
    print(f"wrote {a.output}  (play fullscreen, on loop; film with the phone held steady)")


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:stream_side_data=rotation", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    w, h = s["width"], s["height"]
    rot = next((abs(int(d.get("rotation", 0))) for d in s.get("side_data_list", [])), 0)
    return (h, w) if rot in (90, 270) else (w, h)  # ffmpeg autorotates on decode


def frames(path, max_side):
    w, h = probe(path)
    scale = min(1.0, max_side / max(w, h))
    w, h = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", path, "-vf", f"scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    n = w * h
    try:
        while (buf := p.stdout.read(n)) and len(buf) == n:
            yield np.frombuffer(buf, np.uint8).reshape(h, w)
    finally:
        p.kill()


def scan(paths, max_side, on_payload):
    for path in paths:
        for i, f in enumerate(frames(path, max_side)):
            for r in zxingcpp.read_barcodes(f, formats=zxingcpp.BarcodeFormat.QRCode):
                if on_payload(r.bytes):
                    return
            if i % 30 == 0:
                on_payload(None)


def cmd_receive(a):
    dec = Decoder()
    frames_seen = [0]

    def feed(raw):
        if raw is None:
            frames_seen[0] += 30
            if dec.session is not None and not a.quiet:
                print(f"\r  frame ~{frames_seen[0]}: {len(dec.seen)} symbols, "
                      f"{dec.known}/{dec.k} blocks", end="", file=sys.stderr)
            return False
        dec.add(raw)
        return dec.done

    scan(a.videos, a.max_side, feed)
    print(file=sys.stderr)
    if dec.session is None:
        sys.exit("no qrtape codes found in the video(s)")
    if not dec.done:
        sys.exit(f"incomplete: {dec.known}/{dec.k} blocks from {len(dec.seen)} symbols "
                 f"(usually ~{math.ceil(dec.k * 1.05)} needed) - record another loop and "
                 f"pass both videos: receive a.mov b.mov")
    unpack(dec.payload(), a.output)
    print(f"ok: {dec.k} blocks from {len(dec.seen)} symbols "
          f"(overhead {len(dec.seen) / dec.k - 1:+.0%}), sha256 verified -> {a.output}")


CAL_VERSIONS = [10, 15, 20, 25, 30, 35]
CAL_GRIDS = [(1, 1), (2, 1), (2, 2), (3, 2)]


def cmd_calibrate(a):
    w = open_writer(a.output, a.width, a.height, a.rate)
    rng = np.random.default_rng(0)
    n_per = int(a.seconds * a.rate)
    shown = {}
    for v in CAL_VERSIONS:
        cap = qr_capacity(v, a.ecc)
        for cols, rows in CAL_GRIDS:
            try:
                px = module_px(v, cols, rows, a.width, a.height)
            except SystemExit:
                continue
            key = f"v{v}-{cols}x{rows}"
            shown[key] = n_per * cols * rows
            for i in range(n_per):
                tiles = []
                for t in range(cols * rows):
                    tag = f"CAL|{key}|{i}|{t}|".encode()
                    tiles.append(render_qr(tag + rng.bytes(cap - len(tag)), v, a.ecc, px))
                w.stdin.write(compose(tiles, cols, rows, a.width, a.height).tobytes())
    w.stdin.close()
    w.wait()
    print(f"wrote {a.output}: {len(shown)} settings x {a.seconds}s @ {a.rate}/s "
          f"({len(shown) * a.seconds:.0f}s). Film it start to finish, then run calibrate-read.")


def cmd_calibrate_read(a):
    got = {}

    def feed(raw):
        if raw and raw.startswith(b"CAL|"):
            _, key, i, t, _ = raw.split(b"|", 4)
            got.setdefault(key.decode(), set()).add((i, t))
        return False

    scan(a.videos, a.max_side, feed)
    n_per = int(a.seconds * a.rate)
    print(f"{'setting':<12}{'decoded':>9}{'KiB/s':>9}")
    for v in CAL_VERSIONS:
        cap = qr_capacity(v, a.ecc) - OVERHEAD
        for cols, rows in CAL_GRIDS:
            key = f"v{v}-{cols}x{rows}"
            total = n_per * cols * rows
            frac = len(got.get(key, ())) / total
            print(f"{key:<12}{frac:>8.0%}{frac * cap * cols * rows * a.rate / 1024:>9.1f}")
    print("Pick the highest KiB/s with decoded >= ~60%; pass it to send as --version/--grid.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def video_opts(sp):
        sp.add_argument("--rate", type=float, default=10, help="QR frames per second (default 10)")
        sp.add_argument("--width", type=int, default=1920)
        sp.add_argument("--height", type=int, default=1080)
        sp.add_argument("--ecc", default="m", choices="lmqh", help="QR error correction (default m)")

    s = sub.add_parser("send", help="directory -> QR video")
    s.add_argument("dir")
    s.add_argument("-o", "--output", default="tape.mp4")
    s.add_argument("--version", type=int, default=20, help="QR version 1-40 (default 20)")
    s.add_argument("--grid", default="1x1", help="QR codes per frame, COLSxROWS (default 1x1)")
    s.add_argument("--redundancy", type=float, default=1.6,
                   help="symbols per data block in one loop of the tape (default 1.6)")
    s.add_argument("--all", action="store_true", help="send every file, not just code")
    s.add_argument("--max-file-kb", type=int, default=1024, help="skip files bigger than this (default 1024)")
    s.add_argument("--list-skipped", action="store_true")
    s.add_argument("-n", "--dry-run", action="store_true", help="print size and duration only")
    video_opts(s)
    s.set_defaults(fn=cmd_send)

    r = sub.add_parser("receive", help="phone recording(s) -> directory")
    r.add_argument("videos", nargs="+")
    r.add_argument("-o", "--output", default="received")
    r.add_argument("--max-side", type=int, default=2160, help="downscale frames to this (default 2160)")
    r.add_argument("-q", "--quiet", action="store_true")
    r.set_defaults(fn=cmd_receive)

    c = sub.add_parser("calibrate", help="write a density-sweep clip to film")
    c.add_argument("-o", "--output", default="calibrate.mp4")
    c.add_argument("--seconds", type=float, default=3)
    video_opts(c)
    c.set_defaults(fn=cmd_calibrate)

    cr = sub.add_parser("calibrate-read", help="score a recording of the calibration clip")
    cr.add_argument("videos", nargs="+")
    cr.add_argument("--seconds", type=float, default=3)
    cr.add_argument("--max-side", type=int, default=2160)
    video_opts(cr)
    cr.set_defaults(fn=cmd_calibrate_read)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
