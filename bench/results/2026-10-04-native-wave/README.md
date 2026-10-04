# Native wave and generic retained paths, UTRQ 0.12

Parent checkpoint: `885ca87`; sources are preserved by this evidence commit.
Exact normal boot media, compiled service modules and independently built
NWAVE/NCLOCK programs are in `bench/artifacts/2026-10-04-native-wave`.
Published root `build/udeks.*` snapshots are untouched. Captured `.bin` files
have VICE's two-byte load-address prefix; do not treat that as app data.

## Qualified

- VICE x128 D64/1541 and D81/1581: ordinary `nwave &`, then `nclock &`, without
  any kernel name-table entry. NWAVE runs in the larger native allocation;
  it is not small enough for the second. Legacy XCLOCK/XWAVE stay on the disk.
- All 525 samples and 524 grid edges match independent oracles. The app uses
  21 bounded Z80 row requests once per load. Private heights survive old wave
  overwriting common worker output. Moves do not PRESENT again or lease the
  Z80; resize rebuilds packed geometry from cached heights without new leases.
- Grow, minimum size, regrow, stacking with a native clock, date, console
  cowsay, four-window compatibility, shutdown, reap, reload and guard checks.
  Repaints still rasterize retained vectors; this is not a pixel-blit latency
  or native mouse qualification. Intermediate outline sizes may be reported
  by EVENT and reprojected while a resize is held.
- The custom VDC font remains byte-identical after the boot glyph source is
  replaced by code/state. Live asset header and tile maps remain byte-identical.
  A paused monitor steps the four-instruction post-install console guard to
  RTS, then restores PC/A/X/Y/SP/flags/MMU before resuming (no borrowed stack).
- D71/1571 full native-clock regression: both relocations, date, drag/resize,
  targeted foreground Ctrl+C, reload, four apps, actual VDC panel and bitmap
  equality. D64 default four-app calculator/drawing regression also passes.
- Normal/panic real-map checks, separate delivery/retention lifetimes and
  exact module packaging pass. A fresh source copy built with `make -j8`
  reproduces D64/D71/D81, both modules and both candidate executables.

No new 1986 or physical-C128 evidence is claimed. The old four-app model is
preserved; four interchangeable native allocations and default cutover remain
the next feature work. These tests do not claim improved repaint speed.

## Placement and regression lessons

Bank-0 glyph-only overlay `$96B8-$9AA7`: PATHSTATE 60 bytes, GRAPHICSPATHS 938,
10 padding bytes. The 16-byte header before it and 88-byte tile maps after it
remain live. Base graphics uses 1,535/1,536 bytes at `$0C00`; BSS ends `$9693`,
20 bytes before the assets. Storage code ends `$C50C`, below its `$C600` bound.
Bank-1 `$C600-$CFFF` first delivers the modules, then becomes two 1,280-byte
retained images. No task image, stack, CPU page or common gate moved.

Two initially failing probes were corrected before qualification:

- cc65 static locals in a code-named BSS segment put data at function entry
  labels. Separate emitted state/code segments fix this; the actual map checks
  exported entries are inside executable code. Host C alone cannot catch it.
- A shell WAITING state may be a command-completion POLL, not input readiness.
  The wave probe now reads task state in bank 0 and waits specifically for READ
  before injecting the next command. Earlier injected keys were correctly
  discarded while the console was not yet accepting input.

## Reproduce

```sh
distrobox enter my-distrobox -- make -j8 boot native-wave native-clock graphics-apps-check placement-check
make check
python3 tools/native_wave_probe.py --disk build/boot/udeks.d64 --drive 1541 --output build/native-clients/paths-wave-final-d64
python3 tools/native_wave_probe.py --disk build/boot/udeks.d81 --drive 1581 --output build/native-clients/paths-wave-final-d81
python3 tools/native_clock_probe.py --disk build/boot/udeks.d71 --drive 1571 --output build/native-clients/paths-clock-vice-d71
python3 tools/xcalc_probe.py --disk build/boot/udeks.d64 --drive 1541 --four-apps --output build/native-clients/paths-baseline-four
```

The independent app is 2,221 file / 1,741 image / 1,681 BSS bytes, built with
the reference my-distrobox cc65 toolchain. The identical NCLOCK file remains
2,770 file / 2,180 image / 369 BSS bytes and fits either native allocation.
Every probe terminates its own VICE process group; no user session is reused.
