# Private bounded repaint frontend

Issue #14, 2026-09-29. This is host-tested manager-context C code and full-link
budget evidence. **It is not wired into the real manager's poll/lifecycle, not
an installed service, and not a new disk or input-latency qualification.**
Normal boot images and public application ABI remain unchanged.

## What the frontend actually does

`bench/window-repaint-frontend/frontend.inc` adds two private entry points to
the compact-manager sizing source:

- Control sends INIT, REQUEST, CHANGED or ABORT to the banked lane. REQUEST
  queues damage without revoking current work; CHANGED must succeed **before**
  scene/table/content/lifetime edits. A deferred or rejected fence does not
  authorize the edit. ABORT discards work only on whole-surface retirement.
  INIT is only valid for a fresh/quiesced lifetime with no outstanding work.
- Poll reconstructs current visible views from the actual manager table,
  preserving sparse handles and current rank rather than storing a pointer or
  old view between polls. Geometry checks avoid 16-bit wrap before publication.
  It issues one PEEK, copies the returned work into caller-owned local storage,
  and performs at most one qualified manager-owned raster step.

CLIENT is explicitly delegated with an unacknowledged receipt. Repeating a poll
offers the same work, rather than running/replaying a legacy painter or claiming
the whole callback is bounded. No retained flag is published until a real
cache-provider continuation is integrated. The existing old manager/cache paths
remain present only for conservative sizing and independent reference tests.

The frontend returns a private DEFERRED status without publishing or drawing
when its caller does not assert lease value 1, graphics is inactive, cache
admission is not exactly `$80`, or cache phase is neither EMPTY nor READY.
This rejects capture, paste, frontend repair-busy `$82` and unknown phases.
Polling also defers while dragging; control may still fence/cancel that job.
The lease argument is a **trusted caller assertion**, not an implemented lock or
proof that the repaint module was admitted. Cache acceptance only establishes
the existing cache's readiness. Production repaint admission, app-paint/nested
call/teardown ownership, flag storage and all call sites remain to be built.

Deferrals leave packet, lane, output, clip and pixels untouched. Invalid geometry
can overwrite some view-packing scratch but does not call the policy or alter
job/output/pixels/clip. Successful bank calls may overwrite common RPC scratch;
work must be local, never an alias into that packet. No callback, scheduler,
service poll or Z80 handoff occurs during a bank lease or raster step.

## Budget with actual frontend code

| Added frontend function | CODE bytes |
| --- | ---: |
| Resource/lease deferral gate | 48 |
| Request/fence/abort/init control | 98 |
| View packing and one-step poll | 440 |
| Added frontend total | **586** |

Sequential view-pointer packing uses compiler-managed register locals and avoids
pulling in a multiply-by-nine helper. No persistent frontend state is allocated:
the compact table/drag state remains 76 bytes and row scratch 12, matching the
original manager's 88 bytes. Admission/paint-lease storage is **not** silently
borrowed from these bytes or the common packet.

Both complete normal and panic links retain the same 72-byte newly linked
helper closure as the preceding raster experiment, without new DATA/BSS/ZP
allocation. The manager object is 8,719 CODE bytes; conservative full-link CODE
growth is 1,240 bytes while legacy synchronous composition is retained. All
fixed segment ranges and HIGHBSS (298 bytes) stay unchanged; RODATA/DATA/BSS and
shadow sizes stay unchanged. These sizing links move the shadow and have stale
import bridges: **unbootable, never package them**.

The measured component total is now **2,599 bytes**, against the prior optimistic
2,113-byte retired-body/reserve allowance: **at least 486 bytes short**. This still
excludes call-site migration, repaint admission/delivery, NMI cleanup, busy/
teardown and real client/cache providers. The preceding 100-byte figure was
only headroom for drawing/receipts, not available space for a complete adapter.

Four older functions occupy a further 722 bytes: damage-set 87, damage-add 163,
intersection 316 and cache-paint-image 156. They are **not counted as reclaimed**:
real drag/cache/callback paths still use them and their replacements have costs.
Their possible retirement guides the next replacement experiment; it does not
prove fit or justify deleting compatibility paths now.

## Qualification and reproduction

Host tests use the real manager table, C bank dispatcher/lane, receipt wrappers
and compact row/backend. They check two overlapping windows with sparse handles
and ranks out of slot order, full shadow/display canvases against old full-window
composition, four-row clear/one-row chrome/one-page commit counts, no implicit
legacy callback, repeated delegated work and deliberate packet clobbering after
the work is copied locally. Clients and page copying remain diagnostic models.

Additional tests cover hidden windows/four slots, pending-only requests preserving
live work, fences before poisoned-title/slot retirement, invalid/wrapping geometry,
epoch exhaustion, whole-surface abort and atomic resource/lease deferrals.
Compiler-object and both whole-link measurements charge helper/state changes;
evidence tests verify exact source/provider/library/map hashes and arithmetic.
**No new native/emulator run qualifies this frontend**, nor NMI/RESTORE, live
apps, task paging, production delivery or hardware behavior. Prior native raster
evidence remains valid only for its recorded scope.

From the reference container:

```
make repaint-frontend
```

To preserve a new measurement (refuses overwrite):

```
python3 tools/window_repaint_frontend.py --preserve
```

Evidence: `bench/{artifacts,results}/2026-09-29-repaint-frontend`. Every split
output is isolated; normal provider binaries are never replaced by sizing links.

## Next gate

Replace the real damage/clip/cache-composition call sites one family at a time,
first proving that superseded helpers can actually retire without breaking drag,
overlap, app painting or close/slot reuse. Measure all new call sites and complete
helper closure; recover or explicitly relocate more service code if needed.
Then implement checksummed repaint delivery/admission, serialized private-stack/
gateway ownership and common-NMI drainage in the restored kernel map. Neither
`SEI` nor the lease argument qualifies NMI safety. Live poll/providers and a
visible disk follow only after these placement/interlock gates pass.
