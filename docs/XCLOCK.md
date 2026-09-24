# `xclock` analog clock application

`xclock` will be the first application on the UDEKS VIC-IIe graphical
environment. It replaces `xwave` as the initial application milestone;
`xwave` remains planned as the later dual-engine computation demonstration.

The visual and lifecycle reference is GEOBENCH's analog Clock application:

- a framed, movable graphical window;
- a circular segmented rim and twelve hour marks;
- hour and minute hands, with an optional seconds hand;
- a small digital readout;
- bounded updates that erase and redraw only the old and new hands;
- complete repaint after damage, move, or reveal.

The first UDEKS edition uses a fixed-size window while the general window
manager is still being established. Its geometry is derived from a 60-entry
fixed-point sine/cosine table, and every line is clipped to its managed client
area. It uses window, display, and time service APIs rather than direct pointer,
VIC-IIe, CIA, or SID access.

The current compact managed window is 72x77 pixels and can be dragged by its title
bar with the port-1 mouse button or port-2 joystick fire. During a drag its
contents disappear and only an 8502 assembly-blitted outline follows the pointer;
one complete repaint occurs on release. Its close box, `xclock -q`, or
VDC-console `Ctrl+C` terminates it. `xclock` starts VIC graphics automatically
when needed. The shell remains responsive on the independent VDC display.

Rendering is prepared in an aligned 8 KiB bank-0 shadow bitmap. Pixel, line,
rectangle, and fill operations mark dirty 256-byte pages; a common-RAM gateway
copies only those pages into the bank-1 VIC bitmap. The final page copy stops
at `$7F3F`, preserving the pointer sprite at `$7FC0`. Clock ticks erase and
redraw only the old/new hour and minute hands and digital digits before
committing their dirty pages. The default `HH:MM` clock refreshes once per
minute, matching GEOBENCH's responsive default. A move performs a complete
off-screen repaint followed by a page commit.

`xclock` is deliberately an 8502-owned application. A clock tick is a small,
bounded interactive update, so handing it to the Z80 would cost more than it
saves. `xwave` remains the first application intended to demonstrate measured
Z80 computation with 8502 plotting.

For the static bootstrap image, `xclock` has its own class-10 lifecycle adapter
so the service registry can poll it independently. This is not a claim that an
application belongs in the microkernel: the task loader will replace the
adapter once application scheduling exists.

## Delivery gates

- [x] Add bounded VIC-IIe pixel, line, rectangle, and fill primitives.
- [x] Add a CIA TOD service suitable for clock applications.
- [x] Create, move, and close one fixed-size graphical window.
- [x] Route normalized pointer motion and buttons to the window manager.
- [x] Draw the face, hour/minute hands, and digital readout.
- [x] Add bounded incremental hand repaint.
- [ ] Add an optional seconds hand and per-second readout.
- [x] Support VDC `Ctrl+C`, `xclock -q`, and graphical close-box termination.
- [x] Verify timekeeping, repaint, and command lifecycle in 1986.
- [ ] Verify pointer dragging and close-box input in 1986 and VICE.
- [ ] Verify timekeeping, repaint, input, and cleanup on real
  hardware.
