# `xwave` dual-engine graphics demo

`xwave` is the first UDEKS application that makes the system's division of
labor visible. It opens a wireframe-style window on the VIC-IIe graphics
screen and plots a sine waveform inside it, inspired by the
small interactive function-plotter concept referenced during design. The
linked example page was unavailable during implementation, so this contract
records the requested behavior rather than depending on its code.

## Engine split

- The resident 8502 owns the application lifecycle, keyboard routing,
  VIC-IIe mode, window frame, clipping, axes, labels, and line rasterization.
- The Z80 computes batches of fixed-point function samples in C through the
  versioned mailbox worker.
- The 8502 validates each returned batch before plotting it. The application
  must remain correct if the Z80 is unavailable, with an 8502 computation
  fallback retained for qualification and comparison.
- Common-RAM diagnostics count Z80 batches, 8502 fallbacks, repaints, focus,
  and drag state so the collaboration is observable and testable.

The first implementation uses a 64-entry signed sine table, two phase units
per sample, 64 plotted samples, and one mailbox lease per full repaint. No
floating-point library is used. The identical table in the 8502 application
is the correctness and availability fallback.

The initial plot is deliberately static. An earlier once-per-second full
repaint could occupy the 1 MHz 8502 long enough for the next tick to arrive,
starving pointer and keyboard service. Future animation must retain computed
samples and rasterize a small bounded segment budget per cooperative poll; it
must not invoke another full compositor pass from the periodic application
poll.

## Foreground job and cancellation

Launching `xwave` makes it the foreground job while the VDC root console
remains the controlling terminal. Pressing `Ctrl+C` on that console produces
character `$03` through the existing normalized keyboard service and requests
termination.

The Z80 cannot be interrupted by the 8502 while it owns the C128 bus.
Computation is therefore divided into short, statically bounded leases.
`Ctrl+C` is observed between batches; the 8502 then stops submitting work,
retires any partial plot safely, releases application-owned VIC resources,
restores terminal focus, reports interruption, and emits a fresh shell prompt.

Appending a standalone `&` runs `xwave` in the background and immediately
returns a shell prompt. A foreground `xwave` retains terminal ownership even
if another graphical window is raised with the pointer.

## Delivery gates

- [x] Generalize the VIC-IIe surface into clipped pixel and line primitives.
- [x] Define a bank-aware shared sample-buffer lease.
- [x] Add one bounded Z80 fixed-point sample operation and an 8502 fallback.
- [x] Add foreground/background job control and `Ctrl+C` cancellation.
- [x] Draw a managed, resizable wireframe window, axes, and computed polyline.
- [ ] Verify identical samples, resizing, and bounded cancellation in `1986`, VICE, and
  real hardware.
