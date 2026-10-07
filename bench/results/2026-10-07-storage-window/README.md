# Storage top-RAM proof — VICE and 1986

Both emulators pass `$D506=$09` and `$49`: 128 rounds, 215 visible + 169 hidden
NMIs, 128 boundary-window arrivals, 3,840 common bytes unchanged, restored
mapping/stack, and execution from hidden RAM. A one-instruction negative
control suppressing private-pending forwarding fails with code 1 in both.
JSON includes raw 32-byte records, decoded results, artifact/source hashes,
linked-candidate budget and emulator provenance. No disk is attached.

This qualifies the standalone mapping/NMI mechanism and separately measures
the full service. It does not qualify an installed storage lease, lifecycle
cleanup, live filesystem, graphics/Z80 interaction or physical hardware.
See [Storage 0.3](../../../docs/STORAGE-0.3.md#placement-candidate--guarded-top-ram-window-2026-10-07).
