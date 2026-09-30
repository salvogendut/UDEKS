# Command extraction — issue #24

The user authorized three steps in sequence: merge disk graphics, move everyday
utilities to disk, then retire resident command policy. PR #23 is merged at
`2c88e07`; work continues on `boot-disk-commands`, issue #24.

## Step 2: disk utilities

Normal disks contain COWSAY, DATE, LS and CAT as ordinary UDEX SEQ files.
Bare names resolve from mounted `/mnt`, and explicit uppercase DOS paths work.
Normal bootfs has only mount, umount (one small helper image) and recovery ush.
It shrinks from 8,016 to 3,024 bytes; this is bootfs content space, not a new
general RAM allocator. Disk utilities need `mount 8 /mnt` first. `echo`, `cd`,
`pwd` and the recovery shell remain available without a mounted disk.

`tools/disk_commands_probe.py` cold-boots normal or missing-USH recovery disks,
checks both lookup forms, date setting, missing-file messages, coexistence
with both graphical apps, and unmount/remount recovery. Builds preserve old
benchmark/probe-specific bootfs images; normal bootfs has no cow/date/ls/cat.

## Step 3: command/service boundary

Remove the resident name/handler catalog, duplicate builtins and diagnostic
formatting. Keep shell policy in disk ush, diagnostics in disk utilities, and
graphics/engine actions behind bounded numeric service requests. Work that
changes banks or leases the Z80 must run after the bank-1 request stack has
unwound. Preserve the EXEC/WAIT compatibility transport as loader/session
mechanism, not a hard-coded command registry. Do not claim kernel-only boot
while device/window/terminal services are still preloaded.

Qualification: host/ABI tests, bounds/placement and clean builds, true-drive
VICE D64/D71 including recovery, native 1986 pointer/keyboard, compiled tasks,
startup scripts and dual graphics. No rendering or IEC optimization.
