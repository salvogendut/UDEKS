# Default normal window-cache build

The qualified generic cache now has a regular source-built configuration:

```
distrobox enter my-distrobox -- make -j8 boot all panic-probe placement-check
```

It produces the normal `build/boot/udeks.d64` and `.d71` paths. `WINDOW_CACHE=1`
is the hardware-accepted default; `WINDOW_CACHE=0` selects the prior compositor.
Switching configurations rebuilds the affected compiler,
transport, scheduler-envelope and disk outputs without requiring a clean.
Do not run different configurations concurrently in the same build directory.
The direct development PRG is a bootstrap diagnostic, not the bank-1 cache
delivery path; use the native boot disks for window-cache testing.

## Integration contract

The module sources live in `src/services/window/cache`; the selected compositor
is `window_manager_cached.c`. No archived binary, private clone, app transform,
new xwave projection table, extra application BSS, or kernel-specific wave
policy is used. The unselected compositor stays available as an explicit fallback.
Host tests compare the selected source with the qualified generic candidate
and exercise its full canvases after move, resize, destruction and retained
movement. The specialized module C also matches the host-qualified providers.

The bank-1 module compiles from source at $4200. Its gateway is an exact suffix;
the build generates the VCC2 identity, bounded validator page count, module
checksum, and gateway source/length from that link. Scheduler sources move to
$6000, while the disk LOAD begins at $4200. Those are deliberately different:
the installer validates USOV at $6000, not the cache at the start of the file.
Installed scheduler addresses, UAPP/cc65 zero page and syscall gates do not move.

The selected manager is 7,762 CODE / 130 RODATA / 88 HIGHBSS bytes, with a
377-byte fully charged transport and 20 bytes of held padding. Before packaging,
the build rejects changes to any qualified normal/panic segment, including the
$A1E0–$C11F shadow. Runtime acceptance verifies identity and the entire module
before executing banked C. Capture/paste retains the existing four-row poll
budget, invalidation, source/destination ownership, guards and redraw fallback.

Dragging shows only the outline. Exposed background remains yellow until
release, when composition repairs it. Background repair remains synchronous
and can take seconds; this integration is not a new general speed claim.
Xwave-local projection/render optimizations remain separate future work.

## Qualification and manual gate

Both D64/D71 pass native 1986 keyboard/mouse, cached moves, overlap clock repair,
resize fallback, partial-paste cancellation, subsequent typing, NMI stress and
graphics shutdown/restart. Both pass VICE cold boot, complete pixels, NMI and
restart; native VICE mouse input is not inferred from monitor-based checks.
Actual selected disks also pass clock-only and clock-over-wave drag-start
tests at 17 PAL frames in both formats, within the 30-frame guard. The observer
waits for the dirty map to drain and full shadow/VIC equality, rather than
sampling a periodic clock repaint after an arbitrary delay.
Fresh source-only parallel builds and a 1→0→1 configuration switch reproduce
the selected disks and the unchanged prior default disks exactly. Evidence:
`bench/{artifacts,results}/2026-09-29-window-cache-integration`.

Stable copies for testing live in `build/window-cache-integration/udeks-cache.d64`
and `.d71`, independent of the currently selected normal build configuration.
Boot one, then run:

```
xinit
xclock &
xwave &
```

Move the wave below the clock title, then drag the clock. Check prompt outline
start, outline-only motion, correct content after release, resizing and VDC
typing. Run `xwave` in the foreground separately and check Ctrl+C, followed by
`xinit -q` and a graphics restart. On physical hardware also check RESTORE
during activity and verify input/console responsiveness afterward.

Real-hardware feedback (2026-09-29): the user reports "it looks ok on real HW"
for this integration. This records positive overall manual feedback, not an
itemized test log or confirmation of the disk format/hash used. The user also
confirms pressing RESTORE while dragging a window on real hardware, with input
still working afterward. This closes the requested manual RESTORE/input gate;
it does not establish every possible NMI source or CPU-handoff case on hardware.
The user subsequently approved default promotion, scoped commit/push and PR
merge. The archived qualification records retain their original opt-in status;
the default produces the same qualified disk bytes. The cache remains a
window/display-service concern, not a kernel or xwave-specific optimization.

Promotion verification: the isolated scoped tree passes 821 host tests, a clean
parallel default build (`boot all panic-probe placement-check`), and default → 0
→ default switching without cleaning. The default disks match the archived
qualified images byte-for-byte; the explicit fallback matches the prior disks.
No new emulator or exhaustive hardware claim is implied by these build checks.
