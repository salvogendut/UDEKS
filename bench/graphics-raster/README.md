# Standalone raster timing suite

This benchmark extracts the actual line/fill functions from the display service
and compares an automatic-local reference with integrated static scratch storage. It
does not boot UDEKS or replace production build outputs.
The builder normalizes only those declaration blocks, so the reference remains
available after the production service switches to static locals.

```sh
distrobox enter my-distrobox -- python3 tools/graphics_raster_bench_build.py
distrobox enter my-distrobox -- python3 tools/graphics_raster_bench_run.py \
  --engine 1986 --output build/graphics-raster-results
python3 tools/graphics_raster_bench_run.py \
  --engine vice --output build/graphics-raster-results
python3 tools/graphics_raster_bench_decode.py build/graphics-raster-results
```

The 1986 runner uses the unmodified sibling sources plus SDL in the container;
it loads raw benchmark code into RAM and needs no ROM files. This is deliberately
not a native disk/input test. VICE uses the existing deterministic paused-monitor
raw loader and terminates each owned session after capturing the result.

PRGs load/enter at `$2000`. The startup selects bank-0 RAM/I/O, 1 MHz, normal
zero/stack pages, and masks IRQ/NMI sources with the VIC display and sprites off.
It uses a `$7800` software stack and the production `$A1E0` shadow address.
The linker stops code/BSS below `$7000`, outside stack/result/shadow areas.

CIA1 Timer A counts Phi2 events from `$FFFF`; Timer B counts its underflows.
The benchmark stops both and complements their counter bytes to form a 32-bit
elapsed count. Counts include fixed timer call/stop overhead. There is no timer
overflow in these workloads. Display-off, interrupt-masked primitive timing
is **not** an end-to-end console/window latency measurement.

Each 8,096-byte record starts at `$7FC0`:

| Offset | Meaning |
| --- | --- |
| 0–3 | `RAST` signature |
| 4 | Format 1 |
| 5 | State 1 running, 2 complete |
| 6 | Variant 0 baseline, 1 static scratch |
| 7 | Workload 0–3 |
| 8–11 | Little-endian 32-bit elapsed timer count |
| 12–63 | Reserved zero |
| 64–8063 | Entire 8,000-byte resulting bitmap |
| 8064–8095 | Entire 32-byte dirty-page map |

The decoder requires a complete record, exact independent-reference pixels
and dirty flags, and equal output across both variants/emulators before
reporting timing reductions. Initial bitmap bytes are `(offset*13+7)&255`.
Workloads are 96 short lines, 24 long clipped lines, 24 aligned fills, and 24
non-byte-aligned clipped fills. Black sets bitmap bits; nonblack clears them.

For physical C128 use, these are raw RAM-entry probes, not BASIC `RUN` programs.
They take over interrupts, timers, and mapping and intentionally spin after
completion. Reset afterward; do not try them as resident UDEKS applications.
