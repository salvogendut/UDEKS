# Private pre-edit repaint fence

Issue #14, 2026-09-29. `bench/window-repaint-edit/fence.{h,c}` is a
host-tested, cc65-compiled *contract experiment*, not linked into UDEKS and
not a public window/UAPP status code. The normal/panic images are unchanged.

`repaint_edit_fence(available, old, new)` validates the pre- and proposed
post-edit half-open rectangles. If admission is unavailable, it returns a
distinct retry result without changing the lane or scene. If admitted, it
unites old/new bounds and calls `udeks_lane_changed` **before** the caller
edits the window table, cache eligibility or content. The lane itself unites
that rectangle with active and pending repair and invalidates the old ticket.
Only an OK result authorizes the edit. Exhaustion closes the lane; it does not
authorize an edit. The host test uses the real lane to prove create, drag and
destroy order, deferred/no-mutation behavior, old-ticket withdrawal, the
active/pending/old/new union, invalid inputs and fail-closed exhaustion.

The measured standalone cc65 `-Oirs` object is **495 CODE bytes**, no
RODATA/DATA/BSS/ZP. This is *not* an incremental full-link number. The earlier
candidate was already at least 255 bytes short before any caller; this C
wrapper is therefore a behavioral reference, not a placement solution.

## Caller migration obligations

| Current path | Earliest point needing admission/fence | On defer |
| --- | --- | --- |
| Create | Before publishing the slot, rank, focus or any pixels | Keep slot free; caller needs an explicit retry outcome distinct from full/invalid. |
| Destroy | Before retiring the slot, changing ranks, toggling a drag outline or calling `close` | Keep window and close callback intact; retrying `stop` cannot be silently lost. |
| Drag start and outline motion | Before erasing content, setting drag ownership or XORing the outline | Do not consume/lose the release; hold or retry the internal event. |
| Drag release/resize | Before outline removal and old/new geometry edit | Retain the release geometry and drag state until the edit is accepted. |
| Raise/focus | Before rank/focus publication | Retry the click without partially changing rank or focus. |
| Repaint/begin-paint | Before cache invalidation, image-complete flag change or client pixels | Do not report an accepted paint that never occurred. |
| Image complete/cache capture or paste | Before cache eligibility/ownership changes and retained-pixel transport | Treat cache readiness separately from scene/paint ownership. |
| Stop/reset | Before invalidating slots or surface pixels | Drain or abort all tickets under ownership; release clips and leases. |

The current public painter returns `void`; create returns a handle or zero;
other operations return only OK/INVALID/FULL. No published retry result exists.
Returning INVALID on a busy destroy could leave a client unable to clean up;
returning zero on a busy create conflates temporary contention with permanent
failure. An app-visible retry contract, versioning/compatibility and call-site
updates remain a design gate. The test does **not** resolve that ABI choice.

The `available` argument is a trusted test stand-in, **not** a lock. A real
implementation must acquire/release one serialized graphics/scene lease and
prove it against NMI/RESTORE; `SEI` alone is insufficient. The fence also
does not make a `void` painter bounded, safely invoke a UDEX application from
the resident service, or handle a failure after pixels but before ack. No
emulator or physical C128 test is useful for this uninstalled prototype.

The follow-up [admission prototype](WINDOW-REPAINT-ADMISSION.md) pairs this
fence with a short-lived owner byte, retaining EDIT ownership until the
actual mutation completes. Its smaller trusted-bounds alternative is only a
size comparison: current create geometry can overflow on a 16-bit target, so
it cannot replace validation without a caller fix/audit.
