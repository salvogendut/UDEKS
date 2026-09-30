# Command extraction — issue #24

The user authorized three steps in sequence: merge disk graphics, move everyday
utilities to disk, then retire resident command policy. PR #23 is merged at
`2c88e07`; work continues on `boot-disk-commands`, issue #24.

## Step 2: disk utilities

Normal disks contain COWSAY, DATE, LS and CAT as ordinary UDEX SEQ files.
Bare names resolve from mounted `/mnt`, and explicit uppercase DOS paths work.
Normal bootfs has only mount, umount (one small helper image) and recovery ush.
Step 2 shrank it from 8,016 to 3,024 bytes; step 3's larger recovery shell
brings it to 3,797 bytes. This is bootfs content space, not a new
general RAM allocator. Disk utilities need `mount 8 /mnt` first. `echo`, `cd`,
`pwd` and the recovery shell remain available without a mounted disk.

`tools/disk_commands_probe.py` cold-boots normal or missing-USH recovery disks,
checks both lookup forms, date setting, missing-file messages, coexistence
with both graphical apps, and unmount/remount recovery. Builds preserve old
benchmark/probe-specific bootfs images; normal bootfs has no cow/date/ls/cat.

## Step 3: command/service boundary

The resident name/handler catalog, duplicate builtins and diagnostic
formatting are removed. Shell policy lives in disk ush, diagnostics in an
ordinary UNAME/LSHW/LSMOD/LSCPU/Z80CTL multicall image, and
graphics/engine actions cross bounded numeric CONTROL requests (UTRQ 0.7). Work that
changes banks or leases the Z80 must run after the bank-1 request stack has
unwound. Preserve the EXEC/WAIT compatibility transport as loader/session
mechanism, not a hard-coded command registry. Do not claim kernel-only boot
while device/window/terminal services are still preloaded.

Qualification passes: host/ABI tests, bounds/placement and byte-identical clean
parallel builds, true-drive VICE D64/D71 including recovery, native 1986
pointer/keyboard, compiled tasks, startup scripts, malformed disk/managed
program rejection and dual graphics. See the
[preserved evidence](../bench/results/2026-09-30-disk-commands/README.md).
No rendering or IEC optimization.

The compatibility session still owns generic EXEC tokenization/loading, job
ownership and generic loader-error output. It contains no builtin catalog or
CLI option handling. It is not a general process manager or IPC replacement.
ush owns prompt rearming; this also prevents extra prompts between RC commands.

VICSHADOW remains exactly 8,000 bytes at `$A1E0-$C11F`, preserving all frozen
delivery/overlay addresses. Shrinking resident CODE/RODATA leaves an unused
gap before it; placement checks reject overlap and still enforce all service
and gateway reservations plus normal/panic parity. The gap is not a heap and
`free` correctly does not report it as allocatable memory.

The filesystem remains standard read-only CBM DOS (D64/D71), not a UDEKS
disk format. Current single-mount command lookup has a practical limitation:
ls/cat and other disk utilities must themselves exist on the mounted command
medium. Separating a system-command volume from arbitrary data disks is a
future multi-volume/path feature; UDEX executables are not required for the
storage service to read ordinary data files.

## Test the candidate

Cold boot `build/boot/udeks.d64` from this worktree (D71 for a 1571):

```text
help
mount 8 /mnt
ls /mnt
uname -a
lshw
lscpu
z80ctl test
xinit
xclock &
xwave &
cowsay hello
date 123456
df
```

Drag/focus both windows and type in the console. Then `xwave -q`, `xwave`
(without `&`), Ctrl+C: the clock must remain running and the prompt must return.
`xinit -q` must stop the desktop and both apps. `umount /mnt` followed by
`echo recovery alive` and `mount 8 /mnt` verifies recovery. Disk utilities
are intentionally unavailable while unmounted; this includes ls and uname.
Mount and umount remain usable without an external executable file.

There is no new real-hardware acceptance for this candidate yet. Earlier
accepted images and archived evidence are unchanged.
