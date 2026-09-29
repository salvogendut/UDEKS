# Experimental cache-core delivery and C policy measurement

This archive preserves isolated D71/D64 delivery disks, the one-byte stage-1
LOAD change, the exact scheduler payload and build inputs, and a separately
measured **unexecuted** bank-1 C policy link. It does not enable cached moves.

`build/build-report.json` binds the delivered 213-byte core, disk hashes,
canonical USOV payload, unchanged normal disks and source hashes.
`build/policy-report.json` reports 2,567 linked bytes: 213 core, 1,828 C policy,
526 helpers. Actual cc65 lease/row record sizes are 13/9. No private C
dispatcher, stack or production caller has been qualified by these disks.

See [the delivery notes](../../../docs/WINDOW-CACHE-DELIVERY.md) for the
candidate layouts, limits and reproduction commands. Captures and emulator
provenance are in the matching results archive. `SHA256SUMS` covers preserved
inputs and outputs; this explanatory README is outside that manifest.
