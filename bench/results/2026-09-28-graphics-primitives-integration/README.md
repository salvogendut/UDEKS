# Installed span/pixel qualification — 2026-09-28

Exact testable D71/D64 disks and source/maps are in the matching artifact
directory. Both are deterministic across a clean parallel container build.
The installed display service saves 170 CODE + 3 BSS = 173 bytes, held as
named CODE padding. Shadow `$A1E0-$C11F`, common gateway extents, scheduler,
module/stack allocations and UAPP zero-page ABI remain unchanged.

Native 1986 D71/D64 stress passes 32 real-input wave drags with a background
clock, lifecycle guards, exactly 21 Z80 row leases and console cancellation.
The normal D71 input suite passes typing/backspace/history, 1351 dragging,
early foreground cancellation, background apps and console recovery. No
sibling emulator files were modified. The qualifier checks its input hashes
against the standalone pixel run and records provenance.

The same current harness reruns the preserved no-replacement D71. Maximum
partial release changes 279→171 PAL frames, completed release 266→167, and
completed-wave cancellation 174→140. Remaining replay after the last release
is **674→970** frames. Scripted release timing changes remaining work; this
is not an improved full-image-completion claim. Repaint still takes seconds.

VICE D71/D64 scheduler/app/utility/input-wait checks pass. Its shadow-clear
and installed-tail probes pass, and the two normalized raw bitmap files match
in all 8,000 bytes. Native mouse drag stress was not run in VICE. Physical
C128 and visual resize/overlap qualification remain pending. No pixel move
cache is installed; issue #6 stays open.

`qualification.json` records measured placement, exact disk hashes, provenance
and timings; the logs retain every drag sample. No ROMs or full snapshots are
preserved. `SHA256SUMS` excludes this explanatory README.

See `docs/GRAPHICS-PRIMITIVES.md` for the user test and reproduction procedure.
`tools/graphics_primitives_qualify.py` refuses to overwrite these records.
