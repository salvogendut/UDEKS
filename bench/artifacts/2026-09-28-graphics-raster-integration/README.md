# Exact raster integration artifacts

Integrated boot disks, standalone automatic/static raster PRGs, and source
snapshots. Qualification and reproduction are documented in the matching
`bench/results/2026-09-28-graphics-raster-integration/README.md`.

The PRGs are RAM-entry `$2000` probes, not BASIC RUN applications; they disable
display/interrupts and spin after completion. Reset afterward. The D71/D64
images are the normal UDEKS boot images for functional hardware testing.
