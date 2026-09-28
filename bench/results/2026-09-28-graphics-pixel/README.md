# Pixel ABI qualification — 2026-09-28

Sixteen positive records: C reference and ASM entry × four cases × 1986/VICE.
Each compares 8,000 bitmap bytes, 32 logical dirty flags, completion metadata,
three guards, reserved bytes and a software-stack-balance failure flag.
Signed extremes, custom and empty clips, all bit/row offsets, non-black colors,
unaligned logical page boundaries and 1,024 repeated pixels are covered.

The 190-byte ASM entry saves 87 linked bytes. Combined with span/fill it saves
173; library-helper membership is unchanged. Timings are masked-IRQ,
display-off, 1-MHz primitive probes including diagnostic driver overhead, not
GUI timings or hardware qualification. Exact PRGs and source snapshots are in
the matching artifact directory; run manifests bind raw results to their PRGs.

The corrected stack checker stores both SP reads before comparison. An inline
comparison pushes a cc65 temporary and falsely rejected the C reference.
`SHA256SUMS` covers preserved evidence, excluding this explanatory README.
