# Private synchronous repaint admission

Issue #14, 2026-09-29. This is a host/cc65 **prototype**, not a linked
manager, UAPP ABI revision or bootable performance change.

The private admission byte has FREE/EDIT/RASTER/CLIENT/CACHE owners. A
same-owner or different-owner nested acquisition returns a distinct DEFERRED
result without changing ownership. Wrong-owner or duplicate release is
rejected. `repaint_edit_begin` acquires EDIT, validates/fences old/new damage,
and **retains** admission on success; the caller edits synchronously before
`repaint_edit_end`. Every failed begin releases. A defer during raster work
leaves both the scene and lane unchanged. The host harness checks these paths,
re-entry, NMI-pending interposition, exhaustion and release ordering. It also
source-locks the installed 8502 NMI stub to its record-only instructions.

This is a short, non-yielding call-frame contract, **not** a task lease with
reacquisition tokens. It does not allow a task switch, callback-retained
ownership, or an app's `begin_paint`/`end_paint` pair to hold this byte across
worker work. One raster step must release RASTER before a separate CLIENT
step; otherwise the client is correctly deferred. The NMI source test shows
only that the installed stub cannot enter the manager. IRQ/other entry paths,
actual storage placement and every exit path still need a live integration
audit; no general NMI-safety claim follows from the host model.

Using cc65 `-Oirs`, standalone objects measure:

| Prototype object | CODE | State |
| --- | ---: | ---: |
| Admission try/release | 79 | 1 HIGHBSS byte |
| Paired edit begin/end | 80 | 0 |
| Validating edit fence | 495 | 0 |
| Trusted-bounds fence alternative | 298 | 0 |

The trusted alternative matches the validating reference for 1,800 valid
old/new/availability cases against the real lane. It deliberately omits
per-input bounds validation and is **not approved for real callers**. In
particular, the current `udeks_window_create` tests `x + width > 320`; on the
target's 16-bit `unsigned int`, an overflowing sum may pass. Caller geometry
must be corrected and audited before trusting it. A better eventual route may
reuse the existing measured ASM `damage_set`/`damage_add` and 78-byte control
marshaller rather than install a second rectangle-union body. Neither route
has a complete normal/panic link or live app bridge yet.

The previous candidate was already at least 255 resident bytes short before
admission, callers or a provider. These standalone sizes cannot be booked as
exact incremental link costs. No public retry status exists: create returns
handle/zero; other operations have OK/INVALID/FULL. A busy destroy cannot be
silently mapped to INVALID, and `xclock`/`xwave` stop paths currently translate
non-OK into NOT_READY. The app-visible retry/versioning decision and all
call-site migrations remain open. No production image or manual test changed.
