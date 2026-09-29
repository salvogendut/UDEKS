# Graphics cache placement snapshot — 2026-09-28

This is a layout/budget qualification, not an executable cache integration.
See `docs/GRAPHICS-CACHE-PLACEMENT.md` for the ownership inventory and next gate.

`report.json` was generated in `my-distrobox` with cc65 V2.18 / Fedora
2.19-15.fc44. `inputs/` preserves every fingerprinted source, map and installer
image at its original repository-relative path. `audit.py` is the exact audit
implementation that produced the report. The assembled ca65 listings measure
actual function and reserve extents; the three od65 dumps measure the cache
wrapper, row mechanism and transfer installer/source. `SHA256SUMS` covers the
qualified files (this explanatory README is not a measured input).

Reproduce current sources with:

```sh
distrobox enter my-distrobox -- make graphics-cache-placement
```

The audit reconstructs the installed scheduler envelope exactly. Its primary
map gap is entirely owned: 1,875 live core bytes, 141 packaged padding bytes,
1,163 installed handler bytes, 50 reserved handler bytes, 323 context code/state
bytes. The cache needs 1,023 bytes against a 49-byte reserve, excluding future
bindings. The five candidate C raster routines total 2,023 live CODE bytes;
that number is not a savings measurement.

Production disks remain unchanged. No emulator or real-hardware run is claimed
by this audit. Historical cache timing/pixel records are preserved separately.
