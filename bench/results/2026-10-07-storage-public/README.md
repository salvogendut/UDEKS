# Public create-only writes — step 2

Based on `160c591` plus the step-2 working-tree changes. The source disks and
written disposable copies are preserved in
[`bench/artifacts/2026-10-07-storage-public`](../../artifacts/2026-10-07-storage-public).
SHA256SUMS paths are relative to the worktree root. Earlier private-backend and
owner-retirement evidence is unchanged.

VICE true-drive 1541/D64, 1571/D71 and 1581/D81 each pass two cold boots with
the **normal disk-loaded SAVE.BIN**, public UTRQ 0.14, and the real shell and
loader. Only keyboard input events are injected; no syscall, policy, owner or
service code is patched. Both boots initially reject writes (EROFS). Explicit
root RW remount enables create; `df` follows actual permission. Each run checks:

- Exact 0, 1, 24, 254 and 515-byte files, covering all binary byte values and
  sector/chunk boundaries. SAVE checks CLOSE and exact readback itself.
- Folded duplicate rejection, reserved-root-suffix and /bin creation rejection,
  and writable-device alias rejection. No overwrite is issued.
- A write with a native background clock active, subsequent console CAT,
  stopping the clock, remounting RO, and another denied create.
- A fresh emulator process on the written disk: RO defaults restored, every
  new file verifies with `save -c`, and existing console file reading works.

After both processes exit, the host independently decodes every DOS file:
all preexisting file byte streams must match the pristine image, and the only
new files must match the exact five binary patterns. Tests also compare the
SAVE executable inside each disk to the independently linked artifact and
enforce its existing $0200-$0BFF allocation. JSON retains command output and
image hashes. Probes terminate only their own VICE processes in `finally`.
Final gates: **1,324 host tests**, boot/user-programs build, placement-check and
graphics-apps-check pass. Rebuilt normal disks match these artifacts exactly.

Reproduce (each invocation creates a fresh disposable subdirectory):

```sh
distrobox-enter my-distrobox -- make -j8 boot placement-check graphics-apps-check
python3 tools/storage_public_probe.py --drive 1541 --disk build/boot/udeks.d64
python3 tools/storage_public_probe.py --drive 1571 --disk build/boot/udeks.d71
python3 tools/storage_public_probe.py --drive 1581 --disk build/boot/udeks.d81
make check
```

This is the user-testable success path, **not** final step-3 acceptance. Public
write cancellation/leak cleanup, disk-full/write-protect/media-loss injection,
integrated RESTORE, native 1986 and physical C128/PI1541 checks remain due.
No rollback/power-loss guarantee is claimed; failures can leave partial files.
Use disposable copies/media, not disks containing irreplaceable files.
