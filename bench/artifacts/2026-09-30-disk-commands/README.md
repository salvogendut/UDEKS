# Command extraction candidate — 2026-09-30

Issue #24, branch `boot-disk-commands`, following merged PR #23 (`2c88e07`).
Step-2 checkpoint: `d42073c`. This candidate also removes the resident command
catalog and adds UTRQ 0.7 deferred service controls. The source and evidence
are committed together; these exact images were tested, not reconstructed
from a later build. See [results](../../results/2026-09-30-disk-commands/README.md)
and [test instructions](../../../docs/COMMAND-EXTRACTION.md).

`udeks.d64`/`udeks.d71` are normal native-boot images. `udeks-test.d64` adds
disk-execution rejection fixtures; `spawn.d64` is the compiled lifecycle probe,
not the interactive system. UDEX files, recovery bootfs and normal/panic maps
are preserved with hashes. Rebuild with `make -j8 boot disk-exec-image panic-probe
placement-check` in my-distrobox. No root `make clean`: active worktrees live
under build. An isolated clean parallel build reproduced all normal/panic disks
byte for byte.

No new physical-C128 qualification is claimed. The user-test candidate is the
normal D64 (PI1541) or D71 (1571), not the regression-probe disk.
