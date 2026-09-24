# `xmandel` dual-engine Mandelbrot viewer

`xmandel` is the planned computation-heavy companion to `xwave`. Its visual
and numerical reference is `../geobench/apps/xaos/main.c`, GEOBENCH's
render-then-explore `XAOS.APP`: a fixed-point Mandelbrot viewer with
incremental row publication, recentering, and zoom controls.

The UDEKS version will preserve the useful constraints proven there—Q4.12
fixed-point coordinates, bounded iteration counts, and incremental visible
progress—while adapting the execution model to the C128:

- the Z80 computes bounded pixel or row tiles into a leased common-RAM result
  buffer;
- the resident 8502 validates returned tiles, maps iteration values to the
  one-bit UDEKS presentation, and commits them through the VIC-IIe service;
- the 8502 window manager retains title-bar, focus, pointer, clipping, zoom,
  recenter, close, and damage policy;
- the VDC root console remains live and observes `Ctrl+C` between short Z80
  leases;
- an 8502 calculation path produces the same iteration values for correctness
  checks and crossover measurements.

The GEOBENCH source reports roughly 15–20 seconds for an 80x56, 20-iteration
render on its 4 MHz Z80 target and uses 16-pixel cooperative budgets. UDEKS
must measure its own tile size: the C128 CPUs do not run concurrently, so a
lease must be long enough to amortize ownership transfer but short enough to
preserve input and console responsiveness.

`xwave` remains the first dual-engine client because its sample batches are
small and deterministic. `xmandel` follows as the sustained-compute and
cancellation stress test.
