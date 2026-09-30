# Storage 0.1 — external read-only disk

Issue [#15](https://github.com/salvogendut/UDEKS/issues/15). The first user
gate is `mount 8 /mnt`, `ls /mnt`, and `cat /mnt/NAME` from a real disk, with
bootfs and the shell still working when device 8 is absent. This is a feature
milestone, not an IEC speed project. Writes, 1571 burst, a new filesystem
format, and storage-backed UDEX launch belong to later milestones.

## Existing boundary and hardware facts

- Stage 1 uses the inherited KERNAL to load `SCHEDOVR`, then UDEKS does not
  call KERNAL again (`src/boot/stage1.s`; `docs/PLAN.md`). Runtime storage
  therefore needs a native IEC transport, not an unadvertised ROM dependency.
- The current request gateway sends `OPEN`, `GETDENTS`, `STAT`, and `CLOSE`
  to the common-RAM bootfs service. `READ` currently handles stdin only.
  Storage 0.1 must route non-stdio descriptors to a service without changing
  the existing request numbers or growing bootfs policy into the kernel.
- CIA2 port A carries the slow serial lines and also selects the VIC bank.
  IEC output writes must preserve the VIC selection bits, coordinate with
  display ownership, use bounded timeouts, and release bus lines on failure.
  See the [original C128 Programmer's Reference Guide, serial-port
  description](https://www.manualslib.com/manual/1235228/Commodore-128.html?page=643).
- The normal `1986` virtual drive intercepts KERNAL serial calls; it cannot
  qualify a native line-level driver. Its optional ROM-backed 1571CR mode
  models CIA2/IEC lines and requires a valid DOS ROM. See the
  [1986 bus model](https://github.com/salvogendut/1986/blob/39797864231dd0c52431df3ed9b4c724af2d19a9/src/iec_bus.c)
  and [drive selection](https://github.com/salvogendut/1986/blob/39797864231dd0c52431df3ed9b4c724af2d19a9/src/main.c).
  VICE testing likewise needs true-drive/line-level operation; physical
  PI1541 remains the final device gate.

## Directory decoder

`src/services/filesystem/cbm_directory.c` incrementally decodes the
Commodore DOS directory program a byte at a time. Its caller owns the bounded
state, so a storage-service poll can cap received bytes rather than parse the
whole directory at once. It emits file names, block counts and type markers;
the adapter encodes names into the existing explicit-byte `GETDENTS` record
used by `/bin/ls`. Truncated, malformed, or overlong records fail closed.
Names remain raw PETSCII at this layer; the mount service will define any
conversion and path-escaping policy. No production image or syscall is changed
by this component alone.

The host tests include the fixed-width directory layout emitted by the
[1986 virtual drive](https://github.com/salvogendut/1986/blob/39797864231dd0c52431df3ed9b4c724af2d19a9/src/disk_image.c),
zero free blocks, padded and maximum-length names, truncated streams,
explicit termination, and the 24-byte `GETDENTS` envelope. The source also
compiles under the reference cc65 toolchain; it is service code, **not**
resident-kernel code.

## Native IEC transport qualification

`src/services/filesystem/iec_slow.s` implements a private 8502 slow-serial
transport for directory channel 0 and named-file channel 2 on devices 8–11.
The file operation accepts a service-owned 1–16-byte PETSCII filename and
uses the same bounded `READ`/`CLOSE` operations. It uses no KERNAL
vectors: line writes preserve CIA2's live VIC bank bits; waits are finite;
receive-byte IRQ masking covers the entire clock/data handshake; and each
transaction selects 1 MHz, then restores the prior CPU speed and releases
ATN/CLK/DATA on close or failure. A future storage service must serialize
ownership of CIA2 and
the CPU-speed register before linking this transport into UDEKS.

`make iec-probe` builds this same transport into a standalone raw-load PRG.
`make iec-vice-probe` creates a **non-autoboot** D64 in `build/`, reads its
directory through VICE true-drive 1571 and 1541 models, compares the exact
directory streams, reads and compares 32 and 512 bytes of a named on-disk PRG
through channel 2, reads a complete short file through EOI, and checks that
an absent device returns `NO_DEVICE` with the bus released and CPU speed
restored. The probe forces 2 MHz before open
to prove the transport's 1 MHz selection and restoration. The first live
VICE 1571 directory capture is also a host decoder regression fixture.
These are line-level runs, not VICE's KERNAL disk traps.
The 512-byte PRG probe crosses a sector boundary and the 12-byte text fixture
tests file EOI. Longer files, error-channel status (including missing files),
and media changes still need qualification before `cat` can rely on them.
An earlier receiver intermittently timed out after 4–5 bits of a byte on the
1541 model. Longer waits did not fix it; masking
IRQs for the complete receive handshake, matching the
[original C128 KERNAL serial routine](https://github.com/mist64/cbmsrc/blob/master/KERNAL_C128_05/serial.src),
passed three independent complete VICE runs on both drive models; the later
short-file and sector-boundary probe passed once. The decoder
retains the live bit counter at result offset 17 on read failure. This
qualifies the bounded VICE samples, not real hardware or the `/mnt` request
path.
Build the PRG in the reference container with
`distrobox enter my-distrobox -- make iec-probe`, then run
`make iec-vice-probe` on the host with the VICE Flatpak installed.

The standalone probe is **not** a bootable UDEKS mount test. It validates
the transport and parser separately; nonresident service placement, request
routing, and shell commands are still missing. `1986`'s ROM-backed raw IEC
mode and physical C128 + PI1541 remain unqualified.

## Shortest path to Storage 0.1

1. **Bootable service:** reserve and link a nonresident C storage service with
   its own runtime context. Route `/mnt` requests to it through the existing
   task-request boundary, preserving bootfs for all other paths and when no
   disk is present. First gate: `mount 8 /mnt` then `ls /mnt` in VICE.
2. **Useful files:** connect `OPEN`/`GETDENTS`/`READ`/`CLOSE`, add `umount` and
   `cat`, and make `ls -l` use the selected path. Handle PETSCII names,
   missing files, EOI, timeouts, and media errors without stranding the bus.
   Gate: `cat /mnt/HELLO` prints the disk file and returns to the prompt.
3. **Qualify the workflow:** test bootfs fallback and graphics-active VIC bank
   preservation on D64/D71 in VICE and `1986` raw-IEC mode, then on a
   physical C128 + PI1541. Storage 0.1 is complete only after these pass.

Storage-backed UDEX loading is the subsequent Storage 0.2 milestone. The
directory decoder and native IEC transport are real service ingredients, but they
are **not** a completed mount or an image ready for manual testing.
