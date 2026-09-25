# `xclock` analog clock application

`xclock` is the first application on the UDEKS VIC-IIe graphical environment.
It established the managed-window path before the later dual-engine `xwave`
computation demonstration.

The visual and lifecycle reference is GEOBENCH's analog Clock application:

- a framed, movable graphical window;
- a circular segmented rim and twelve hour marks;
- hour and minute hands, with an optional seconds hand;
- a small digital readout;
- bounded managed updates that repaint the clock and preserve occluding
  windows;
- complete repaint after damage, move, or reveal.

Its geometry is derived from a 60-entry fixed-point sine/cosine table, and
every line is clipped to its managed client area. After a resize, the face
radius is recomputed from both available width and height; the rim, hour marks,
and hands expand or contract together while the compact digital readout keeps
a stable legible font size. It uses window, display, and time service APIs
rather than direct pointer, VIC-IIe, CIA, or SID access.

The default managed window is 72x77 pixels and can be dragged by its title bar
or resized from its lower-right grip with the port-1 mouse button or port-2
joystick fire. During either operation its contents disappear and only an 8502
assembly-blitted outline follows the pointer; one geometry-aware repaint occurs
on release. Its close box, `xclock -q`, or
VDC-console `Ctrl+C` terminates it. `xclock` starts VIC graphics automatically
when needed. The shell remains responsive on the independent VDC display.

Rendering is prepared in an aligned 8 KiB bank-0 shadow bitmap. Pixel, line,
rectangle, and fill operations mark dirty 256-byte pages; a common-RAM gateway
copies only those pages into the bank-1 VIC bitmap. The final page copy stops
at `$7F3F`, preserving the pointer sprite at `$7FC0`. The default `HH:MM`
clock requests one managed damage repaint per minute. This costs more than an
isolated incremental hand update, but allows the compositor to reconstruct the
clock and every intersecting higher window in correct z-order. A move uses the
same managed repaint after its outline is released.

`xclock` is deliberately an 8502-owned application. A clock tick is a small,
bounded interactive update, so handing it to the Z80 would cost more than it
saves. `xwave` remains the first application intended to demonstrate measured
Z80 computation with 8502 plotting.

`xclock` is a standalone UDEX image in bootfs. A small resident managed-app
service loads it into the `$0200-$0BFF` slot on first invocation and calls its
fixed lifecycle entry table thereafter. Its implementation and private state
are no longer linked into the resident kernel image.

## Delivery gates

- [x] Add bounded VIC-IIe pixel, line, rectangle, and fill primitives.
- [x] Add a CIA TOD service suitable for clock applications.
- [x] Create, move, resize, and close a graphical window.
- [x] Route normalized pointer motion and buttons to the window manager.
- [x] Draw the face, hour/minute hands, and digital readout.
- [x] Add bounded, overlap-safe managed clock repaint.
- [x] Scale the analog face and hands to the resized client area.
- [ ] Add an optional seconds hand and per-second readout.
- [x] Support VDC `Ctrl+C`, `xclock -q`, and graphical close-box termination.
- [x] Verify timekeeping, repaint, and command lifecycle in 1986.
- [ ] Verify pointer dragging and close-box input in 1986 and VICE.
- [ ] Verify timekeeping, repaint, input, and cleanup on real
  hardware.
