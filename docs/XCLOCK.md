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

The first UDEKS edition may use a fixed-size window while the general window
manager is still being established. Its geometry will be derived from a
60-entry fixed-point sine/cosine table, and every line will be clipped to the
client rectangle. The application must use display, pointer, time, and window
service APIs rather than direct VIC-IIe, CIA, or SID access.

`xclock` is deliberately an 8502-owned application. A clock tick is a small,
bounded interactive update, so handing it to the Z80 would cost more than it
saves. `xwave` remains the first application intended to demonstrate measured
Z80 computation with 8502 plotting.

## Delivery gates

- [ ] Add clipped VIC-IIe pixel and line primitives.
- [ ] Add a monotonic/wall-clock service suitable for clock applications.
- [ ] Create, move, damage, raise, and close one graphical window.
- [ ] Route normalized pointer motion and buttons to the window manager.
- [ ] Draw the face, hour/minute hands, and digital readout.
- [ ] Add the seconds-hand option and bounded incremental hand repaint.
- [ ] Support VDC `Ctrl+C` termination and graphical close-button termination.
- [ ] Verify timekeeping, repaint, input, and cleanup in 1986, VICE, and real
  hardware.
