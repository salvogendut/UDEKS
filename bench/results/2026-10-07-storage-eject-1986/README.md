# 1581 media ejection — verified under native 1986

This follow-up covers the UDEKS media-loss behavior that the VICE 1581 run
could not observe. It uses unchanged 1986 revision
`19386ef83d43f2770fd503541ef7ee26d4ae1249` and the unchanged UDEKS candidate
from `451fdcf`. Only the UDEKS-side test harness and host-side audit are new.
It does **not** diagnose or fix VICE's disappearing monitor/process.

## Test and result

Two ROM-backed 1581s use raw IEC: copied system D81 at unit 8, disposable data
D81 at unit 9. The system copy only adds the already qualified WHOLD.BIN fixture.
Keyboard commands run through 1986's normal input. Only WHOLD's private case
and release bytes are poked; no OS request, owner, error or lifecycle state is
patched. Ejection calls `drive_attach_disk(&machine->drive2, NULL)`, the same
media API as the UI. The harness asserts the 1581 remains connected while its
WD1770 has no disk. No drive reset, power cycle or disconnect substitutes for
removal.

After a successful initial 24-byte write, the client yields with the file open.
The harness ejects media, releases the client to WRITE another 24 bytes and
CLOSE, and verifies:

- WRITE returns EIO (5), with zero additional bytes accepted.
- CLOSE returns EIO (5); the task exits and releases its allocation.
- Owner generation advances 1 -> 2, with cleanup error zero.
- The console can still read `/hello` from the separate system disk.
- Reinserting the same data disk permits KEEP readback and a new RECOVER save.
- The same native allocation can run another writer, EXIT-finalize OWNER4,
  and read it back. Guards remain intact.
- A second fresh emulator process reads KEEP, RECOVER and OWNER4 exactly.

Host decoding independently confirms KEEP is unchanged; RECOVER and OWNER4
are closed SEQ files containing exactly bytes 0..23; the copied system image
is unchanged. The aborted OWNER2 has **no directory entry** in this run. A
failed operation is allowed to leave no entry, an unclosed entry or partial
data; absence here is not a general rollback guarantee.

Both emulator phases completed successfully. The original postprocessor then
incorrectly required an aborted OWNER2 entry to exist. `original-run.log`
preserves that assertion. The corrected `collect_ejection()` audits the same
completed logs and media, permits the documented absent/partial outcomes, and
generates `result.json`. No emulator behavior, client or UDEKS runtime was
changed to obtain this pass. Host regression tests reproduce that audit.

## Reproduce

From this feature worktree:

```sh
distrobox-enter my-distrobox -- make -j8 storage-failure-fixtures
distrobox-enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --storage-eject --drive 1581 \
  --emulator /path/to/1986 --roms /path/to/1986/roms \
  --disk bench/artifacts/2026-10-07-storage-acceptance/udeks.d81 \
  --output build/storage/native-eject
```

Each invocation creates fresh disposable copies. Source/fixture/media hashes
and emulator revision are in result.json; SHA256SUMS paths are relative to the
repository root. ROM-bearing snapshots and the native executable are not
archived. The VICE-specific case remains unreproduced successfully, but the
equivalent UDEKS 1581 ejection/recovery path now has independent emulator
coverage. This is not a physical 1581 test or proof of arbitrary power-loss
safety. No production image was changed.
