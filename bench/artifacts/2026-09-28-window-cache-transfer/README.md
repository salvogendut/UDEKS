# Standalone packed-window transfer prototype

Exact eleven PRGs, linker maps, generated assembly, source snapshots and
measured build report for issue #6 on `graphics-window-cache-spike`, based on
`94a0ea1`. The PRGs load/enter at `$2000` through the raw monitor, not BASIC.
They are **not replacement UDEKS boot disks**. They use stock 1 MHz with
display disabled and IRQs masked; no ROM image is distributed.

The production cache C flags are `-Oirs`. The diagnostic driver is deliberately
unoptimized after an unsafe optimized constant-pointer completion store was
observed during development. cc65/compiler provenance and all relevant input
hashes are in `build-report.json`; the cache C is 1,113 CODE + 30 BSS bytes,
and transfer assembly is 130 CODE bytes, including a 99-byte copied gateway
at `$F68A-$F6EC`. This does not fit the production 49-byte raster reserve.

Rebuild and run from the repository root with the tools listed in
[the design note](../../../docs/WINDOW-MOVE-CACHE.md). Matching raw records,
timer results and engine provenance are in
`bench/results/2026-09-28-window-cache-transfer/`.

`SHA256SUMS` covers the exact programs, maps, generated assembly, source
snapshots and report. README text is not part of the generated checksum list.

The production D71 remains
`5f71ff8593f0313747987995e35310e506a15bef8d0881d210f336d2bd51c2d7`;
the D64 remains
`3f6543641f7090e657cd5d94cc3d65ae05a8a0146d8b8da47b177ee2fcedde68`.
No resident image was modified or qualified by this prototype.
