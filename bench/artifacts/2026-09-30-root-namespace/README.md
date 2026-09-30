# Root namespace candidate — 2026-09-30

Issue #26, `storage-root-namespace`, based on `446567d` plus this implementation.
Not yet a hardware-accepted release. Main is unchanged.

Cold-boot `udeks.d64` (Pi1541/1541) or `udeks.d71` (1571). Device 8 backs `/`;
`/bin` shows .BIN/.SH stems, `/etc` shows .ETC stems, `/mnt` starts free.
`USH.BIN` and `RC.ETC` are ordinary DOS files. General .SH execution is still
pending; only /etc/rc auto-runs. Storage is read-only, one stream at a time.
Use `data.d64` on device 9 to test `mount 9 /mnt` and `cat /mnt/HELLO`.
Full manual sequence: [boot documentation](../../../docs/BOOT-STARTUP.md#root-namespace-candidate-26).

`1986-test.d64` is the candidate plus EMPTY/ONE test files. `task-spawn.d64`
is the separate compiled-child task regression fixture, not a user boot disk.
Maps, recovery bootfs, disk shell and filesystem policy/driver bytes record
the placement: policy $B000-$C6D3 (5,844 bytes), BSS $E000-$E116 (279 bytes),
bootfs 3,957 of 4,096 bytes. Shell image is 3,588 bytes plus 368 reserved BSS
(360 used), 140 bytes of reserved-slot headroom. No fixed public gate moved.

Fresh `make -j8 boot placement-check` in `/tmp/udeks-root-build.M1TYvo` under
my-distrobox reproduced both disks byte-for-byte. It was an isolated source
copy, not a clean of a directory containing worktrees. Reference cc65/SDCC
toolchain: [BUILDING](../../../docs/BUILDING.md). Preserved test records live
in [results](../../results/2026-09-30-root-namespace).
