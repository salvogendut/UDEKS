# Storage 0.3 — step-3 emulator and physical functional acceptance

Candidate: `5fb989b` plus the step-3 working changes. Exact normal disks and
storage service images/map are in `bench/artifacts/2026-10-07-storage-acceptance`.
SHA256SUMS paths are relative to the worktree root. Earlier evidence is unchanged.
Final checks: **1,332 host tests**, container boot, placement-check and
graphics-apps-check pass. No VICE processes remain after the probes.

## Coverage

| Platform | Public failure / retirement suite | Native input, NMI, reboot |
| --- | --- | --- |
| VICE 3.10 / 1541 / D64 | Pass, including media removal and disconnected CLOSE | Earlier public reboot suite |
| VICE 3.10 / 1571 / D71 | Pass, including media removal and disconnected CLOSE | Earlier public reboot suite |
| VICE 3.10 / 1581 / D81 | Pass except explicitly skipped mid-write media removal | Earlier public reboot suite |
| 1986 `19386ef` / 1571 / D64 | Not the fault-injection harness | Pass |
| 1986 `19386ef` / 1581 / D81 | Not the fault-injection harness | Pass |
| Physical C128 / PI1541 | Fault injection not tested | Manual checklist passed, user report 2026-10-07; RESTORE, not CIA2 timer stress |

### Manual acceptance — 2026-10-07

The user first confirmed the checklist in 1986, then reported that all tests
passed on a real C128 with PI1541. The checklist covers WRTEST (515 bytes),
EMPTY (0), LIVE (24) creation and cold-boot verification; duplicate rejection;
RW/RO remount and RO defaults after reboot; clock dragging, RESTORE, console
input, clock close and reading `/hello`.

The supplied D64 is the archived normal candidate, SHA-256
`1e29e08fe0e633f6b5d643623dbf1661973651d4806138a9aaeb9cdec240a678`.
No hardware memory dump or independently measured tested-media checksum was
provided. This is user-reported functional acceptance, not a physical full-disk,
write-protect, removal/power-loss, or 1581 test. The VICE limitation below remains.

### Automated failure and retirement checks

The VICE suite uses a copied system disk on drive 8, independent public clients,
and freshly generated data disks on drive 9. No OS request replies are patched.
Foreground return, native EXIT/slot reuse and actual parent CANCEL/WAITPID all
finalize written files before owner-generation retirement. Foreign CLOSE is
rejected by the parent fixture. The fixtures are not shipped on normal disks.

Physical write protection, absent device, completely full disk and exhaustion
partway through WRITE produce errors, preserve existing files, and leave the
console and storage usable. The full-disk case motivated a free-block preflight:
some drive allocation failures report DOS 67 instead of 72. Known zero free
blocks now return ENOSPC before create; genuine geometry errors remain EIO.
No speculative mapping of all DOS 67 errors to disk-full is made.

The full-disk image gains no file. The partial-write image can contain a closed
partial file despite the reported failure. Removed/disconnected media retain
unclosed entries. This is expected: there is no rollback or power-loss guarantee.
Independent host decoding verifies all preexisting file contents, exact new
successful byte patterns, read-only disk immutability, and unchanged system
disks. Written copies are included here; **do not use faulted copies as boot media**.

For the CLOSE fault, the harness disables the VICE software bus device and true
drive, checking resource readback, then restores the drive and successfully saves
again. Eject alone is not a reliable CLOSE fault: firmware may acknowledge a
buffered close after removal. These are separate test cases.

### Explicit 1581 limitation

The Flatpak VICE process repeatedly disappears immediately after `detach 9`
while a 1581 writer is open. `vice-1581-limitation/run.log` preserves the failed
attempt; it is **not a successful UDEKS media-loss test**, and the root cause in
VICE is not diagnosed here. The subsequent D81 run uses the explicit
`--skip-media-removal` option and records that omission in JSON. Drive loss at
CLOSE and recovery still pass. Mid-write 1581 media loss remains an acceptance
gap requiring a working emulator path or physical test before claiming coverage.

### Native 1986

The sibling emulator source was not modified. Its real keyboard enters SAVE,
mount and clock commands; the 1351 path drags a clock. RESTORE is a real key
event; recurring CIA2 Timer A NMIs exercise a save via device registers, not OS
hooks. The harness checks NMI drain counters, pending state and task canaries.
Each run starts a second fresh emulator on the written disk, checks RO defaults,
and reads back BINARY (515), ZERO (0), NMITEST (515), GRAPHICS (24). Host decoding
also verifies all preexisting files and the exact four new byte patterns.
Logs, resulting images and source/candidate hashes are retained; ROM-bearing
emulator snapshots are deliberately not archived.

## Reproduce

From the feature worktree, using the container for the toolchain/SDL:

```sh
distrobox-enter my-distrobox -- make -j8 boot storage-failure-fixtures placement-check graphics-apps-check
python3 tools/storage_failure_probe.py --drive 1541 --disk build/boot/udeks.d64
python3 tools/storage_failure_probe.py --drive 1571 --disk build/boot/udeks.d71
python3 tools/storage_failure_probe.py --drive 1581 --disk build/boot/udeks.d81 --skip-media-removal
distrobox-enter my-distrobox -- python3 tools/1986_storage_smoke_build.py --storage-write \
  --emulator /path/to/1986 --roms /path/to/1986/roms --disk build/boot/udeks.d64
# Second native run: add --drive 1581 and select udeks.d81.
make check
```

The default VICE probe does not skip any failure case. Each invocation creates
disposable media and terminates only its own VICE processes. Physical acceptance
above is the separately reported manual checklist; PR/merge is not implied.
