# Bounded window-manager composition

Issue [#14](https://github.com/salvogendut/UDEKS/issues/14), branch
`graphics-bounded-repaint`; follows the default-cache integration in PR #13.
Status: baseline, host-tested continuation reference and measured state-reclaim
preparation, compact lane plus bounded row-backend prototype. Normal disks
unchanged; the bounded service adapter is not linked.

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

## Continuation reference (not production-linked)

`src/services/window/repaint_policy.c` and the private
`include/udeks/window_repaint.h` now implement a caller-owned job. No application
callback, app-slot address, cache pointer or hidden mutable state is retained.
The policy emits one work record; the driver resolves its handle and executes
one bounded operation, then acknowledges DONE or MORE.

```
pending damage → clear (≤4 rows/record) → windows in ascending rank → commit
                                        ├─ chrome → client steps
                                        └─ retained-image restore steps
```

Active and pending damage stay distinct. Repeated requests coalesce pending
damage without changing the current clip/cursor. A scene change unions active,
pending and old/new affected extents, withdraws the old job ticket, and restarts
composition. Changes to geometry, rank, visibility, content/cache eligibility,
destruction or handle reuse must use this operation before altering the scene;
ordinary queueing is not a structural-invalidation substitute. A retained flag
is a trusted driver's promise of an immutable, eligible image, not proof from
this policy that a cache lease exists.

Each work ticket contains generation, scene revision, stage, rank, handle and
cursor. Validation precedes drawing and acknowledgment validates again. No
yield is permitted between validation and the bounded raster operation. Replayed
or stale acknowledgments cannot advance the job. MORE advances the stage cursor;
the next stage cannot run until DONE. A title-only repair yields past an empty
client intersection without calling its painter. Empty/hidden scenes still clear
and commit. Abort discards work only when retiring the whole graphics surface;
closing one window must instead invalidate and repair the exposed region.

Generation/cursor exhaustion fails closed rather than wrapping to an old ticket.
Init/reset is valid only after all old records are quiesced; it is not a safe
way to reuse an exhausted live ticket namespace. This is a private reference
contract, not a frozen application ABI or a protection boundary for untrusted
clients. The real adapter must also reset shared clips/workspace between polls,
interlock ordinary app painting/image completion, and release busy/cache locks
on interruption. Those real-backend mechanisms are not implemented here.

Seventeen host tests compile the actual policy with strict warnings. They cover
atomic rejection/output preservation, pending unions, sorted/sparse ranks,
clipped opaque composition, retained restore, progress receipts, invalidation,
abort/exhaustion and complete 320×200 canvases. The incremental mock renderer
matches an independent full-scene reference after partial damage, queued work,
move/resize/restack and destroy/reuse during client/restore/commit. This is not
execution of the cc65 object or qualification of actual VIC/application painters.

The target budget gate is repeatable:

```
distrobox enter my-distrobox -- make repaint-policy
```

The actual cc65 object measures **4,643 CODE bytes**, with no own BSS/DATA/ZP.
Target sizeof probes report job **22**, ticket **9**, work record **15**, window
view **9** bytes. The caller also owns its scene views and backend continuation;
those temporary costs and any added runtime helpers must be charged on linkage.
The CODE number is a lower bound, not a closed linked footprint. Source/object/
assembly/dumps and toolchain/hash bindings are preserved under
`bench/{artifacts,results}/2026-09-29-repaint-policy`.

Directly adding this generic object is ruled out by the existing budget: HIGHBSS
is full and resident padding is only 20 bytes. Do not relocate the shadow or
consume guard/stack bytes to force it in. The next increment is a compact service
adapter that replaces existing compositor logic and has a separately measured
state/placement plan, checked against this reference before resident linkage.
The normal fallback and the public UAPP painter API remain unchanged.

## Compact adapter preparation: state reclaim

`tools/window_repaint_compact.py` constructs a private candidate from the selected
manager. It removes three redundant bytes per window: `active` (a live rank is
already nonzero), `surface` (create admits only bitmap windows), and `owner`
(the current private manager never reads it). The public create signature still
accepts owner and validates surface; this does not introduce ownership checking.
If future isolation needs a stored owner, account for it explicitly. The tool
rejects new owner/surface readers instead of silently stripping them.

Rank zero now retires a slot. Destroy saves its old rank first, repairs remaining
ranks, and invokes the close callback only after retirement. The live test in
`top_window` is deliberately retained: without it an empty table would focus a
free rank-zero slot when the active count is also zero.

Six host tests cover the actual old/candidate managers and budget-parser guards:
full retained-image
occlusion and partial-paste canvases, then sparse four-slot create/close/reuse,
move/resize/close while dragging, callback retirement and reset for all 256
owner bytes. Their pixels, diagnostics and callback counts agree. This tests
state compaction, not bounded composition or actual cc65 execution. The mock
painter uses caller identity rather than reaching into the removed private
owner field; real application painters have no such internal-field access.

Repeatable target measurement (reference container):

```
distrobox enter my-distrobox -- make repaint-compact
```

| Manager allocation | Selected baseline | Private compact candidate |
| --- | ---: | ---: |
| CODE | 7,762 | 7,645 |
| HIGHBSS | 88 | 76 |
| RODATA | 130 | 130 |

Both normal and panic whole-link replays prove **117 CODE + 12 HIGHBSS bytes**
reclaimed; the imported helpers and linked library module sizes are unchanged.
The total HIGHBSS end would move from `$E2E1` to `$E2D5`, making
`$E2D6-$E2E1` available. Combined with the existing 20-byte CODE reserve,
this is a prospective 137-byte code budget, not a delivery/placement approval.
The full 22-byte reference job is still ten bytes larger than this new state
space before any reuse/specialization. Do not claim its caller temporaries,
backend state, or app continuations are free.

The experiment inventories actual procedure sizes: selected draw-glyph/title/
chrome total 1,315 CODE bytes, and paint-window/compose-damage total 697.
These are replacement candidates, not wholly reclaimable bytes: their pixel,
cache and callback semantics must survive in the bounded adapter. The next
step is a compact continuation/state layout and bounded chrome/clear/commit
driver, checked against the reference. Any overlay with drag fields must first
prove its input/create/destroy lifetimes; none is assumed safe here.

Every split output is redirected into the private experiment; normal outputs
are untouched. Its kernel images are **UNBOOTABLE sizing artifacts**, not test
disks: the unpadded shadow moves to `$A16B` and derived private import bridges
have not been regenerated. Restore the frozen `$A1E0` shadow and prove all
bindings/state/clip/cache cancellation before any production candidate is run.
Evidence under `bench/{artifacts,results}/2026-09-29-repaint-compact` preserves
source, providers, target objects/listings, isolated normal/panic maps and hash
bindings, with two integrity tests. No latency improvement is claimed yet.

## Compact lane and bounded raster prototype

`src/services/window/repaint_lane.c` is a private, single-surface continuation.
It packs phase/pending and rank/handle, and uses one non-wrapping epoch to fence
both scene changes and new jobs. Unlike the generic reference it has no separate
caller revision: the manager must call `changed` **before every table/content/
cache-lifetime mutation**. Views are trusted, already-validated manager metadata,
not a new public scene parser. There are no stored pointers or callback addresses.
Do not expose this reduced contract as the public/generic reference ABI.

Target state is **18 bytes**: active rectangle 6, pending rectangle 6, epoch 2,
cursor 2, packed state/selector 2. Replacing the existing damage box and using
the recovered twelve bytes gives `76 - 6 + 18 = 88` manager state bytes, within
the current allocation. This is a replacement plan: old damage globals still
exist in the sizing translation unit. Caller views/work/backend continuations
and stack costs are additional. No drag/guard/cache-workspace overlap is used.
Target ticket/work/view sizes are 6/12/9. Init remains fresh/quiesced-lifetime
only; abort retires work, and epoch/cursor exhaustion fails closed, never wraps.

Seven host tests execute both actual policies and compare status, active/pending
extents, epoch, cursor, phase, rank, handle, clips and progress receipts. They
exercise queued damage, empty/hidden/title-only repairs, cancellation/reuse in
clear/chrome/client/restore/commit, invalid requests, exhaustion and 40 seeded
scene changes. The final full 320x200 mock canvases match an independent oracle.
The commit model follows VIC byte-interleaving, one page per record. These are
not execution/timing or NMI qualification of the cc65 object.

`bench/window-repaint-lane/chrome.inc` renders an opaque **single row** directly,
not the old full chrome routine under a small clip. It preserves both borders,
title bar and 3x5 glyphs, close button and resize strokes. One call uses at most
three one-row spans and 250 direct pixel calls, bounded by the 320-pixel width.
The pixel test compares the original drawing across narrow/full-width and
short/full-height windows, all flags, titles/case, edge positions and clips;
every generated primitive is restricted to the requested row. This proves
operation counts and pixels, not a target input-service deadline.

The private raster entry in `raster.inc` validates its receipt before drawing,
clears at most four rows, renders one chrome row, or copies at most one dirty
256-byte bitmap page. Successful steps reset shared clipping before ack.
Stale/rejected work leaves pixels, dirty map, clip and progress untouched; the
future poll driver owns cleanup on cancellation/error. CLIENT and RESTORE
return `BACKEND_REQUIRED` without running a legacy callback, touching a lease,
or acknowledging it. Their real bounded providers are still missing.

The actual C backend host test checks complete chrome/client pixels, all 32
modeled pages, clip cleanup, progress, stale work after a table/title replacement,
clean-page handling and client/restore delegation. Its client is a **bounded mock
row provider**, not xclock/xwave. No old callback is repeatedly clipped/replayed.
Two sizing guards and two evidence tests prevent omitted code or uncharged state.

```
distrobox enter my-distrobox -- make repaint-lane
```

Actual cc65 sizes: lane CODE **2,641**, own HIGHBSS **18**; chrome row **1,468**;
raster backend **1,175**. The sizing source keeps a 70-byte synchronous chrome
compatibility loop and all old call sites; it is not poll integration. The
compiler originally omitted the unused static raster entry. It is now an explicit
private exported bench symbol (no UAPP gate), and the gate requires both measured
functions in the actual object listing.

Even optimistically removing all five old glyph/title/chrome/paint/compose
bodies and spending the 137-byte reserve leaves **at least 3,171 CODE bytes**
short. Helpers, call-site replacement, legacy/cache adapters, admission and
teardown interlocks remain uncharged. State fit does **not** mean code fit.
Evidence is preserved under `bench/{artifacts,results}/2026-09-29-repaint-lane`.
No normal link, disk, UAPP entry or application changes; no new test disk yet.

The next placement spike is now qualified **in isolation**: the complete C
policy/dispatcher/helper link fits 3,286 bytes at proposed bank-1 `$D100`, with
18-byte bank-owned state and an 84-byte binding. Both 1986/VICE pass 1,415 calls
and reject zero-page/IRQ/private-stack fault controls. See
[WINDOW-REPAINT-BANK.md](WINDOW-REPAINT-BANK.md) for exact ranges/lifetimes and
limits. This does not install a service or qualify NMI/live apps/cold-boot delivery.
That first row/backend/binding draft exceeded the optimistic resident replacement
budget by at least 614 bytes before integration costs. The follow-up compact
raster now measures 2,013 bytes including real receipt wrappers, binding and new
linked helpers; granting retired bodies/reserve leaves 100 provisional bytes.
Both engines pass real C/ASM shadow pixels with banked receipts. This is still
only a component lower bound, not a full adapter fit: delivery/admission, real
painter/cache providers, poll/view packing and busy/teardown interlocks remain
uncharged. See [WINDOW-REPAINT-RASTER.md](WINDOW-REPAINT-RASTER.md).
Do not annex bootfs/task/USH/VIC regions, persist state in common scratch, or
silently move the frozen shadow. Normal disks remain unchanged.

The private frontend now reconstructs views from the actual manager table,
handles request/fence/abort control and performs at most one manager raster
step per poll. Host tests prove current sparse ranks/full canvases, atomic
resource deferral and unacknowledged client delegation. Actual added CODE is
586 with unchanged helper closure, so the component total is 2,599, at least
486 bytes above the current allowance before delivery/providers/call sites.
Possible legacy damage/clip/cache helpers are not credited as retired until
their real users are replaced and qualified. This is still not wired to the
production manager; no new emulator or test disk qualification follows.
See [WINDOW-REPAINT-FRONTEND.md](WINDOW-REPAINT-FRONTEND.md).

## Next increments and gates

1. Establish baseline input-service gaps, not just release totals or row counts.
2. Host-test a generic damage/composition continuation: union pending damage,
   order windows correctly, distinguish current work from new damage, and restart
   safely on geometry/stack changes, destruction/reuse, reset and cancellation.
   Do not retain a stale callback or pointer into a replaced app slot.
   Reference contract/tests are complete; this is not yet a resident adapter.
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
