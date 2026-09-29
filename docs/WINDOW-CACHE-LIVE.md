# Live window-cache test candidate — 2026-09-28

This is the first integrated **pixel-cached move** candidate. It is built in a
private repository copy, not enabled by normal `make boot`. The normal D71/D64
and provider outputs stay byte-identical. Manual visual/input and physical-C128
qualification remain gates before promoting it into the normal build.

Manual feedback received on 2026-09-28: the user reports, "it all looks good to
me." This accepts the presented candidate's appearance/behavior. The platform
and individual test cases were not specified, so this is not a physical-C128,
RESTORE/NMI or measured-latency qualification. Normal-build promotion remains
separate from that feedback.

A later [band-boundary repaint candidate](WINDOW-CACHE-REPAINT.md) provides new
test disks, measured page-copy reductions and a shutdown IRQ correctness fix.
The records and image hashes below remain the original accepted checkpoint.

## What to test

Use the separate `udeks-cache.d64` or `udeks-cache.d71` under
`bench/artifacts/2026-09-28-window-cache-live/build/`, or the identical copies
under `build/window-cache-live/`. The private repository's ordinary
`repo/build/boot/udeks.d71` is **not** this image: it lacks the delivered module.

```text
xinit
xclock &
xwave
```

Wait for the initial plot and image capture to finish. Then:

1. Drag the wave by its title bar several times, including over the clock and
   toward screen edges. Only the outline moves while held. After release, the
   completed wave should return from retained pixels, without a new line-by-line
   function plot. There is still a visible repaint delay.
2. Leave the clock running through a seconds change, and move the wave again.
   The clock's update should not force the wave to re-plot.
3. Resize the wave. This intentionally invalidates cached pixels and redraws at
   the new geometry. Images beyond the 2,224-byte lease use ordinary redraw.
4. Press Ctrl+C at the VDC console, including while a move is being repainted.
   The wave should exit, the clock should remain, and typing should still work.
5. Run `echo console alive`, then `xinit -q`, `xinit`, and `xwave &` to check
   shutdown, restart, background launch and continued console input.

Dragging during the initial incomplete plot deliberately falls back to redraw;
it is not a cache-hit test. Focus/restack/content changes also invalidate.

## Integrated placement

The 4,106-byte qualified compact module includes its immutable common-gateway
source. The accepted module is delivered at bank-1 `$4200–$5209`, with VCC2 at
`$5210`, private state at `$5220`, a guarded private stack at `$5250–$533F`, and
the packed image at `$5350–$5BFF`. The temporary scheduler source is `$6000`.

The complete resident transport and C command wrapper charge 377 CODE bytes,
including all five seam state bytes and the diagnostic helper. Applying cc65
`register` to local window pointers recovers 521 CODE bytes with identical
host drawing/state traces; adding the real hooks costs 487. The net manager
change is therefore −34 bytes (7,679 → 7,645 CODE). RODATA remains 130 and
HIGHBSS remains 88; no BSS/ZP/helper growth is admitted. Of the previous 502
padding bytes, 159 remain. The outline reserve is untouched.

Both real normal/panic links preserve **every segment**, including the exact
8,000-byte shadow `$A1E0–$C11F`, common gates, stacks and published runtime ZP.
All private import bridges/checksum installers are regenerated from these new
links. An earlier transport-only link with stale bridges must not be booted.

## Ownership and bounded work

Capture freezes its source; paste freezes its destination. Each manager poll
runs at most four row STEP leases, restoring MMU, cc65 runtime, status, hardware
stack and IRQ ownership between every row. Dirty screen pages commit once per
batch. A new click is deferred while paste finishes; pointer IRQs and console/
task polling continue. Early drag, resize, restack, new content, close/reuse,
shutdown and cancellation invalidate or take the original redraw fallback.

A cached move recomposes the background while skipping its owner, then pastes
the retained image. Updates to a lower clock likewise restore the top wave
from retained pixels rather than calling its painter. During synchronous
background composition, the resident phase is temporarily `$82` (READY plus
frontend-busy); the banked flow stays READY. Screen consumers must not mistake
that interval for a completed presentation. The following PASTE publishes 3
and completes at 2. This is a private frontend state, not a public ABI change.

The private xwave build also publishes the callback's handle before initial
paint: the global handle is not yet assigned during `window_create`'s callback.
This fixes diagnostic publication without growing the full bootfs.

## Qualification scope and cost

Both D71 and D64 pass the native 1986 keyboard/1351 runner: incomplete-plot
fallback, 16 repeated cached moves covering all horizontal alignments, every
one of 17,472 window pixels against both shadow and VIC bitmap, unchanged wave
painter/21 Z80 lease counters, clock updates, partial-paste Ctrl+C, oversized
resize fallback, slot reuse, shutdown/restart, typing/history and RESTORE/CIA2
NMI pressure. State/stack guards and the immutable module are checked. Only the
row core's two self-modifying address operands and four scratch bytes may vary;
operands must point to the exact completed last row. Every other module/header/
padding byte remains exact. The test runner uses 1986's positional Equals key
for the C128 minus key; it does not patch the OS keyboard queue.

VICE 3.10 independently cold-boots both formats and verifies the full default
image, full shadow/bitmap equality, immutable gateway source, stack guard, NMI
drain/handoff and graphics shutdown/restart. Its commands use the existing
line-editor diagnostic seam; **VICE native mouse dragging is not claimed**.
The complete native move/input sequence is covered by 1986 instead.

Sampled PAL native runs take about 60–81 frames from mouse release to completed
background repair, followed by 139–164 frames to settled cached presentation.
That is roughly 4–5 seconds combined, not instant blitting. Clock repair and
dirty-page commit remain substantial costs. This candidate proves retained
pixel reuse and bounded ownership, not completion of issue #6's responsiveness
gate. Physical RESTORE/Z80 NMI routing remains separately unqualified.

The final regression gate passes 781 host tests, archive checksums and Python
compilation. Normal container `boot`, `all` and `placement-check` pass unchanged.

A clean private `make -j8` rebuild produces the same test disks:

- D71: `a172c4cf965fbd06d32f360682e006dd4cc4bf61a864185cb96bfbba46633e3f`
- D64: `098160836ba442bbe739fbf08afefd02bedac8292eb6f9a0ea7c356c8240c588`

Generated sources, objects, maps, import bridges, split outputs, disks, input/
report hashes, machine records, logs and emulator provenance are preserved in
`bench/{artifacts,results}/2026-09-28-window-cache-live`. Full snapshots containing
ROMs are deliberately not archived. Build report qualification describes the
pre-run candidate; the matching two emulator run bindings supply the gate.

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_live.py build
distrobox enter my-distrobox -- python3 tools/window_cache_live.py 1986
python3 tools/window_cache_live.py vice
python3 tools/window_cache_live.py preserve
```

Preservation refuses existing evidence or changed inputs/disks/results. With
positive manual feedback recorded, the next engineering gate is measuring and
reducing background repair and commit cost before normal-build promotion.
Start by counting dirty-page copies per cached move: the current four-row batch
commits whole 256-byte pages, so adjacent batches can copy the same screen page
again. Compare bounded alternatives while retaining pointer/keyboard polling,
Ctrl+C, guards and full pixel equality. Do not freeze hardware behavior from
emulator-only evidence.
