# Bounded repaint caller and provider gate

Issue #14, 2026-09-29. This is a source-locked audit and isolated cc65
measurement, **not a linked manager or a bootable disk**. No public ABI or
application code was changed.

## What the real manager currently assumes

The selected manager has ten synchronous calls to `compose_damage`, seven
`damage_set` and two `damage_add` calls, two `cache_paint_image` calls and two
direct `window->paint(handle)` calls. The public painter type is `void`; there
is no progress result or continuation cursor. One callback occurs in normal
damage composition, the other in a clipped/fully hidden repaint path. `xwave`'s
callback loops over its plotted prefix; its separate foreground poll is bounded
to four vertices, but that does **not** bound the callback. `xclock` likewise
has a full `void` painter. The current public window result set is OK, INVALID
and FULL—no explicit deferred/retry result.

Create publishes window fields before synchronous composition and returns a
handle afterwards. Destroy saves damage, retires the slot, recomposes and then
calls the close callback. Drag release changes geometry and recomposes before
returning; repaint can recompose and invoke a painter before returning. These
orderings are the compatibility contract to review, not evidence that simply
queueing a paint after each call preserves behavior. In particular, rejecting
a destroy as generic INVALID when the repaint lease is busy could strand app
cleanup; calling the old painter on the next poll would still block input.

The audit deliberately locks these call counts and representative ordering
seams to the actual source. A source change fails qualification until the graph
is reviewed. It does not prove all paths safe, perform call-site rewriting, or
measure elapsed time.

## Measured first adapter cost

`bench/window-repaint-callers/control.c` is a private, uninstalled entry that
converts the manager's existing six-byte damage box into a lane rect and calls
the already-measured frontend control. cc65 emits **78 CODE bytes**, with no
RODATA, DATA, BSS, HIGHBSS or ZP. Both complete normal/panic isolated links
grow by exactly 78 versus the geometry checkpoint, pull no new library helper,
and leave fixed ranges and state sizes unchanged. Their growth over the
accepted kernel is 1,009 bytes (931 + 78). Because the earlier component was
2,371 against a geometry-adjusted allowance of 2,194, the measured minimum
deficit is now **255 bytes, before one actual call site**. No admission/lease,
provider, delivery, NMI, error/retry, busy or teardown cost is included.

This adapter only samples old damage globals. It does **not** itself establish
that a snapshot is the correct pre-edit union, own a graphics lease, fence a
mutation, or route a client. The actual window table and boot images remain
unchanged. Isolated sizing links are UNBOOTABLE (moved shadow/stale bridges) and
must not be packaged.

## Next design gate

Before inserting a real caller, specify and host-test:

1. An explicit bounded client-step provider with ticket/clip validation,
   `MORE`/`DONE` progress, and no callback spanning a bank lease. Migrate
   `xclock` and `xwave` painting separately; the manager owns the common
   provider contract, not xwave's plotting optimization.
2. A pre-edit scene fence for create, destroy, drag release, restack, repaint,
   begin-paint/image-complete and cache lifetime changes. If a lease conflicts,
   cancellation or deferral needs a defined bounded and retryable result—not a
   silent mutation or a generic INVALID return that existing callers drop.
3. Separate live admission/paint ownership from cache readiness. Validate and
   release clip, busy state and leases on normal, failure and NMI/RESTORE paths.
   `SEI` alone does not cover NMI. Account every caller/provider byte in
   normal and panic links before producing a visible disk.

## Private client-step experiment

`bench/window-repaint-provider/provider.{h,c}` and
`tests/test_repaint_provider.py` define a **host-tested, compile-only** fixed
dispatcher seam. It validates a live lane ticket, selected handle/rank,
visibility, clip bounds and row cursor before calling a pure admission check.
Admission may defer with no clip, pixels or lane acknowledgement. On admission
it sets the clip, draws exactly one row through an explicitly stepwise provider,
resets the clip, and acknowledges `MORE` or `DONE`. The host test verifies 83
row advances, order `validate → ready → clip → draw → reset → ack`, stale and
malformed rejection, no mutation on defer, and withdrawal after a scene change.

The fixed dispatch was chosen after measuring a generic callback-table version
at **1,396 CODE bytes**. The fixed version still compiles to **1,124 CODE
bytes**, no object-owned state, using the project's `-Oirs` cc65 options.
These are standalone object sizes, not linked incremental costs. The previous
normal/panic isolated links were already at least 255 bytes short; therefore
this C implementation is a contract/proof, **not a resident placement
candidate**. A smaller shared/assembly dispatch or an alternate banked
placement needs a complete normal/panic link measurement before integration.

The contract does not turn the current `void` xclock/xwave painters into
bounded providers. It also does not establish a safe UDEX task/app bridge,
hold scene/graphics ownership, or cover NMI/RESTORE between drawing and ack.
Those are explicit remaining gates. No boot image or public API changed.

Evidence under `bench/{artifacts,results}/2026-09-29-repaint-callers` includes
the exact source, cc65 listing/object, full isolated links, provider library,
input/build SHA-256 bindings and the audit report. `make repaint-callers` in
the reference container reproduces it; preservation refuses overwrite. No
new emulator or hardware run qualifies this *uninstalled* marshaller.
