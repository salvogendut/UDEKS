# Installed shared-raster qualification

D71/D64 pass native 1986 32-drag stress with a background clock, lifecycle
guards, partial/complete plots, exactly 21 Z80 leases, Ctrl+C and subsequent
console input. The normal D71 input smoke also passes typing/backspace/history,
1351 dragging, early foreground cancellation and background-app recovery.
VICE both-format boot/scheduler/app/utility/input-wait smokes pass; its shadow
clear/installed-tail gate passes and all 8,000 bitmap bytes match between banks.
Native mouse drag stress was not performed in VICE. Hardware/visual resize
and overlap testing remains pending. No sibling emulator files were edited.

The same harness reruns the preceding span/pixel checkpoint: maximum partial
release 171→107 PAL frames; completed release 167→103; remaining replay after
the last release 970→655. Completed-wave cancellation is **140→161**, not an
improvement. These are scripted samples, not guarantees; full repaint remains
slow and compositor acceptance stays open.

The full link saves 294 additional bytes, held as padding. Cache reserves now
total 516 and still need at least 507 more before bindings/bounded state. No
cache is installed. Clean parallel build reproduces the exact disks saved in
the matching artifacts. `qualification.json`, logs, provenance, map budgets
and normalized bitmap captures preserve the checks. No ROMs/full snapshots
are saved. SHA-256 manifests exclude this explanatory README.

See `docs/GRAPHICS-SHARED.md` for reproduction and user testing;
`tools/graphics_primitives_qualify.py --shared --preserve` refuses overwrite.
