# Disk-first shell boot — 2026-09-30

Issue #20's first testable slice; positive user acceptance is recorded below.
The platform for that manual test was not specified.
This does not implement startup scripts or finish the kernel-only boot model.
The exact normal images and DISKCOW test candidates are under
`bench/artifacts/2026-09-30-disk-shell`, with SHA-256 manifests checked by
`make check`. The preceding accepted Storage 0.2 artifacts are unchanged.

- `vice-1541.json`, `vice-1571.json`: VICE x128 3.10, true 1541/D64 and
  1571/D71. Each records six cold boots. Changing only the disk `USH` file
  changes `uname -a` to diskA/diskB, while missing, bad magic, wrong persistent
  entry and wrong flags recover to the original bootfs shell. All variants
  accept mount/read/unmount and a bootfs command afterward. Fixtures are
  reproducible by `tools/disk_shell_fixture.py`; host tests reconstruct their
  hashes from the preserved normal images and verify only USH bytes changed.
- `disk-exec-1541.json`: the final test D64 passes all 43 existing shell
  commands: arguments/repeated disk launches, header/bounds/errors, child-slot
  rejection, bootfs fallback, media removal/reinsertion, xclock/xwave active.
- `1986.json`, `1986.log`: unmodified sibling revision `637baa2`, native
  cold boot/raw IEC and real keyboard events. Checks disk-source diagnostic,
  `uname -a`, repeated execution, file errors, exit/BSS and media recovery.
  No keyboard queue or submitted-line record is patched in this runner.
- `spawn.log`: two real compiled child SPAWN/return/EXIT(37)/WAITPID cycles
  using the dedicated probe shell, also delivered as the disk USH file.
- `shadow.log`: full shadow clear, installed scheduler, 50-byte tail-preimage
  preservation and bank-0 shadow/bank-1 VIC equality after xinit+xclock.

A fresh source-only `make -j8 boot disk-exec-image panic-probe placement-check`
inside my-distrobox reproduced all four normal/test disk files byte-for-byte.
Reference compiler remains cc65 V2.18 (Fedora package 2.19-15.fc44). Normal
and panic links retain the resident/VIC placements. The new common loader is
1,496/1,520 bytes including padding; bank-1 lookup/bootstrap is 891/1,536.
`make check` passes 898 host/evidence tests; container `make placement-check`
passes. All private VICE sessions exited after qualification.

The first live attempt exposed the still-live scheduler activator at `$F68A`
being overwritten by storage's temporary gateway. The final bootstrap saves
and restores its full 42 bytes, including recovery paths. A later 1986
test-harness check typed `uname +a`: its positional SDL Minus mapping is C128
plus, so the harness now uses SDL Equals for native minus. No emulator or
UDEKS input driver changes were needed. Failed attempts are not counted as
passes; these records are the passing final-image runs.

All live runs here use IEC unit 8. Other units, unreadable-media during the
initial shell read, and failure of both disk and embedded recovery shell
remain outside this live qualification. Existing disk-command I/O-error
tests are not a substitute for those bootstrap-specific tests. Physical
acceptance of PR #19 does not qualify the additional read/startup path here.

## User acceptance

After receiving this candidate and its boot/command/graphics checklist, the
user reported: "it all looks good". This is positive manual acceptance of
the disk-loaded-shell slice. No platform, disk hash, or individual check
results were supplied; do not broaden it into a separately confirmed
physical-C128/PI1541 or exhaustive recovery-path qualification.
