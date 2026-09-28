# Span results — 2026-09-28

Sixteen positive records: two implementations × four cases × two emulators.
Independent decoders compare all 8,000 shadow bytes and 32 dirty flags. Matrix
and isolated-crossing records also check shadow/state guards and reserved bytes.

The two negative-control records have correct pixels but deliberately omit
logical dirty flag 0. They must be rejected; they are not positive passes.

`report.json` records primitive timings. Bulk aligned/clipped fills improve
3.55–3.57×; the small-fill matrix improves 1.29×. IRQs are masked, display off,
stock 1 MHz, with no screen commit, compositor, input or hardware claim.

Run manifests bind every record to its exact PRG. 1986 provenance fingerprints
the read-only emulator inputs; VICE's Flatpak identity is preserved. The probe
runner closes only its own VICE sessions. `SHA256SUMS` covers qualified files,
not this explanatory README. No production image has changed.
