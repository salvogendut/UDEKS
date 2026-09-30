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
- The request gateway now routes `/mnt` and descriptor 4 to a private bank-1
  C service, retaining common-RAM bootfs as the fallback. Directory operations
  and ABI 0.5 mount/unmount plus named-file reads are exposed by shell commands.
  No device policy was added to the
  resident C link.
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

## Directory decoder (original formatted-stream path)

This decoder remains host-tested and used by the standalone transport probe.
The runtime service now uses the raw sector-chain reader described below;
formatted directory listings cannot provide the exact byte length needed to
fix zero/one-byte DOS stream EOF.

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
ATN/CLK/DATA on close or failure. The initial native service serializes CIA2
and CPU-speed ownership with a synchronous IRQ-masked call. It does not yet
promise responsive input or graphics during a disk transaction.

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
tests file EOI. Later native-service and shell probes below cover longer files
and missing-file status. Media changes still need qualification.
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

The standalone probe is **not** a bootable UDEKS mount test. It validates the
transport and parser separately. The following native service gate now covers
placement and request routing; the later interactive gate covers shell
commands. `1986`'s ROM-backed raw IEC keyboard workflow now passes;
physical C128 + PI1541 remains unqualified for this storage path.

## Native service checkpoint — 2026-09-30

`iec_service.c` provides read-only mount/unmount, directory and file reads via
the existing `$CF30`/`$FF16` request boundary (ABI 0.5). The service has its own
cc65 runtime, saves/restores caller zero page, and makes no KERNAL calls.

| Runtime region | Owner |
| --- | --- |
| Bank 1 `$1200-$1FFF` | Service entry, sector-chain reader and C helpers |
| Bank 1 `$8A00-$8FFF` | C mount/handle/request policy |
| Bank 1 `$9A00-$9FFF` | IEC assembly driver; ush image+BSS must end below it |
| Bank 1 `$E000-$E0FF` | Service BSS (111 bytes currently) |
| Bank 1 `$E100-$E1FF` | Private C stack, top `$E200` |
| Bank 0 `$C880-$C8FF` | 75-byte routing/overlay stub, after scheduler BSS |
| Common `$F68A-$F6B3` | 42-byte temporary bank-switch code; below transient stack |

The linker bounds each piece. The secondary `SCHEDOVR` boot file delivers
them in the gaps around existing owners; its padded envelope is larger and
may increase real-hardware boot time. Scheduler/cache source bounds remain
distinct from the envelope's load/end bounds. Neither the resident layout,
VIC shadow, app slots, graphics cache, nor ush stack moves. Delivery rejects
an oversized ush, service, or scheduler overlap. The router invalidates the
VIC overlay lease and restores kernel mapping/context before any fallback.

`python3 tools/storage_service_probe.py` boots the real D64 with VICE's
true-drive 1541 and starts `xinit` plus `xclock &`. A debugger harness then
calls the real request gate to test absent-address failure, mount, directory
entries/EOF, busy-unmount rejection, close/unmount, and bootfs fallback. It
checks the VIC bitmap and caller C context. Use `--disk build/boot/udeks.d71
--drive 1571 --output build/storage/vice-1571` for the other format. Sessions
are private and automatically terminated; the input disk is never modified.
This harness takes over the CPU, so it does **not** certify returning to an
interactive shell after storage I/O or responsiveness during a request.

## Interactive file checkpoint — 2026-09-30

The normal native D64/D71 include transient `/bin/ls`, `/bin/cat`,
`/bin/mount`, and `/bin/umount`. These directory names reference one C multicall UDEX image, using the published
request ABI; no command policy was added to the resident shell. Bootfs is
delivered directly in the existing secondary file at bank-1 `$A000-$D0FF`,
removing its old 11,708-byte staging limit without dropping a program. Its
12,544-byte **runtime** limit still applies: 12,307 bytes are used. Sharing
the 2,506-byte executable keeps every previous command without enlarging
bootfs into task contexts. The service and multicall command use cc65 static
locals, are synchronous/nonrecursive, and remain separately linked modules.

Build with `distrobox enter my-distrobox -- make -j8 boot`. From a normal
boot with the disk attached to device 8, try:

```text
mount 8 /mnt
ls /mnt
cat /mnt/HELLO
cat /mnt/NOFILE
cat /mnt/HELLO
umount /mnt
ls /bin
```

`ls /mnt` should show `SCHEDOVR` and `HELLO` on the boot disk. The first
`cat` prints `HELLO UDEKS`; the missing file reports
`cat: No such file or directory`, and
the next read still succeeds. Successful mount/unmount
are silent and return the prompt. Repeat with `xinit`, `xclock &`, and
`xwave &` active. An unused device (for example `mount 11 /mnt`) should
report failure and return control; mounting an already mounted `/mnt` fails.
After unmounting, `ls /mnt` fails while `ls /bin` still works.

`make storage-shell-probe` on the host automates that workflow on VICE's
true-drive 1541/D64 and 1571/D71. It adds extra fixtures only to disposable disk
copies, feeds terminal keyboard events including Return, and requires the
input cursor plus ush's WAITING/INPUT state after every command. It checks
transient exit status, listing/file contents, remount/error paths, bootfs, and
both apps' running states. It does not take over the CPU. Logs, disk hashes,
and screenshots are saved under `build/storage/shell-{1541,1571}`; private
VICE sessions are terminated on success or failure.

The tests include a multi-sector text file, both PETSCII uppercase alphabets,
missing-file recovery, and output without a final newline. `cat` sends the
explicit file bytes to stdout without adding a newline; the terminal starts
its next prompt on a fresh row when necessary. A host test covers all cursor
positions, including scrolling. This prompt fix saves six resident CODE
bytes; six reserved bytes retain the qualified shadow/scheduler placement.

`storage_service_probe.py` additionally compares 2-, 24-, and 515-byte file
streams exactly, including embedded NULs, 24-byte request boundaries, the
last EOI byte, repeated EOF and sector transitions. It verifies caller
zero-page/software-stack preservation and unchanged VIC bitmap. Host tests
cover partial-read errors, invalid filenames, operation validation and
byte-exact multicall output. File-open policy checks DOS channel 15, maps
missing files to `ENOENT`, and closes channels on error. Recovery commands
reselect 1 MHz even when a failed transfer already restored the caller speed.

### 1986 setup and independent check

Use ROM-backed real-drive mode (`real_disk_drive=1`) and a valid 1571CR ROM.
In sibling revision `3979786`, **quit and reopen 1986 after changing that
setting**: F5/Ctrl+F5 does not reconfigure `drive_raw_iec`. The user confirmed
the earlier mount/list image worked after a full application restart.
The native raw-IEC harness now passes mount/list/cat/missing-file/unmount
using normal keyboard input and unmodified sibling sources:

```sh
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --emulator /var/home/salvogendut/Dev/1986 \
  --roms /var/home/salvogendut/Dev/1986/roms
```

It copies the disk before use and saves `build/storage/1986/run.log` plus a
snapshot. It does not use KERNAL traps or certify physical drive behavior.

### Remaining gates

- Physical C128 + PI1541 is the remaining release gate; see the hardware
  checklist below. Automated tests cover the finite cases recorded here, not
  every drive fault or every damaged disk.
- Always unmount before exchanging media. Removal during a read is tested to
  fail and recover, but an undetected swap during a live handle is not a
  supported workflow. No automatic media-generation detector is claimed.
- Only absolute `/mnt/NAME` file paths are supported. Names have the restricted
  mapping in [the request ABI](../abi/task-request.md#read-only-iec-mount-05).
  `cd /mnt`, per-file byte-size metadata and storage-backed program loading
  are not implemented. `ls -l /mnt` prints `?` for unknown sizes rather than
  accidentally looking up a namesake in bootfs.
- The driver is synchronous and IRQ-masked; disk I/O can pause input/graphics.
  There is no write support or storage cancellation yet. The boot banner's
  historical `STORAGE/FILESYSTEM SERVICES: DEFERRED` wording is also still due
  for correction; runtime commands, not that banner, describe this checkpoint.

**Merge update (2026-09-30):** PR #17 merged by explicit user authorization
as `92a2e36`. Physical C128 + PI1541 qualification is still unrecorded;
the preserved hardware images remain available for that test. Issue #18 now
implements the first disk-execution slice.
Storage 0.2 disk-backed program loading is the next feature, not IEC optimization.

### Byte-accurate EOF and media recovery — 2026-09-30

The stock C128 KERNAL reproduces the same error as the old reader on VICE's
true 1541 and 1571 ROM paths: a one-byte SEQ produces four bytes, a zero-byte
SEQ produces 254 bytes, and two bytes read correctly. `make iec-eof-reference`
builds the isolated reference PRG; `tools/iec_eof_reference.py --drive 1541`
(or `1571`) reproduces this without UDEKS. Prefetching data before reading DOS
status did not fix it. The reference is evidence for these fixtures, not a
claim about all DOS versions or a physical-hardware result.

`cbm_file.c` now opens a private `#` buffer and issues the documented read-only
`U1:2 0 track sector` command. It streams sectors without allocating a 256-byte
buffer on the C128. It checks DOS status after every U1, parses raw directory
entries, and uses the final sector's count minus one as the exact payload
length. No padding is guessed or silently trimmed. File types, counts, sector
geometry and chain bounds are validated; errors are sticky until close.
No disk writes, drive-memory patches, new kernel policy or moved memory slots
are involved. The formatted-directory decoder remains available to benchmarks.

The native service probe with `--tiny-files --media-recovery` passes on VICE
1541/D64 and 1571/D71: exact reads of 0, 1, 2, 24, 255 and 515 bytes;
repeated EOF; removal during a read (254 already-buffered bytes, then EIO);
absent-media mount failure; replacement-disk data without stale bytes; unchanged
caller context and VIC bitmap. The immediate remount requires one retry in
both debugger runs. The normal-keyboard shell probes pass empty/one-byte reads,
missing-file diagnostics, removal/reinsertion, bootfs fallback, and commands
while xclock/xwave run. These are correctness gates, not performance claims.

### Hardware checklist

Use `build/storage/hardware/udeks-storage-test.d64` on PI1541 in full emulation
mode (the image includes EMPTY and ONE test files). Cold-boot it as you did the
previous working D64. In the VDC console:

```text
mount 8 /mnt
ls /mnt
cat /mnt/HELLO
cat /mnt/EMPTY
cat /mnt/ONE
cat /mnt/NOFILE
cat /mnt/HELLO
umount /mnt
ls /bin
```

HELLO prints `HELLO UDEKS`, EMPTY prints nothing, ONE prints exactly `X`, and
NOFILE reports `No such file or directory`; each returns a usable prompt.
Repeat HELLO/EMPTY/ONE with `xinit`, `xclock &` and `xwave &` active, then check
pointer, dragging and console typing. Unmount, eject/deselect the image on
PI1541, try mounting (must fail and return), reselect it, and mount/read again.
If the drive is still busy, retry the mount after it settles. Do not physically
unplug IEC cables while powered. Report any reset, frozen prompt, extra bytes
or failed recovery. Merge remains blocked until this test passes.

Initial file-read checkpoint, before the diagnostic follow-up below:
871 host tests pass, normal/panic images build,
placement and staging audits pass, and the shadow probe passes (8,000-byte
clear, installed scheduler tail and VIC bitmap equality). Final shell and
byte-stream probes pass on VICE 1541/D64 and 1571/D71; the normal keyboard
workflow passes in 1986 raw-IEC mode. These claims exclude the separately
recorded tiny-file reproducer and physical hardware. Image hashes:

```text
22bd260de7c340a5876e917e3c17b6d6d4a38a86f4d06a2f21512a404069b490  udeks.d64
0af5d77bc6e7891e734e8a9533da1ae7595d802e1ce93f0c34f18e20e0c95f7e  udeks.d71
```

Diagnostic follow-up: `cat` now exposes `ENOENT` as `No such file or directory`
on stderr, with exit status 1; other open failures are not mislabelled as
missing files. Overlong paths set `EINVAL` before returning locally, so they
cannot reuse an earlier request's error. The VICE 1541/D64 shell sequence
passes with the new wording, successful reads after failure, and both
graphics apps active. Both disk formats have been rebuilt; the kernel and
storage driver are unchanged. Follow-up image hashes:

```text
003acf92fba1b8eaba96445966e7a7b4f69c56074a81070498fe26a416e63be4  udeks.d64
a9ac2aa2a10890897b1f4c47e3f23f5739c16e621029b65c5bfead5bb0bd0321  udeks.d71
```

## Shortest path to Storage 0.1

1. **Bootable service:** reserve and link a nonresident C storage service with
   its own runtime context. Route `/mnt` requests to it through the existing
   task-request boundary, preserving bootfs for all other paths and when no
   disk is present. First gate: `mount 8 /mnt` then `ls /mnt` in VICE.
2. **Useful files:** connect named-file `OPEN`/`READ`/`CLOSE`, add `cat`,
   and make `ls -l` use the selected path. Handle PETSCII names,
   missing files, EOI, timeouts, and media errors without stranding the bus.
   Gate: `cat /mnt/HELLO` prints the disk file and returns to the prompt.
3. **Qualify the workflow:** test bootfs fallback and graphics-active VIC bank
   preservation on D64/D71 in VICE and `1986` raw-IEC mode, then on a
   physical C128 + PI1541. Storage 0.1 is complete only after these pass.

Storage-backed UDEX loading is the subsequent Storage 0.2 milestone. The
file-reading slice is ready for manual testing; the remaining EOF and
machine/device gates are still needed to complete Storage 0.1.
