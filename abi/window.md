# VIC-IIe window manager / UAPP 0.4

The first UDEKS graphical window manager owns VIC-IIe bitmap-window policy.
Applications register bounded descriptors and repaint callbacks; they do not
draw borders, poll pointer hardware, hit-test title bars, or implement close
buttons themselves.

Each descriptor records a handle, owner, surface type, flags, geometry,
z-order, title, repaint callback, and close callback. The initial registry has
four static slots and performs no dynamic allocation. Version 0.3 admits
bitmap surfaces and supports four overlapping visible application windows.
Damage is cleared and recomposed through repaint callbacks from the lowest
intersecting window to the highest; no save-under buffer is allocated.

The manager draws the double-line frame, title bar, three-by-five title, and
optional close box. It establishes a client-area clip before invoking a
repaint callback. Incremental client drawing uses the same clip through the
bounded begin/end-paint calls only while the client is the top window. A
background client requests a managed repaint instead, allowing the compositor
to reconstruct its damage and every intersecting window above it in order.

Clicking an exposed part of a window focuses and raises it. Z values are kept
as the compact range 1 through the active-window count, so repeated switching
cannot wrap an ever-growing sequence number. Destroying a window recomposes
its old rectangle and focuses the remaining top window.

Resizable application windows show two diagonal marks in their
lower-right corner identify a ten-by-ten-pixel resize grip. Pressing the grip
hides the window contents and starts the same direct-to-VIC outline operation
used for movement. The outline is constrained to the 320x200 surface and a
48x48 minimum. Releasing the button commits the new width and height, then
recomposes the union of the old and new rectangles. Client paint callbacks
obtain the new geometry and remain clipped to the resized client area.

## Outline dragging

A press on a movable title bar begins an outline drag. The manager recomposes
the old rectangle without the dragged window, exposing any windows beneath,
then installs a one-pixel XOR outline. While the button remains held, only the
old and new outlines are transferred; the client callback is not invoked and
the window contents stay hidden. Releasing the button removes the outline,
commits the new descriptor geometry, and recomposes the union of the old and
new rectangles.

Outline motion calls the VIC graphics module's dedicated 8502 assembly
blitter. C prepares one compact 15-byte geometry record per outline. The
blitter enters physical bank 1 once, XORs the old and new outlines directly in
VIC bitmap RAM, and returns to bank 0; it does not copy dirty shadow pages and
does not alter the retained shadow surface. Its relocated common-RAM code is
cached across consecutive drag updates and invalidated by an ordinary bitmap
page commit. The 8502 retains window policy and final display ownership. Z80
leases remain reserved for large, bounded client computations rather than
latency-sensitive dragging.

The window manager is service class `9`, instance `0`, with its own start,
poll, and stop lifecycle. The VIC-IIe display service does not call its poll
routine or know about window clients.

## Client clicks and fixed-size windows (UAPP 0.4)

The manager routes each primary-button press edge to the topmost hit window.
Title dragging, close and resize gestures do not generate client clicks.
`udeks_window_take_click(handle)` consumes the pending event only for its
focused owner; wrong handles cannot consume it. Coordinates are relative to
the window origin, including the title height. A held button does not repeat.
The one-event mailbox retains a click until consumed or superseded by a new
press; destroy/reset invalidates it, including before handle reuse. Copy the
borrowed record before returning to the service loop. This is intentionally
a bounded click API, not a general event queue or focused keyboard routing.

`UDEKS_WINDOW_FLAG_FIXED_SIZE` (0x10) suppresses the resize grip and gestures.
Old clients without this flag retain their existing resizable behavior.
xcalc uses it for its initial 104x133 layout; dragging and close remain active.
The VDC console retains keyboard input, including foreground Ctrl+C.

## Explicit image completion (UAPP 0.3)

`udeks_window_image_complete(handle)` returns `OK` only for a live, visible,
topmost bitmap while no window is being dragged. It sets a private descriptor
flag, consumes no additional BSS, and may be repeated. The application, not
the manager, asserts that its whole image is finished. `end_paint()` alone
does not imply completion of an incremental renderer.

A successful `begin_paint` and any intersecting compositor repaint withdraw
completion before changing pixels. Creation masks application flags to the
four stored public bits (plus the fixed-size option) so clients cannot forge the private completion bit;
handle reuse, reset and closure discard the old descriptor. Newly raised,
previously obscured windows pass through damage repaint before eligibility.

The original increment published the completion seam only. Normal builds now
enable the bank-1 retained cache; application private state is not exposed.
Existing moved-window redraw remains the fallback.

## Diagnostic record

The 32-byte `WMGR` record begins at `$F240`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `WMGR` |
| 4 | 1 | Format (`1`) |
| 5 | 1 | Ready state (`2`) |
| 6 | 1 | Active descriptor count |
| 7 | 1 | Focused handle, or zero |
| 8 | 1 | Dragged handle, or zero |
| 9–10 | 2 | Current outline X |
| 11 | 1 | Current outline Y |
| 12 | 1 | Current outline width |
| 13 | 1 | Normalized action-button state |
| 14 | 1 | Registry capacity (`4`) |
| 15 | 1 | Capabilities: registry, z-order, clipping, outline drag, damage recomposition, resize grip (`$3f`) |
| 16–17 | 2 | Windows created |
| 18–19 | 2 | Windows destroyed |
| 20–21 | 2 | Window repaint callbacks invoked by composition |
| 22–23 | 2 | Outline movement updates |
| 24–25 | 2 | Drags started |
| 26–27 | 2 | Drags completed |
| 28–29 | 2 | Graphical close-box requests |
| 30–31 | 2 | Damage-composition passes |

## Banked clients (UTRQ 0.9)

Banked ordinary UDEX programs do not call UAPP's resident paint functions or
register foreign-bank callbacks. They submit operation 23 through the existing
`$FF16` request boundary: descriptor/flags zero, count 24. Unused payload bytes
are ignored; clients should clear them. Each registered task owns at most one
window. The service derives the task from the scheduler, binds owners `$83`–`$86`
to tasks 3–6, and copies titles into its own storage.

| Payload | Request | Successful result |
| --- | --- | --- |
| `1, x-lo, x-hi, y, width, height, flags, title[8]` | CREATE | Window handle in result byte |
| `2, handle, pointer-lo, pointer-hi, count` | PRESENT | Result 0 |
| `3, handle` | EVENT | Result 4, payload `state, x-lo, x-hi, y` |
| `4, handle` | CLOSE | Result 0 |

CREATE currently requires FIXED_SIZE (`$10`), with optional MOVABLE (`$02`)
and CLOSABLE (`$04`) only. Geometry passes the existing window-manager bounds
checks. Titles are eight bytes plus a private terminator. EVENT is nonblocking:
state 0 means closed, 1 alive/no click, 3 alive with a consumed client click.
Click coordinates are relative to the whole window. There is no keyboard or
resize event in 0.9; clients sleep/yield between polls. An already-closing owner
gets state 0, never another window's events.

### Geometry events (UTRQ 0.10)

All envelope fields and operation numbers stay unchanged. CREATE accepts
exactly one of FIXED_SIZE (`$10`) or RESIZABLE (`$08`), optionally combined with
MOVABLE/CLOSABLE. A 0.9 request still rejects RESIZABLE. No callbacks or foreign
code pointers are introduced. The existing manager's lower-right outline grip
commits a size only on release, constrained to the display and its 48×48 drag
minimum. CREATE uses the existing bounds; clients choose an appropriate initial
size. A resized window may be wider than 255 pixels.

EVENT input is `3, handle, last-width-lo, last-width-hi, last-height`, padded
to the usual 24 bytes. The client supplies the geometry it last rendered;
zero requests an initial size notification. The seven-byte reply is:

`state, click-x-lo, click-x-hi, click-y, width-lo, width-hi, height`

- `0`: closed; only state is valid.
- `1`: live, geometry unchanged, no click.
- `2`: live, dimensions differ from the client's acknowledgement.
- `3`: live, dimensions unchanged, one consumed client click.

Width/height are valid for every live response; click coordinates only for
state 3. Geometry delivery takes precedence without consuming a pending click.
Repeated polls with an old size repeat state 2; multiple intermediate resizes
coalesce to the current size. While a drag/resize outline is held, state 2 is
suppressed; applications continue with the last acknowledged size. Releasing
it exposes the committed size. Acknowledging it allows pending clicks through.
No extra resident queue or lost one-shot notification is required. Moves and
stacking alone do not generate a size change. Ownership checks precede either
geometry lookup or input consumption. The closing owner sees state 0 before
any lookup, and no freed window handle is dereferenced.

Applications recompute content themselves and PRESENT an updated retained
image. Until then the old image remains clipped to the new client rectangle.
The service does not implement clock scaling or any other app-specific model.
Old 0.9 executables retain their exact four-byte EVENT and fixed-size behavior.

PRESENT takes at most 160 eight-byte commands (1,280 bytes, matching the PATHS
budget) from **inside the caller's own image+BSS reservation**. Commands use
window-relative byte coordinates:

| Opcode | Remaining seven bytes | Meaning |
| --- | --- | --- |
| 0 | `x,y,width,height,color,unused,unused` | Filled rectangle |
| 1 | `x,y,x2,y2,color,unused,unused` | Line |
| 2 | `x,y,row0,row1,row2,row3,row4` | 3×5 glyph, doubled pixels; low three bits per row |
| 3–10 (UTRQ 0.13) | `x,y,row0,row1,row2,row3,row4` | 8×5 monochrome tile, MSB at left; integer scale is opcode minus 2 |

Tiles draw set bits in black and leave clear bits transparent. For example,
opcode 3 draws an 8×5 tile at 1×; opcode 10 draws it at 8× (64×40 pixels).
Coordinates are widened before scaling and clipped by the compositor, just
like glyphs. Clients clear the background with a preceding fill if needed.
Older request minors reject tile opcodes atomically with `EINVAL`; all prior
commands and event semantics are unchanged. This is a generic bitmap primitive,
not a sprite-editor service. Request payload bytes 5–23 remain reserved; 0.13
does **not** implement the experimental partial-damage payload.

Colors are black (0) or yellow (7). The complete list is validated before
commit; a rejected update leaves the old retained list and window unchanged.
The service copies commands into a packed 2,304-byte bank-0 pool at
`$1300-$1BFF` and repaints through the compositor's client/damage clip.
All four owners share that capacity. Replacing or closing an image compacts
the pool; an update exceeding the available capacity returns `ENOMEM`
without changing any owner's retained image. Sources must stay below the
caller's private stack page, even if the total allocation extends further.
Future moves, raises or partial uncovering replay that copy at the current
window origin, without running the client or trusting a client buffer again.
Zero commands clears the retained content. There is no cross-task begin/end
painting lease and no app-specific calculator renderer in the service.

### Packed retained paths (UTRQ 0.12)

GRAPHICS suboperation 5, `PATHS`, accepts
`5, handle, pointer-lo, pointer-hi, length-lo, length-hi` in the existing
24-byte payload. Descriptor and flags remain zero. The source range must be
entirely inside the caller's allocation. Length is an eight-byte multiple,
8–1,280 inclusive. The service validates the **entire** stream before copying
or repainting; any rejection preserves the prior image, length and window.
A 0.11-or-earlier request for PATHS returns `ENOSYS`; invalid length, stream,
pointer or ownership returns `EINVAL`. Result is zero on success.

Each path consists of:

1. Header: low seven bits are the point count (2–127); bit 7 is initial X bit 8.
2. Initial X low byte, followed by initial Y byte.
3. `count - 1` pairs of signed eight-bit X/Y deltas, joining consecutive points.

Every decoded point must be in X 0–319, Y 0–199. Points are window-relative;
painting still obeys the compositor's client/damage clip. Paths are black.
A zero header terminates the stream; **only zero to seven zero padding bytes**
may follow. Header `$80`, missing terminators, truncated paths, coordinate
overflow and nonzero/excess padding are invalid. Eight zero bytes represent
an empty image. Each new path has an absolute starting point, so paths can be
disconnected. PRESENT and PATHS replace each other; there is one retained image
per owner, not two simultaneous buffers.

After success the client may reuse its source buffer. Moves/raises replay the
service-owned copy with a new origin, without executing client code or leasing
the Z80. This is retained **geometry**, not a promise of a cached pixel blit or
constant-time repaint. The parser is synchronous and bounded by stream length;
further rendering-latency work remains separate. Projection, function sampling
and resize policy belong to the app, not the service or window manager.

Unknown suboperations, bad ranges/counts/flags and foreign handles are `EINVAL`;
CREATE failure is `ENOMEM`. Earlier request minors or a service not yet installed
are `ENOSYS`. Completion preserves the request sequence; clients must not depend
on unreturned payload bytes (used as transfer scratch).

Closing retires the window immediately, then the client observes EVENT=0 and
exits. The service retires any remaining window before reaping an exited task.
It never frees a live task. Root-session `xcalc -q`, `xdraw -q` and foreground Ctrl+C use
this same graceful close path. A noncooperating native program is not protected
or forcibly terminated by this interface; these are trusted cooperative apps.
