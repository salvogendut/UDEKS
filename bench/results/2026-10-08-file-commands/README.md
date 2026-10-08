# Writable root and standalone file commands — 2026-10-08

Issue #47, branch `storage-0.4-file-commands`; UTRQ 0.18. The exact boot
images, compact storage service/map and independent commands are in
`../../artifacts/2026-10-08-file-commands/`. D64 deliberately omits XSPRDEF.BIN
and has 31 free blocks. D71 and D81 retain every application. No original or
user disk was attached during these tests; probes operate on disposable copies.
Toolchain: `cl65 V2.18 - Fedora 2.19-15.fc44` in `my-distrobox`.

## Passed gates

- VICE Flatpak 3.10, true-drive 1541/D64, 1571/D71, 1581/D81: native boot,
  CP/MV/RM through the ordinary shell/loader, exact-name and collision errors,
  RO rejection, empty copy, 2 KiB (D64) / 4 KiB (D71/D81) binary copy/rename
  and readback with xclock active, deletion, reboot persistence and preservation
  of every original file. Public reports identify the exact input disk hashes.
- Native 1986 rev `19386ef83d43f2770fd503541ef7ee26d4ae1249`, ROM-backed 1571
  with the final D64: actual keyboard, binary/empty CP/MV/RM, clock dragging,
  RESTORE, write/readback and cold-reboot persistence. **Periodic CIA2 timer-NMI
  stress explicitly skipped** in this successful ordinary run (see below).
- 35,320 simulated-6502 mutation cases against the independent C backend,
  6,193 writer-status cases against C, and pending/abort/exhaustion checks.
  The 65,535-observation bound terminates without resending a DOS command.
- 24 real cc65 SDK scenarios: calling convention, gate records, pending poll,
  cleanup, version/sequence handling, malformed replies and error precedence.
- 1,492 host tests, boot, graphics-apps-check, placement-check, namespace
  differential/negative control, isolated full-service link. Original memory
  reservations stay fixed: 11 code bytes and 26 state bytes spare in aggregate.

## Reproduction

In `my-distrobox`:

```
make -j8 boot graphics-apps-check placement-check storage-mutation-policy \
  storage-namespace-check file-mutation-sdk-check storage-mutation-backend-check
python3 tools/1986_storage_smoke_build.py \
  --emulator /var/home/salvogendut/Dev/1986 \
  --roms /var/home/salvogendut/Dev/1986/roms --disk build/boot/udeks.d64 \
  --storage-write --skip-write-timer-stress --output build/storage/1986-file-commands
```

On the host: `make check`; then `python3 tools/storage_public_probe.py
--mutations --drive 1541 --disk build/boot/udeks.d64` (repeat with 1571/D71 and
1581/D81). Probes terminate their own emulator instances.

## Known limits and observations

The full periodic timer-NMI run is **not qualified**. A native 1986 run printed
`save: loader error` for `/nmitest`. The old test incorrectly accepted previous
success text plus a stale zero exit code; reboot then exposed the missing file.
The failure transcript is retained, and the harness now checks loader state
and the submitted command as well. Ordinary testing explicitly records
`timer_nmi_stress: false`; it is not a replacement for that stress gate.

An earlier VICE D64 run returned EIO after SCRATCH had deleted the requested
file. Subsequent complete D64 runs passed, including the final image. Its error
record is retained; the cause has not been established. An I/O error must not
be retried automatically and does not imply rollback.

Console programs still run synchronously. Copy/rename is same-filesystem only,
destinations must not exist, and removal never accepts wildcards or directories.
Physical C128/Pi1541 acceptance of these new commands is still due.

The older failed-fit checkpoint under `2026-10-08-file-command-policy` remains
unchanged historical evidence, not the delivered service.
