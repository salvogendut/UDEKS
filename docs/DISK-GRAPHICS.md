# Disk-loaded graphical applications

Issue [#22](https://github.com/salvogendut/UDEKS/issues/22), branch
`storage-disk-graphics`, follows merged PR #21. Normal D64/D71 images contain
closed SEQ `XCLOCK` and `XWAVE` files: raw UDEX bytes without a PRG prefix.
Neither application is bundled in normal bootfs anymore. Recovery commands,
the recovery shell and preloaded services remain transitional; this is not
yet the final kernel-only boot model.

## Try it

Cold boot a current image (default RC mounts device 8 at `/mnt`), then:

```text
ls /mnt
xclock &
xwave &
```

Move, resize and switch between the windows; type `cowsay hello` in the VDC
console while both run. Stop with `xwave -q`, restart with `xwave` (no `&`),
then press Ctrl+C: the clock should keep running and the prompt return.
Repeat from a cold boot with wave before clock. `xinit` remains optional:
either application initializes the graphical desktop when needed.

First launch needs `/mnt`; without it, the current `request failed` message
returns to a usable prompt. Mount and retry. Stopping does not unload an app;
subsequent starts use the retained image, even if media is removed. Reboot to
test a changed file. Optional automatic startup belongs in disk `RC`:
append `xclock &` and `xwave &` after the default `mount 8 /mnt` line.

## Implementation boundaries

- Existing common gate `$F916` delegates disk read/validation to the private
  bank-1 loader extension. No new public ABI or service placement.
- Clock must target bank-0 `$0200-$0BFF`; wave `$1200-$1BFF`. Each has six
  absolute JMP callbacks; every target must lie after its table and inside
  its own image, not in BSS or the other app. Exact EOF/header/size/BSS and
  flags checks complete before any live destination write.
- Staging borrows bank-1 task 2 only while FREE. Rejected busy loads leave
  that allocation and its common launcher untouched, including STOPPED and
  ZOMBIE ownership. This is a synchronous compatibility loader, not a new
  scheduler, allocator, or arbitrary executable sandbox.
- No app, window-manager, rendering, input-driver or Z80 algorithm changes.
  Existing retained-code, foreground/background and cancellation semantics
  remain. First-load IEC latency is expected; optimization is separate work.
- The failure tail now establishes the CPU zero flag from its nonzero error
  result, not zero X. Otherwise the assembly managed caller could enter old
  slot contents after a missing/invalid file. Negative live tests cover this.

## Repeatable checks

Build with `distrobox enter my-distrobox -- make -j8 boot disk-exec-image panic-probe placement-check`.
Run `make check` on the host, then:

```sh
python3 tools/managed_disk_probe.py --faults --output build/disk-graphics/vice-faults
python3 tools/managed_disk_probe.py --drive 1571 --disk build/boot/udeks.d71 \
  --first xwave --output build/disk-graphics/vice-wave-first
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --emulator /var/home/salvogendut/Dev/1986 \
  --roms /var/home/salvogendut/Dev/1986/roms --disk build/boot/udeks.d64 \
  --disk-shell --sysinfo --disk-graphics --output build/disk-graphics/1986
```

VICE feeds normal terminal key events, checks both launch orders, disk/code
identity, missing mount/media entry, malformed headers/callbacks, atomic
rejection with a running peer, and retained restart without media. The busy
case deliberately seeds STOPPED/ZOMBIE ownership; it is not a native child
creation test. The 1986 harness uses native keyboard/1351 events and raw IEC
against unmodified emulator sources. No physical-hardware acceptance is
inferred from these checks.

## Candidate checkpoint — 2026-09-30

VICE true-drive D64/1541 (clock first, 13 file faults plus busy ownership)
and D71/1571 (wave first) pass. Native 1986 revision `43d7dce` passes raw-IEC
loading, clock drag/resize, wave drag, foreground Ctrl+C, both-app console
use, stop/restart and media recovery. Existing disk-exec, RC-started clock,
free/df and real compiled SPAWN/EXIT/WAITPID regressions pass. A clean parallel
build reproduces both normal disks, the panic disk and the D64 disk-exec fixture
byte-for-byte. The shadow-clear/bitmap check uses mounted disk apps now.

TASKLOADER uses 1,362/1,392 bytes before BOOTINIT; TASKLOOKUP 1,138/1,536.
Normal bootfs now uses 8,016/12,544 bytes. This recovers bootfs content space,
not resident kernel RAM, and does not shrink the fixed secondary envelope.
The app and resident kernel image binaries are unchanged; only loader/delivery changes.
Managed programs must be invoked through `xclock`/`xwave`; explicit
`/mnt/XCLOCK` is not an ordinary foreground executable (its managed flags are
deliberately rejected by that path).

Exact candidate images and records are preserved under
`bench/artifacts/2026-09-30-disk-graphics` and
`bench/results/2026-09-30-disk-graphics`. Manual acceptance of this candidate
in 1986 and/or on hardware is unrecorded. The user subsequently authorized
review/merge and continuation with utility and command-layer extraction;
that authorization is not a physical test result.
