# Generic background launch candidate — 2026-10-04

`generic-demo.d64` / `.d71` are the user-test images: normal UDEKS plus
HELLO.BIN and SECOND.BIN, containing identical independently linked C code.
Cold boot, then `hello &`, `second &`; click, drag, close, relaunch. Close all
with `xinit -q`. Neither filename appears in the OS launch catalog. Root
download snapshots were not replaced. This increment remains background-only.

`udeks.d64` / `.d71` are the corresponding unmodified build outputs.
`qualification.*` additionally contain missing/malformed/capacity test fixtures;
use the demo images for manual testing. `native-test.d64` is the ordinary build
with EMPTY/ONE storage-test files for the native 1986 four-app regression.

HELLO.BIN is 597 bytes: UDEX 0.2, 509 image bytes, two BSS bytes and 35 high-byte
patches. The o65 and map are retained, together with changed service images,
loader/resident maps and SHA256SUMS. The packer rebuilds the exact UDEX from
the o65 export and relocation records. No per-slot links or OS rebuild are
needed to install/rename this file. Source: `user/examples/xhello.c`.

See `bench/results/2026-10-04-generic-launch` and
`docs/GRAPHICAL-APPS-SDK.md` for the qualification boundaries and SDK recipe.
