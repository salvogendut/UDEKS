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
per-input bounds validation and is **not approved for real callers**. Both
manager variants now reject 16-bit-wrapping create coordinates with
`x > 320 || width > 320 - x`; host tests exercise the real create paths and
the normal/panic production links retain their frozen layout. This fixes
one caller, not the whole geometry/admission audit. The production D71/D64
integration probes pass in 1986 and host VICE Flatpak.

`transaction_damage.c` is a second private candidate. It uses the manager's
existing ASM `damage_set`/`damage_add` box and the previously measured
78-byte control marshaller, so it adds no second rectangle-union body. A host
test checks deferred/no-change, successful retained ownership, invalid
damage and exhausted-lane release. Its cc65 object is 51 CODE bytes; together
with the admission object, the complete isolated normal/panic links add
130 CODE bytes and one HIGHBSS byte. **Both strict links reject that byte**:
HIGHBSS already ends at `$E2E1`, while `$E2E2` belongs to selected-task cc65
context. `tools/window_repaint_admission_link.py` reproduces the rejection
and uses an explicitly `UNBOOTABLE-sizing.cfg` to measure CODE closure only.
The optimistic resident deficit rises from 255 to **385 bytes**, still before
actual call sites, provider or delivery. The sizing image is never a disk or
placement proposal.

A separate `REPAINT_ADMISSION_BANK0_BSS` build puts the owner byte in resident
bank-0 BSS instead. Both **strict** normal/panic links then pass: +130 CODE,
+1 BSS, no HIGHBSS growth, and the 8,000-byte VIC shadow starts one byte
later than the corresponding sizing link (`$A654`). This resolves the *single
state byte's* placement without borrowing `$E2E2` or changing the owner
algorithm. Its lifetime condition is narrow: every try/release and caller edit
must execute with bank 0 mapped; the existing binding masks IRQ during its
banked policy call and restores the map before return, and the installed NMI
stub only records a flag. Other IRQ/re-entry paths and all real call sites
still require an audit. These isolated links remain UNBOOTABLE because the
repaint candidate has moved shadow/stale delivery bindings and the 385-byte
optimistic CODE deficit. No live admission or performance claim follows.

No public retry status exists: create returns
handle/zero; other operations have OK/INVALID/FULL. A busy destroy cannot be
silently mapped to INVALID, and `xclock`/`xwave` stop paths currently translate
non-OK into NOT_READY. The app-visible retry/versioning decision and all
call-site migrations remain open. No production image or manual test changed.
