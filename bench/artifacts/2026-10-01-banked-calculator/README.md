# Banked calculator candidate — 2026-10-01

Exact working-tree artifacts on `graphics-four-apps`, based on `b94bd43`.
These are qualification images, not refreshed main/release downloads.

Build: `distrobox enter my-distrobox -- make -j8 boot graphics-apps-check
placement-check`. A fresh source copy under `build/four-apps/clean-graphics.DOK1Wc`
reproduced both disk images, `xcalc.udx` and `banked-graphics.bin` byte-for-byte.
Normal/panic maps and graphics outputs agree. The resident calculator was
replaced by a flag-0 native C executable at bank-1 `$2300`; clock and wave stay
at their existing bank-0 addresses.

Preserved files include D64/D71, calculator image/map, resident map, split
graphics module, and private banked loader image/map. Module sizes: graphics
1,536-byte padded output (1,477 bytes code); banked loader 1,792 bytes; calculator
3,912 image + 412 BSS. See the matching results directory for commands, raw
captures, layout/hash report and limitations. Checksums cover the exact files.

The combined candidate is ready for a three-app test in 1986/on C128. No new
native input or hardware acceptance is asserted; a fourth graphical client
has not been integrated yet.
