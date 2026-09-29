# Shared-raster standalone qualification

Reference/candidate × six cases × 1986/VICE: 24 positive records, bound by
run manifests to twelve exact PRGs. Every record checks completion, all 8,000
pixels, 32 dirty flags, three guards, reserved bytes and software-stack balance.
Cases cover line octants/axes/clipping/degenerate points, rectangle clip and
alignment/narrow/invalid geometry, and black/non-black whole-surface clears.

The service C uses production `-Oirs`; the diagnostic driver is unoptimized.
IRQs are masked, display disabled, stock 1 MHz. Line primitive gains are 6–8%,
rectangle matrix 4.14×, clear about 10×. These are not GUI/hardware measurements.
The exact source/build snapshots are in the matching artifact directory.
Independent host geometry and full-image gates are described in
`docs/GRAPHICS-SHARED.md`. SHA-256 manifests exclude this explanatory README.
