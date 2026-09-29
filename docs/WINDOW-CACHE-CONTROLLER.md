# Direct bank-1 cache continuation — 2026-09-28

Status: standalone C controller qualified in VICE 3.10 and 1986. **Not delivered
to the normal kernel and not enabled for GUI moves.** This is a correctness/
placement checkpoint, not a user-visible drag-speed improvement or hardware
qualification.

The continuation calls the C row service directly under one outer private
runtime lease. It never calls back through the resident gateway (which would
reset its own live C software stack), polls a service, yields, or invokes an
application. STEP validates the original window/content-generation ticket
before modifying the shared request and performs at most one synchronous row.

## Complete measured closure

The initial generic in-bank flow plus dispatcher did not fit the proposed
code area: CODE alone overflowed by 202 bytes. A single-owner fixed-address C
specialization reduces flow CODE from 994 to 637; both versions share the
same policy and exhaustive host contract tests. This private specialization
requires the caller to pass the module's own flow address; it is not a new
application ABI or a general arbitrary-flow API.

The resulting full image, including cc65 helpers, dispatch and unchanged
213-byte row core, is **3,977 bytes**:

| Bank-1 allocation | Range | Bytes |
| --- | --- | ---: |
| Linked module/core/helpers | `$4200–$5188` | 3,977 |
| Reserved code slack | `$5189–$521F` | 151 |
| Lease + row + flow | `$5220–$5239` | 26 |
| State guard | `$523A–$524F` | 22 |
| Private C stack | `$5250–$533F` | 240 |
| Stack top guard | `$5340–$534F` | 16 |
| Packed image | `$5350–$5BFF` | 2,224 |

The default 168×104 image needs 2,184 bytes, leaving 40. Oversized windows
remain a redraw fallback. The C stack is not reduced; it crosses a page and
the actual gateway, uploader and guard scanner are qualified for that layout.
Lowest observed changed stack offset is `$CC` (address `$531C`); that observation
is not a proof of maximum depth for future code.

The common gateway remains 217 bytes; its resident source/copy binding remains
241. Bank-0 padding is still 502, so this leaves **261 before actual manager
hooks, locks, marshalling and delivery validation**. Those are not yet linked;
do not claim a complete integration fit. USH stacks, app slots, VIC screen/
bitmap, common gateways, scheduler reservations and bootfs content are untouched.

## Private diagnostic protocol 0.1

The fixed dispatcher is `$42D5`. OP `$F790`: 0 init, 1 invalidate-all,
2 capture, 3 paste, 4 step; other operations reject. Window handle is `$F792`,
content ticket `$F793–$F794`, explicit eligibility `$F795`, geometry `$F7A1–$F7A6`.
Result `$F79C` is policy OK/INVALID/BUSY (0/1/2); successful calls publish phase
at `$F791` and the current ticket at `$F793–$F794`. The outer gateway reports
the returned private SP at `$F79D–$F79E`. This protocol is diagnostic/private,
not the earlier raw-command protocol: phase tags no longer occupy RESULT.

INIT is boot-only. Capture/paste select the module's current content epoch;
STEP must present the original ticket. Tickets are not per-paste nonces:
repeated same-generation pastes are intentional. Invalidating clears backend
ownership before advancing the nonzero epoch, including wrap. Calls must be
serialized; no queued or reentrant continuations. Rejected stale/wrong-owner
STEP leaves the request ticket/owner and persistent state unchanged. Other
backend rejection paths do not promise preservation of every request scratch
field; callers consume outputs only on success.

## Qualification

| Run | Alignment rows / calls | Capture + two paste rows / calls |
| --- | --- | --- |
| 1986 | 132 / 476 | 312 / 333 |
| VICE 3.10 | 132 / 476 | 312 / 333 |

The alignment suite includes all 8×8 source/destination alignments, full-width
and bottom-right pixels. The repeated-paste suite destroys the source bitmap
after capture, then pastes twice without recomputation or recapture. Independent
host oracles compare all 8,000 pixels and 32 dirty-page bytes. Host tests run
the actual fixed dispatcher, flow, command and policy, verify one row per STEP,
stale/cross-owner rejection, cancellation, repeated pastes and generation wrap.
The generic and fixed flow also share exhaustive unexpected-response tests.

All 26 published cc65 ZP bytes, caller/worker software stacks, hardware stack,
I/D flag combinations, MMU restoration and guards are checked. Sustained CIA2
NMI reaches both kernel and worker-flat profiles and drains exactly:
alignment 1986 8,906/128 worker, VICE 8,785/147; repeated 15,194/104 and
15,096/109. These counters are stress coverage, not performance measurements.
Physical RESTORE/Z80 NMI routing remains unqualified.

Four exact live one-byte mutations prove sensitivity: dropped SEI, shifted ZP
restore, private stack redirected into live bank-1 USH memory, and NMI pending
STA replaced by BIT. Each fails the positive decoder while preserving the
pixel oracle. Repair after ZP observation is diagnostic-only, never in the
resident binding. The NMI observer/IRQ at `$FF20`/`$FF80` are standalone only;
those addresses are not available to production code.

Exact sources, generated assembly, linked maps, PRGs, build/report hashes,
emulator provenance and all raw records are preserved in
`bench/{artifacts,results}/2026-09-28-window-cache-controller`.

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_controller.py build
distrobox enter my-distrobox -- python3 tools/window_cache_controller.py run --engine 1986
python3 tools/window_cache_controller.py run --engine vice
python3 tools/window_cache_controller.py preserve
```

Preserve refuses to overwrite evidence and binds both runs to exact executable
and input hashes. ca65 searches a source's directory before `-I`; template
gateway/core sources are copied into the work directory so the old layout
cannot silently supersede the controller layout. The build checks C/assembly
address agreement and byte equality of the qualified row core.

## Next gate

Whole-module cold-boot/lifetime delivery now passes in separate experimental
disks; see [WINDOW-CACHE-CONTROLLER-DELIVERY.md](WINDOW-CACHE-CONTROLLER-DELIVERY.md).
Those disks do not invoke the controller and normal disks remain unchanged.

Measure the full normal/panic integration: runtime acceptance of this module and
bounded resident hooks must fit without moving frozen primary allocations or
stealing live memory. Capture requires explicit completion and frozen source
geometry through READY; paste requires a frozen destination through READY.
Invalidate before pixel damage/repaint, clock overlap, resize, restack,
destroy/reuse, cancellation or graphics shutdown, with ordinary redraw fallback.
Then repeat live input/task/Z80/drag/cancellation/bitmap gates before enabling
GUI caching. No new manual test is needed for this intermediate build.
