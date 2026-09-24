# `xwave` dual-engine graphics demo

`xwave` will follow the initial [`xclock`](XCLOCK.md) application and will be
the first UDEKS application that makes the system's division of labor visible.
It will open a wireframe-style window on the VIC-IIe graphics
screen and plot selectable mathematical waveforms inside it, inspired by the
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
- The status area in the wireframe window will identify `8502: PLOT` and
  `Z80: COMPUTE`, making actual collaboration observable rather than merely
  architectural.

The initial function set should include sine plus at least one function that
does not require a trigonometric table. Arithmetic format, sample count, batch
size, and whether offload is worthwhile must be measured before freezing the
operation ABI. No floating-point library is assumed; fixed-point tables or
bounded integer recurrences are preferred.

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

This requires a foreground-input routing boundary rather than letting the root
line editor consume every key. The router, cancellation flag, buffer lease,
and drawing primitives are prerequisites for the `xwave` command itself.

## Delivery gates

- [ ] Generalize the VIC-IIe surface into clipped pixel and line primitives.
- [ ] Define a bank-aware shared sample-buffer lease.
- [ ] Add one bounded Z80 fixed-point sample operation and an 8502 fallback.
- [ ] Add foreground input routing and `Ctrl+C` cancellation.
- [ ] Draw the wireframe window, axes, labels, and computed polyline.
- [ ] Verify identical samples and bounded cancellation in `1986`, VICE, and
  real hardware.
