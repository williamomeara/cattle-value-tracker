#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["segno", "zxing-cpp", "numpy"]
# ///
"""Pass/fail harness: fountain code, then send -> simulated phone capture -> receive.

The capture simulation is NOT a phone: it approximates perspective, blur,
noise, frame blending, dropped frames, mid-loop start and recompression.
"""
import os, random, shutil, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qrtape

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = [sys.executable, os.path.join(HERE, "qrtape.py")]


def test_fountain():
    rnd = random.Random(1)
    for k_bytes in [10, 900, 2_000, 300_000, 3_000_000]:
        payload = rnd.randbytes(k_bytes)
        enc = qrtape.Encoder(payload, 700)
        overheads = []
        for trial in range(3):
            dec = qrtape.Decoder()
            seqs = list(range(enc.k * 3 + 10))
            seqs = [s for s in seqs if rnd.random() > 0.3]  # drop 30%, incl. systematic
            rnd.shuffle(seqs)
            for s in seqs:
                dec.add(enc.symbol(s))
                if dec.done:
                    break
            assert dec.done, f"K={enc.k} failed to decode"
            assert dec.payload() == payload
            overheads.append(len(dec.seen) / enc.k - 1)
        print(f"  fountain K={enc.k:>5}: ok, overhead {', '.join(f'{o:+.0%}' for o in overheads)}")
    # corrupted symbol must be rejected
    dec = qrtape.Decoder()
    bad = bytearray(enc.symbol(0)); bad[40] ^= 1
    assert not dec.add(bytes(bad)) and dec.rejected == 1


def make_fixture(root):
    os.makedirs(f"{root}/sub/deeper")
    os.makedirs(f"{root}/empty_dir")
    open(f"{root}/empty.txt", "wb").close()
    with open(f"{root}/notes – ünïcödé 🎉.md", "w") as f:
        f.write("hello\n" * 200)
    with open(f"{root}/sub/random.bin", "wb") as f:
        f.write(random.Random(2).randbytes(60_000))  # incompressible
    with open(f"{root}/sub/deeper/script.sh", "w") as f:
        f.write("#!/bin/sh\necho hi\n")
    os.chmod(f"{root}/sub/deeper/script.sh", 0o755)
    os.symlink("sub/deeper/script.sh", f"{root}/link_to_script")


def tree(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        for n in dns + fns:
            p = os.path.join(dp, n)
            rel = os.path.relpath(p, root)
            if os.path.islink(p):
                out[rel] = ("link", os.readlink(p))
            elif os.path.isdir(p):
                out[rel] = ("dir",)
            else:
                out[rel] = ("file", open(p, "rb").read(), os.stat(p).st_mode & 0o111)
    return out


def degrade(src, dst, w=1920, h=1080):
    # Phone 1080p30 filming a screen: perspective skew, ~70% fill, focus blur,
    # sensor noise, frame blending at a mismatched rate, 25% random drops,
    # starts mid-tape, heavy recompression.
    vf = ",".join([
        "pad=iw*1.35:ih*1.35:(ow-iw)/2:(oh-ih)/2:color=gray",
        f"perspective=x0=40:y0=60:x1=W-10:y1=20:x2=0:y2=H-30:x3=W-60:y3=H-70",
        f"scale={w}:{h}",
        "gblur=sigma=1.2",
        "noise=alls=12:allf=t",
        "eq=brightness=0.04:contrast=0.85",
        "framerate=fps=29.97",
        "select='gt(random(0),0.25)'",
    ])
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", src], capture_output=True, text=True).stdout)
    # tape plays on loop; phone starts 40% in and films ~1.3 loops
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "2", "-ss", f"{dur * .4}",
                    "-t", f"{dur * 1.3}", "-i", src, "-vf", vf,
                    "-vsync", "vfr", "-c:v", "libx264", "-crf", "30", "-pix_fmt", "yuv420p", dst],
                   check=True)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("   ", (r.stdout + r.stderr).strip().replace("\n", "\n    "))
    return r.returncode


def make_code_fixture(root):
    make_fixture(root)
    os.makedirs(f"{root}/node_modules/dep")
    open(f"{root}/node_modules/dep/index.js", "w").write("junk\n")
    open(f"{root}/app.zip", "wb").write(b"PK\x03\x04" + bytes(500))
    open(f"{root}/secret.env", "w").write("KEY=1\n")
    open(f"{root}/.gitignore", "w").write("secret.env\n")
    open(f"{root}/untracked.py", "w").write("print('new, not ignored')\n")
    subprocess.run(["git", "init", "-q", root], check=True)
    subprocess.run(["git", "-C", root, "add", "-A", ":!untracked.py", ":!node_modules"], check=True)


CODE_EXPECTED = {".gitignore", "notes – ünïcödé 🎉.md", "empty.txt", "link_to_script",
                 "untracked.py", "sub", "sub/deeper", "sub/deeper/script.sh"}


def test_e2e(tmp, extra, label, code=False):
    src = f"{tmp}/src_{'code' if code else 'all'}/project"
    if not os.path.exists(src):
        (make_code_fixture if code else make_fixture)(src)
    tape, cam, out = f"{tmp}/tape.mp4", f"{tmp}/cam.mp4", f"{tmp}/out_{label}"
    print(f"  e2e [{label}] {' '.join(extra)}")
    t = time.time()
    assert run(TOOL + ["send", src, "-o", tape] + extra) == 0
    degrade(tape, cam)
    assert run(TOOL + ["receive", cam, "-o", out, "-q"]) == 0, "receive failed"
    a, b = tree(src), tree(f"{out}/project")
    if code:
        assert set(b) == CODE_EXPECTED, f"code selection wrong: {set(b) ^ CODE_EXPECTED}"
        a = {k: v for k, v in a.items() if k in CODE_EXPECTED}
    assert a == b, f"tree mismatch: {set(a) ^ set(b) or 'contents differ'}"
    print(f"    tree identical ({len(a)} entries), {time.time() - t:.0f}s")


def main():
    print("fountain code")
    test_fountain()
    tmp = tempfile.mkdtemp(prefix="qrtape-")
    try:
        print("end to end (simulated capture)")
        test_e2e(tmp, ["--all"], "all-files")
        test_e2e(tmp, ["--all", "--version", "25", "--grid", "2x1"], "dense")
        test_e2e(tmp, [], "code-only", code=True)
    finally:
        shutil.rmtree(tmp)
    print("PASS")


if __name__ == "__main__":
    main()
