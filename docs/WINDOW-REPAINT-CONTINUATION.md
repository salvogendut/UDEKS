# Bounded window-manager composition

Issue [#14](https://github.com/salvogendut/UDEKS/issues/14), branch
`graphics-bounded-repaint`; follows the default-cache integration in PR #13.
Status: baseline measurement and continuation design. Normal disks unchanged.

## Why another step is needed

Retained image paste already processes at most four rows per poll. But a drag
release calls `finish_drag → cache_paint_image → compose_damage` synchronously.
The compositor clears the damage, draws each intersecting window's chrome and
invokes its clipped painter before committing and returning to input polling.
The uncached release path and background repaint also use synchronous
composition. A fast drag start does not establish a responsive release.

The public painter is currently `void paint(handle)`: it has no budget,
continuation token or completion result. Moving that entire callback to the next
poll, or repeatedly replaying it under small clips, does not make it bounded.
An obscured client must not later draw through the top-window `begin_paint`
path: that would overwrite windows above it. Keep this distinction explicit.

## First increment: baseline observer

`tools/window_repaint_latency.py` extends the preserved, source-bound native
input harness. It loads the accepted default D64/D71, checks their exact hashes,
binds service entry PCs from the actual map, and uses read-only 1986 entry/return
breakpoints. It measures maximum continuous window-manager call duration and
maximum keyboard-entry gaps, including leading/trailing observation fragments.
Both use **emulated bus cycles**, including interrupts and CPU handoffs; neither
is wall-clock time or an assertion that an input event was handled by a deadline.

Cases cover the clock alone, clock over wave, and 16 retained wave moves. The
existing full-canvas assertions and subsequent Ctrl+C/console/shutdown checks
remain. This diagnostic is not a fresh full compositor/hardware qualification.
IRQ-before-entry redispatches are counted once using the live return frame and
registers; return matching checks SP. The observer resumes the same partial
machine frame after each debugger stop. It never changes OS code/state, input
queues, damage or ownership. Snapshots can contain owned ROMs and stay in build
output only; preserve raw pixels/logs/provenance, not ROM-bearing snapshots.

Run in the reference container (explicit emulator path also works from the
isolated worktree):

```
distrobox enter my-distrobox -- python3 tools/window_repaint_latency.py \
  --build-root /var/home/salvogendut/Dev/UDEKS \
  --emulator /var/home/salvogendut/Dev/1986
```

The baseline deliberately refuses changed disks. A later candidate observer
must carry its own source/build/provenance binding, rather than weaken this gate.

Measured baseline (both formats produce identical records):

| Case | Maximum keyboard-entry gap, bus cycles |
| --- | ---: |
| Clock alone | 941,873 |
| Retained wave moves, median of 16 per-move maxima | 1,228,648.5 |
| Clock dragged over wave | 5,862,866 |

The overlap case has one continuous manager call lasting 5,838,505 bus cycles.
At the harness's nominal PAL cadence (19,656 bus cycles/frame, 50 frames/s),
the keyboard gap is about six seconds. These are observed service-entry gaps,
not a measured keypress-to-command deadline, and not worst cases over all inputs.
They support fixing synchronous composition rather than tuning the row-paste
budget. Normal D64/D71 hashes are unchanged.

Source/runner/map/disk bindings, both logs, and emulator provenance are preserved
in `bench/{artifacts,results}/2026-09-29-window-repaint-baseline`. The decoder
requires all 18 cases and both services, rejects incomplete/duplicate records,
and keeps the settled pixel/input/shutdown and <=30-frame drag-start gates.
Seven new observer/evidence tests pass; the full scoped suite has 828 tests.

## Next increments and gates

1. Establish baseline input-service gaps, not just release totals or row counts.
2. Host-test a generic damage/composition continuation: union pending damage,
   order windows correctly, distinguish current work from new damage, and restart
   safely on geometry/stack changes, destruction/reuse, reset and cancellation.
   Do not retain a stale callback or pointer into a replaced app slot.
3. Split manager-owned clearing, chrome and commit into bounded stages. Measure
   code/state placement before linking: the current HIGHBSS is full and only
   20 resident padding bytes remain. Bank-1 availability is not automatically
   always-mapped state; account for every transport/continuation byte.
4. Qualify an optional generic bounded painter contract if needed. Preserve
   existing UAPP semantics until a versioned migration is evidenced. Old
   synchronous callbacks remain a compatibility limitation, not a bounded claim.
5. Compare both-format candidate service gaps and complete pixels in 1986/VICE;
   retain <=30-PAL-frame clock drag start, partial-paste cancellation, typing,
   pointer tracking, RESTORE/NMI, oversize resize, shutdown/restart and guards.
   Request a physical-machine check once a new visible candidate is ready.

Application projection/sample/render caches belong to xwave and remain outside
this work. The compositor owns damage, stacking, clipping and bounded scheduling;
the microkernel does not acquire display policy. Total repaint time can remain
long even when polling gaps improve; report those separately.
