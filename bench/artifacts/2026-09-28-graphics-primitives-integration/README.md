# Testable raster-primitives disks — 2026-09-28

`build/boot/udeks.d64` and `.d71` are the exact emulator-qualified integrated
images. Source, normal/panic maps, generated private bridges and input harness
are preserved alongside them. Unlike the standalone budget links, these
images retain the frozen shadow placement through 173 bytes of named padding.

Use D64 with Pi1541. Cold boot and exercise `xinit`, `xclock &`, `xwave`, drag,
resize/overlap, VDC Ctrl+C, normal console/history input and `xinit -q`.
Physical hardware testing is pending; this does not enable the pixel cache.
Results and complete provenance are in the matching results directory.
`SHA256SUMS` excludes this explanatory README.
