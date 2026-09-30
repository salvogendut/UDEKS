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

Every current application window is resizable. Two diagonal marks in its
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
