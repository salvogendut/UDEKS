# Compact raster / banked receipt qualification

Standalone issue #14 experiment, 2026-09-29. Not a production adapter, boot
disk, live app/paging/Z80/NMI test, physical-machine result or latency claim.
See `docs/WINDOW-REPAINT-RASTER.md` for contracts, budgets and reproduction.

| Engine | Scenes | IRQ arrivals | Exact final bitmap |
| --- | ---: | ---: | --- |
| 1986 | 8 | 427,181 | matches reference |
| VICE | 8 | 425,942 | matches reference |

Both observe private-stack offset 211 and preserve compiler/MMU/status and
guard checks. Per-scene checksums are `[49629,45346,1790,64949,64211,8171,57,57329]`.
Final 8,000 bytes have SHA-256
`8efa40f4c55d395b9681363a2d872a625ea5a36532cad5a38b6d3ecc266423c7`.
The final bitmap is compared byte-for-byte; host complete-canvas tests and an
independent old-renderer oracle accompany the noncryptographic scene checksums.

Real C chrome/backend/receipt code, real 8502 pixel/span ASM and the exact
previously qualified banked policy run together. CLIENT is a mock row painter;
COMMIT is a bank-0 memory-copy model, not the VIC gateway. Stale work is rejected
after a title pointer is poisoned, without pixel/dirty/clip changes.

The full normal/panic sizing links charge the complete helper closure. The
component total is 2,013 CODE bytes, leaving 100 provisional bytes if old bodies
and reserve are granted. Poll/provider/admission/busy/teardown costs remain
uncharged; experimental sizing kernels are unbootable and must not be packaged.

`budget.json` binds archived inputs and outputs. Each run JSON binds its raw
record and native program to that exact report, with emulator provenance.
Artifacts, provider library, assembly, split-output maps and expected pixels
live in the matching `bench/artifacts/2026-09-29-repaint-raster` directory.
The SHA manifests cover every preserved file, including nested older manifests.
The diagnostic's heavy scans/frame termination budget are not a performance
acceptance bound. Normal disk/kernel hashes remain unchanged.
