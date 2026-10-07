# Actual guarded storage-service qualification

This is the **real linked C service and IEC transport**, run from a standalone
probe. It is not an installed, write-enabled UDEKS disk or a scheduler test.
The exact module/policy/driver/hidden binaries, linker map, probe and negative
probe are in `bench/artifacts/2026-10-07-storage-lease/`. Each JSON records their
SHA-256 hashes, source hashes, VICE version, decoded result and exact file bytes.
The host tests verify these against the preserved binaries.

VICE 3.10 true-drive runs pass on 1541/D64, 1571/D71 and 1581/D81, with both
VIC-bank settings (`D506=$09` and `$49`): **27 requests + 3 cleanup calls** per
case. Tests cover RO rejection, explicit RW/remount, boot-source and cwd
snapshots, trusted instance ownership, idempotent initialization while open,
binary creation/readback, duplicate rejection, exact empty-file cleanup,
invalid mapping rejection, C-stack restoration and its bottom guard, an
untouched 256-byte common-memory sentinel, and hidden NMI forwarding. The
probe pins hardware pages zero/one to bank 0 and saves/restores cc65 ZP around
calls; relocated application CPU pages are a later integration gate.

An independent host DOS-chain reader checks `LEASE` is exactly bytes 0–50,
`EMPTY` is zero bytes and the pre-existing 768-byte `KEEP` is intact, with no
other files. All media are generated fresh, never supplied user disks. The
data remain in the finalized image; reboot readback of this service is not
claimed (the older backend probe covers backend persistence separately).

The negative control changes only the real lease's `STA $FFF5` forwarding
instruction to `BIT $FFF5`. The probe detects the lost deferred NMI at phase
1, before any write; the whole disposable image remains byte-identical.

Reproduce from this branch's worktree:

```sh
distrobox-enter my-distrobox -- make -j8 storage-lease-probe
python3 tools/storage_lease_probe.py
python3 tools/storage_lease_probe.py --vic 64
python3 tools/storage_lease_probe.py --drive 1541 --negative
```

`--preserve` archives evidence but refuses to replace different existing
evidence. Use a new revision after code changes. Working media/logs live in
unique directories under `build/bench/storage-lease/`. The harness terminates
only its own VICE processes. No new 1986, physical-C128, cartridge-NMI,
scheduler/cancellation or production-boot qualification is inferred here.
