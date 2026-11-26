# qrtape

Move a directory across an air gap: laptop screen → phone camera → laptop.

```bash
./qrtape.py send ~/some/dir -o tape.mp4      # play fullscreen, on loop
# film the screen with your phone, AirDrop the .mov back
./qrtape.py receive IMG_1234.MOV -o out/     # rebuilds out/dir, sha256-verified
```

How: `tar.xz` → SHA-256 prefix → fountain code (LT; systematic pass, then
coded symbols; peeling + GF(2) elimination when it stalls) → one symbol per
QR (byte mode, 25-byte header + CRC32) → H.264. Any ~1.05–1.2×K distinct
symbols rebuild the data, so dropped frames, blur and starting mid-loop
don't matter. Short? Film another loop: `receive a.mov b.mov`.

Throughput is set by `--version` (QR size) × `--grid` (codes per frame) ×
`--rate` (frames/s). Default v20, 1×1, 10/s ≈ 6 KiB/s (very conservative).
Find your phone's real ceiling:

```bash
./qrtape.py calibrate -o cal.mp4             # 72 s density sweep; film it
./qrtape.py calibrate-read IMG_5678.MOV      # table of decode% and KiB/s
```

`./harness.py` is the pass/fail check: fountain-code tests plus
send → simulated phone capture (perspective, blur, noise, frame blending,
drops, mid-loop start, recompression) → receive → byte-identical tree.
Simulation is not a real phone.

By default only code is sent: git-visible files (respects .gitignore), text only
(no zips/exes/images), nothing over 1 MB, junk dirs like node_modules skipped.
`--all` sends everything; `--dry-run` prints size and duration only.

Requires `uv` and `ffmpeg`.
