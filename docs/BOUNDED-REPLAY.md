# Focused xwave replay — issue #6 increment

This increment follows [the raster integration](GRAPHICS-RASTER-AUDIT.md).
It does **not** make the general window compositor asynchronous. Its narrow
invariant is that a focused xwave window is topmost, so its previously
sampled wireframe can be replayed by the application's existing bounded poll
loop after the compositor returns. No new syscall, UAPP entry, Z80 operation,
or global window-manager state is introduced.

On a focused damage callback, `paint_wave()` refreshes geometry and resets
only the drawing cursor to vertex zero. The manager still clears damage and
draws chrome synchronously; the callback draws no client vertices. Each later
`udeks_xwave_poll()` paints at most four vertices and commits, using the
already sampled cache. It leases the Z80 only when advancing beyond the
sampled prefix during initial plotting. Repeated drags can restart the replay;
the latest geometry wins, and a completed worker surface stays cached.

For an obscured xwave, the callback retains synchronous clipped-prefix
painting. Ordinary top-window incremental painting cannot be used for a
lower window: it would draw over overlapping windows above it. This is the
remaining architecture work for issue #6, together with synchronous damage
clear/chrome and exposed-clock repaint. A later compositor needs ownership,
occlusion and cancellation rules, plus placement proof before consuming the
49-byte raster reserve. Do not poll/yield recursively inside a compositor or
paint callback.

Host tests exercise the real application against an independent full-grid
wireframe reference. They verify synchronous obscured clipping, zero-vertex
focused callback, bounded per-poll replay, resize, cache reuse without another
worker lease, and stop/relaunch. Native 1986 D71/D64 stress drives 32 real
1351 drags with a background clock, Ctrl+C and console recovery. The harness
waits for the final replay to finish and checks that the worker still has
exactly 21 successful row leases and no fallback rows. VICE D71/D64 scheduler
and app smoke and shadow/bitmap equality are separate transport gates.

Compared with the integrated static-raster disk on the same native script,
worst release-to-drag-completion latency is 290 → 279 PAL frames for the
partial phase and 541 → 266 for cached drags. This is a bounded callback
increment, **not** faster total drawing: the last replay needs another 674
PAL frames (about 13.5 seconds) after release to finish on the tested 1986
run. Input can run between chunks, but the screen visibly fills in. The active
clock, window chrome and damage operations still take time. Physical-C128
qualification of this new image remains pending;
the user's earlier hardware confirmation applied to PR #9, not this change.

Exact disks, logs, source snapshots and checksums are preserved under
`bench/{artifacts,results}/2026-09-28-bounded-replay/`.
