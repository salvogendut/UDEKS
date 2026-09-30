# Storage 0.2 — launch programs from disk

Issue [#18](https://github.com/salvogendut/UDEKS/issues/18), branch
`storage-0.2-disk-exec`, worktree `build/storage-disk-exec`. Based on the
Storage 0.1, merged by explicit user authorization as PR #17 (`92a2e36`).
Physical C128/PI1541 results for Storage 0.1 have not been recorded; merging
does not imply that qualification. Its preserved hardware images are unchanged.

**Current checkpoint:** ordinary foreground disk execution is implemented and
the user reports that all suggested tests passed under 1986 following checkpoint
`f0a9065`, then confirmed they ran beautifully on a real C128 with PI1541 and
authorized continuation. This closes the requested manual hardware gate for
this slice, not exhaustive device/model/error-path qualification. Disk-loaded shell/startup scripts,
disk SPAWN, managed apps and PATH search remain follow-through work.

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

1. **Done:** `make disk-exec-image` packages DISKCOW, BADUDEX, SHORT, ENTRY and
   LIMIT into `build/disk-exec/test.d64` and `test.d71`, without changing bootfs.
2. **Done:** `/mnt/NAME` foreground execution uses the existing C storage
   service's OPEN/READ/CLOSE operations, preserves argc/argv and exit status,
   then passes the staged file through the existing UDEX validator. Exact EOF,
   header, image+BSS bounds and entry are checked before live APP1 is replaced.
3. **Emulator-qualified:** VICE 1541/D64 and 1571/D71 cover repeated execution,
   all header rejection classes, truncation/trailing data, size limits,
   nonzero entry/BSS, missing/unmounted/removed media, recovery, bootfs and
   xclock/xwave coexistence. Native 1986 raw-IEC keyboard tests cover execution,
   arguments, entry/BSS/limit, failures, recovery and bootfs. The user has also
   confirmed the suggested manual 1986 sequence and successful real C128 +
   PI1541 testing. No additional format/hash/model or exhaustive failure-path
   report was supplied; retain that scope when citing hardware acceptance.

## Placement and ownership

The common loader now occupies 1,261/1,520 bytes at `$F910-$FEFF`; the original
bootfs lookup and UDEX validation live in a 716-byte bank-1 extension at
`$1A00-$1FFF`, linked in the same invocation and delivered with `SCHEDOVR`.
Its `ULKP 0.1` identity is checked before dispatch; missing delivery fails closed.
The C storage module uses 2,006/2,048 bytes at `$1200-$19FF`; policy, driver,
BSS, private stack, router, all published gates and the resident/shadow map
are unchanged. The shell's revised result handling saves nine code bytes;
those are explicit padding to preserve the established placement.

Disk bytes are read into **unpublished staging** at bank-1 `$0200-$0C0F`
(16-byte header plus at most 2,560 image bytes). Task 2 must be FREE before
any launcher, argument or staging write: STOPPED and ZOMBIE still own memory.
Rejection returns private loader result `$0103` without altering the child's
common launcher. Normal program exits remain eight-bit values with X=0.
Monitor-seeded STOPPED/ZOMBIE tests prove byte preservation of the launcher
and the entire slot/stack; these are ownership fault-injection tests, not
claims of running a child. The existing real SPAWN/EXIT/WAITPID regression
also passes after moving the shared validator.

The complete file must fit staging and reach clean EOF before validation and
copy into live bank-0 APP1. Every opened file is closed, including overflow
and I/O failures. All 38 shared request bytes, including the original sequence,
are restored before entering the program or reporting failure. The existing
foreground backup/restore path preserves retained bank-0 apps. Disk loading
is synchronous: graphics/input polling pauses during the read; this is not
background disk I/O or a new scheduling claim. No graphics-cache memory is
repurposed as disk staging.

## Try it

Build with `distrobox enter my-distrobox -- make -j8 disk-exec-image` in this
worktree. Cold-boot `build/disk-exec/test.d64` (or `.d71` on a compatible drive).

The qualified copies are preserved as
`bench/artifacts/2026-09-30-storage-0.2/udeks-disk-exec.d64` and `.d71`, with
hashed results in `bench/results/2026-09-30-storage-0.2`.

```text
mount 8 /mnt
ls /mnt
/mnt/DISKCOW hello
/mnt/DISKCOW again
/mnt/BADUDEX
/mnt/SHORT
/mnt/DISKCOW recovered
xinit
xclock &
/mnt/DISKCOW graphics
```

The cow should print its argument each time; BADUDEX and SHORT should report
loader errors and leave a usable prompt. Check clock dragging and typing
afterward. Always unmount before changing media. Explicit `/mnt/NAME` only:
bare names still resolve through the existing shell/bootfs path, and `&` does
not make an ordinary disk executable a scheduled background process.

Reproduce automated acceptance with `tools/disk_exec_probe.py` (use `--disk
build/disk-exec/test.d71 --drive 1571` for D71) and
`tools/1986_storage_smoke_build.py --disk-exec --disk build/disk-exec/test.d64`
with the usual `--emulator`, `--roms` and `--output` arguments in my-distrobox.

## Follow-through

After ordinary disk execution is qualified, use the loading path for the shell
and introduce a shell-run startup script for mounts and optional services.
Define the bootstrap source needed to load that shell before normal mounts
exist. Keep bootfs as the migration fallback, not the intended end state.
