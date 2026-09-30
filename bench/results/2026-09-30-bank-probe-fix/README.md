# Bank-probe regression evidence — 2026-09-30

The archived issue #24 candidate overwrites bank-0 `$8000` with `$A0` during
stage 1. That byte should be `$06`, a zero-page operand in the linked graphics
clip routine. The fix uses `$1000` scratch below both loaded payloads and does
not change the resident image or window-manager implementation.

Native 1986 raw-IEC tests use unmodified sibling source and actual keyboard /
1351 input: mount, uname -a, z80ctl test, implicit-desktop xclock &, repeated
drags, xwave &, wave drag, cowsay hello. The original image fails after its
first drag with 294 missing border pixels. The fixed image passes 12 clock
drags plus wave creation/drag (14 complete-border checks). Merely checking
movement counters had falsely passed the old image; the improved harness
checks the physical bank-1 bitmap, not only window bookkeeping.

`*-site.bin` captures `$8000-$8007`; `*-status.bin` captures bank-0
`$F040-$F3EF`; `*-bitmap.bin` is bank-1 `$6000-$7F3F`. The pre-fix snapshot
is at the first failed clock border; the post-fix one follows cowsay. Their
different scene states are intentional, not a byte-identical image comparison.
JSON records include the exact disk hashes and emulator revision.

VICE also passes the full disk-command/graphics sequence and typed BASIC BOOT
with true 1541 / model c128 on both original and fixed images. The typed-BOOT
probe starts on a blank disk, attaches the candidate and types the BASIC
command; it does not jump into guest code. The diagnostic SETMSG-enabled copy
is tested separately. The original hardware failure is NOT reproduced in VICE
and remains open pending the user's diagnostic-disk result.

Reproduce from my-distrobox:

```
python3 tools/1986_storage_smoke_build.py --emulator ../1986 --roms ../1986/roms --drag-regression --output build/drag-regression
```

Use absolute emulator paths when running from a nested worktree. Add `--disk`
pointing at the original archived D64 to reproduce the expected failure.
