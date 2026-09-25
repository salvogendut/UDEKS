# `xwave` dual-engine isometric surface

`xwave` is the first UDEKS application that makes the system's division of
labor visible. It opens a managed VIC-IIe bitmap window and renders a radial
sinc surface, `z = sin(r) / r`, as a two-axis isometric wireframe.

The visual concept was requested from the RAINBIOS `pcsurf-bbc-msx.bbc`
example, whose comments trace it to an older PC-SURF BASIC program. That file
also states that its source repository declares no license. UDEKS therefore
uses an independent GPL-3.0-or-later fixed-point implementation of the
mathematical surface and isometric projection; it does not incorporate the
BASIC source text. The current projection also follows the classic GW-BASIC
form `screen_x = x - y`, `screen_y = x + y - z`, expressed entirely with
bounded integer arithmetic.

## Engine split

- The Z80 computes signed heights for a fixed 25×21 sinc grid through mailbox
  ABI 0.3 `SURFACE_ROWS` requests.
- Every lease contains one row (25 samples), well below the 64-byte shared
  transfer-buffer limit. The worker validates row, count, and length before
  accepting the request.
- The resident 8502 owns application lifecycle, input, window geometry,
  isometric projection, clipping, and VIC-IIe line rasterization.
- The 8502 contains the identical 35-entry fixed-point sinc table and radius
  approximation as an availability fallback when the Z80 worker is offline.
- Common-RAM diagnostics count Z80 leases, 8502 fallbacks, repaints, focus,
  drag state, grid dimensions, and total surface samples.

The projection uses 25 horizontal points and 21 depth rows. Alternating rows
and columns form continuous polylines through every sample on both grid axes,
producing a readable diamond mesh at the compact default window size instead
of disconnected row strips or an overdrawn black center. Its normalized
coordinates are scaled continuously to the current client width and height on
every managed repaint. A 40-unit fixed-point vertical gain gives the central
sample a pronounced peak while preserving the surrounding sinc troughs and
rings inside the normalized projection envelope. A private 525-byte surface
cache retains every computed height, while the 25-byte row scratch area at
`$F340-$F358` supplies cross-grid connections during plotting. Initial display
and a changed client width or height recompute the cache through 21 bounded Z80
row leases. Moving, raising, revealing, or otherwise repainting an unchanged
window uses the cached heights and submits no Z80 work. The plot is clipped by
the window manager after resizing; moving or resizing still uses the
lightweight outline-only interaction and repaints once on release.

The plot is deliberately static. Periodic full recomposition would monopolize
the 1 MHz 8502 and starve pointer and keyboard service. Future animation must
retain computed samples or advance a bounded row budget per cooperative poll.

## Foreground job and cancellation

Launching `xwave` makes it the foreground job while the VDC root console
remains the controlling terminal. Pressing `Ctrl+C` on that console produces
character `$03` through the normalized keyboard service and requests
termination. Appending a standalone `&` starts it in the background and
immediately returns the prompt.

The Z80 cannot be interrupted while it owns the C128 bus. Each surface row is
therefore a short, statically bounded lease. Once initial painting finishes,
the application poll performs no computation or repaint and normal pointer,
keyboard, and console polling resumes. A compositor repaint caused by move or
stacking projects the cached surface on the 8502; only a resize invalidates the
cache and invokes the Z80 again.

## Delivery gates

- [x] Generalize the VIC-IIe surface into clipped pixel and line primitives.
- [x] Define a bank-aware shared sample-buffer lease.
- [x] Add bounded Z80 sinc-row computation and an identical 8502 fallback.
- [x] Project a 25×21 radial surface as a connected two-axis isometric mesh.
- [x] Preserve foreground/background job control and `Ctrl+C` cancellation.
- [x] Keep the managed window movable, resizable, overlapping, and closable.
- [x] Cache the completed surface so move, reveal, and restack repaints do not
  repeat Z80 computation; invalidate it only when window dimensions change.
- [ ] Verify visual output, resizing, and bounded cancellation in VICE and on
  real hardware.
