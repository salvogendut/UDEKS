# Storage top-RAM placement proof

`probe.prg` is a standalone, no-disk mapping/NMI proof entered at `$2800`.
`no-forward.prg` differs in one instruction and must fail pending-forwarding
validation. The module/policy/driver/hidden blobs and map are a **separate
link-size candidate, not installed or executed by this probe**; its caller
stub denies OPEN. Do not boot UDEKS with these service blobs.

The corresponding result JSON files contain hashes of every artifact and
source provenance. `tests/test_storage_window.py` verifies them. Reproduction,
allocation bounds and remaining integration gates are in
[Storage 0.3](../../../docs/STORAGE-0.3.md#placement-candidate--guarded-top-ram-window-2026-10-07).
