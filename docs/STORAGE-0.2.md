# Storage 0.2 — launch programs from disk

Issue [#18](https://github.com/salvogendut/UDEKS/issues/18), branch
`storage-0.2-disk-exec`, worktree `build/storage-disk-exec`. Based on the
Storage 0.1 candidate `d351d14`; PR #17 stays draft until physical C128/PI1541
testing passes. Do not modify the preserved Storage 0.1 hardware images.

## First acceptance slice

Mount a disk containing `DISKCOW` (the existing cowsay UDEX, stored only as a
real DOS file), invoke `/mnt/DISKCOW hello`, observe the cow and its exit
status, then invoke it again. `DISKCOW` must not appear in bootfs: this keeps
the test from accidentally passing through the existing packaged-program path.
Bootfs commands, the shell, graphics and input must still work afterward.

Reject absent media, missing files, bad headers, truncation, trailing bytes,
unsupported CPU/flags and occupied/out-of-range allocations without entering
partial code. Repeat with a graphical app active and with a live ordinary
task occupying the proposed staging/destination slot.

## Implementation sequence

1. Prepare a disk-only positive fixture and malformed/truncated fixtures.
   **Done:** `make disk-exec-image` packages DISKCOW, BADUDEX and SHORT into
   `build/disk-exec/test.d64` and `test.d71`, without changing bootfs or the
   normal boot images.
   This is fixture preparation, **not yet a working disk-execution command**.
2. Connect the existing mount/read/close path to the existing UDEX validator
   and launch mechanism. Keep pathname/file policy in a non-kernel service;
   preserve argc/argv, exit status, ABI gates and bootfs fallback. Validate
   header/allocation before copying, and exact EOF before publishing/entering.
3. Qualify repeated successful and rejected launches in VICE and 1986, then
   provide the next physical-hardware test image. No loader optimization,
   relocatable format, disk writes or desktop work is a prerequisite.

The placement check is real, not assumed: the current common-RAM loader uses
all 1,520 bytes of `$F910-$FEFF` (`od65 --dump-segments` on stage1-gateway.o).
The storage service currently uses 2,006/3,584 module bytes, 1,297/1,536 policy
bytes, 1,094/1,536 driver bytes and 111/256 BSS bytes. Its bank-0 router uses
75/128 bytes. A loader hook must reclaim/move existing file-lookup code into
service space, not silently grow common RAM or move frozen vectors. Bank-1
APP1 and its stack are task-owned, not unconditional staging scratch; check
ownership before any write. The retained graphics cache is not free space.

## Follow-through

After ordinary disk execution is qualified, use the loading path for the shell
and introduce a shell-run startup script for mounts and optional services.
Define the bootstrap source needed to load that shell before normal mounts
exist. Keep bootfs as the migration fallback, not the intended end state.
