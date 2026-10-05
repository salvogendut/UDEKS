# Native clock: generic geometry events and independent resizing

This supersedes the fixed-size candidate in `2026-10-04-native-clock`, without
overwriting it or changing the default legacy clock/wave programs. Parent
checkpoint: `9f2e994` on `graphics-native-clients` / issue #35.

UTRQ 0.10 allows RESIZABLE CREATE and seven-byte EVENT replies containing the
current window dimensions. Caller-supplied last-rendered dimensions acknowledge
changes; moves alone do not trigger a resize, and pending clicks are preserved
until geometry is acknowledged. UTRQ 0.9 remains unchanged. Scaling is C code
inside NCLOCK.BIN, not a clock-specific operation in the graphics service.

`NCLOCK.BIN` is 2,770 bytes (2,180 image, 369 private BSS), fitting both the
4,608- and 2,816-byte native allocations. The builder checks file length and
image+BSS separately. It uses private static locals because this application
is nonrecursive; each relocated task has its own copies. The old console
loader's size rejection now also permits one-word foreground commands to try
the independently validating native loader. That matters for files >2,560
  bytes; it does not bypass native format, range or allocation checks.

## Qualification

- VICE 3.10, D64/1541, D71/1571, D81/1581: identical executable in both slots;
  complete relocated code equality, retained commands against an independent
  geometry oracle, default 72×88, 126×130, minimum 48×48, regrow, and an
  independent 180×140 peer. Moves do not regenerate drawing within the same
  minute. Time changes, foreground Ctrl+C, reuse, four-window coexistence,
  running-panel bytes/attributes, console, guards and bitmap/shadow equality.
  Pointer actions use monitor-injected WM state, not physical mouse evidence.
- Unmodified 1986 `81485cc7`, D64/1571 and D81/1581: the same sequence uses
  native keyboard and 1351 input, including close/reload. The harness waits for
  the outline to sample the final position before releasing. Native pointer
  endpoints may differ by one pixel; expected dimensions are independently
  calculated from the sampled pointer and outline origin before release.
- Host tests cover old/new sizing flags, ownership, coalescing, pending-click
  preservation, closed handles, width >255, invalid dimensions and untouched
  output on rejection. The 43-command clock model is checked at every minute
  and across a range of window sizes.
- Original xclock/xwave/xcalc/xdraw four-app VICE D64 regression also passes;
  `legacy-four-apps.json` and its log preserve the compatibility result.
- 1,118 host tests pass. A fresh parallel source-only container build reproduces
  D64/D71/D81, NCLOCK.BIN and the graphics module byte-for-byte. Existing build
  products and historical evidence were not used as build inputs.

The service uses an absolute array binding to the existing common request
record, avoiding repeated pointer-materialization instructions. Its existing
reservation is unchanged: GRAPHICSCODE `$0C00-$11FC`, GRAPHICSHELP
`$A100-$A1D7`, resident BSS through `$9AE6`. No task, software stack, hardware
page, loader, shadow or common gate moved. Normal/panic placement gates pass.

Each VICE `.bin` has a two-byte monitor load-address prefix. Reports bind the
test disk and program hashes; `*-geometry.bin` contains width LE16 + height,
and `*-commands.bin` / `*-retained.bin` preserve all 43 commands. The drawing
oracle lives in `tools/native_clock_probe.py`, separate from the target C model.
Artifacts and SHA256SUMS are in `bench/artifacts/2026-10-04-native-resize`.

## Try it

Cold boot `build/native-clients/resize-demo.d64`, `.d71` or `.d81` (1581 selected
and emulator restarted for D81), then:

```text
nclock &
clock2 &
```

Move one aside and resize both using their lower-right grips. Contents remain
hidden during the outline drag, then the clock redraws to the committed size.
`date 214500` updates both; close one and launch it again; `xinit -q` ends both.
The default `xclock`/`xwave` remain legacy pending native-wave and four-slot
migration. Physical C128 confirmation of this resize candidate remains due.

Rebuild with container `make boot native-clock graphics-apps-check
placement-check`; host `make native-clock-probe` reruns all three VICE formats.
The native input gate is `tools/1986_storage_smoke_build.py --native-clock`;
add `--disk build/boot/udeks.d81 --drive 1581` for D81.
