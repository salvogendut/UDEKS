# Deferred background repair at drag start

The user rejected the prefix-cache candidate's xclock drag latency. Native
mouse reproduction found 265 PAL frames (5.3 seconds) from button-down to the
outline when a completed xwave was below xclock, versus 17 frames with only
xclock. Earlier suites dragged xwave, not xclock over xwave, and missed this.

`begin_drag()` recomposed exposed lower windows synchronously. A background
xwave replays its completed wireframe in the 8502 painter: it does not start a
new Z80 computation, but still delays the outline.

With the user's approval, the new isolated candidate clears the old rectangle
and shows only the moving outline. Exposed background stays temporarily yellow
until release. `finish_drag()` repairs the union of old and new rectangles.
The existing compositor has a private erase-only selector, 255, which invokes
no client callbacks. A valid retained move keeps its saved image; other drag
paths still invalidate ownership. Resize, destroy and cancellation keep their
normal repair paths. This is not a new public ABI or normal-build promotion.

## Qualification

Native 1986 real mouse input, identical emulator provenance, D71 and D64:

| Button-down to completed outline | Prefix candidate | Deferred candidate |
| --- | --- | --- |
| xclock alone | 17 frames | 17 frames |
| xclock over completed xwave | 265 frames | 16 frames |

The regression gate allows at most 30 frames for the overlap case, verifies
outline movement with native mouse events, no extra Z80 jobs, shadow/VIC
agreement, Ctrl+C, subsequent console typing and graphics shutdown. This is
drag-start timing, **not** release-to-complete-background timing. Background
repainting after release remains synchronous and can take seconds.

Host full-canvas tests compare release results with the previous compositor
for move, resize, close during drag and retained wave moves. Both-format
native qualification also covers early drag, 16 cached moves, partial-paste
cancellation, oversized resize, NMI, guards and graphics restart. Forced clock
repair canvases remain byte-identical to the previous candidate. VICE tests
cold boot, pixels, NMI and restart, not real VICE mouse interaction.

Manager CODE 7,762 bytes (+12), RODATA 130, HIGHBSS 88; transport 377; held
padding 20. Normal/panic segment boundaries and helper closures stay unchanged.
A clean parallel private rebuild produces identical disks:

- D64: `4872d6aa0471deda7868a4a371fb9d6f792e61588cf1078d3f40b05fc239f2d9`
- D71: `e3eaa384558e2a99c2431436e4ba99ac820ac216c8fa574c7c6ce7a1355cfecb`

Reproduce with `tools/window_drag_start.py` actions `build`, `clean`, `1986`,
`vice`; run `tools/window_drag_latency.py partial` and `deferred` in the SDL
container, then `window_drag_start.py preserve`. Immutable disks, source,
runners, maps, logs, raw pixels and checksums live under
`bench/{artifacts,results}/2026-09-29-window-drag-start`. No ROM-bearing snapshots
are archived. Normal disks and the 1986 source tree are untouched.

## Manual test

Boot the archived test disk, run `xinit`, `xclock &`, then `xwave &`. Move xwave
below the clock's exposed title, then drag xclock. Check the shorter start
delay, moving outline with temporarily blank background, correct pixels after
release, resize and typing in the VDC console. Physical hardware and manual
input acceptance remain separate gates before normal-cache promotion.
