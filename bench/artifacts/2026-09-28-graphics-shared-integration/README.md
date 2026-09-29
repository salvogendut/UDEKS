# Testable shared-raster boot disks

`build/boot/udeks.d64` and `.d71` are the exact emulator-qualified disks,
reproduced identically by a clean parallel build. Unlike standalone budget
images, they hold all 294 new saved bytes as named resident padding and retain
the frozen `$A1E0-$C11F` shadow, UAPP and common-gateway placements.

Source, normal/panic maps, private import bridges and input harness are saved.
Use D64 with Pi1541; try xinit, xclock &, xwave, drag during/after drawing,
resize/overlap, VDC Ctrl+C, console/history and xinit -q. Hardware testing is
pending. No pixel cache is enabled. See `docs/GRAPHICS-SHARED.md` and the
matching results. SHA-256 manifests exclude this explanatory README.
