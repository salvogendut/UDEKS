# UDEKS service-module ABI 0.1

## Disk-time candidate — issue #49 (2026-10-08)

The first extraction target is the **time-of-day service**, not the scheduler's
monotonic tick counter. Its C start/poll logic, assembly clock setting and BASIC
`TI` synchronization now build as an independent `build/services/time/TIME.SVC`.
This is a **candidate only, not installed or enabled by normal boot**. Do not
load it into a running baseline: its provisional `$9300` address overlaps live
resident state in that build.

The module links its own required cc65 code helpers; it does not import private
kernel function addresses or require a kernel-map-generated bridge. The fixed
runtime zero-page layout matches UAPP 0.1 (`sp=$06`, `ptr1=$0e`, `tmp1=$16`,
`regbank=$1a`). Calls must be serialized in the root context with its software
stack, binary arithmetic mode and kernel-I/O map. IRQ scheduling must neither
call the module nor depend on its lifetime. This is a loadable service module,
not a new independently scheduled task or a memory-protection boundary.

### Candidate image contract (not frozen)

All words are little-endian. The disk file has no BASIC/PRG load-address prefix.

| Offset | Bytes | Meaning |
| --- | --- | --- |
| 0 | 4 | `USVM` image magic |
| 4 | 2 | Image ABI 0.1, implicitly 8502/cc65 root-context execution |
| 6 | 2 | Class 4, instance 1 (time of day) |
| 8 | 2 | Proposed load address |
| 10 | 2 | Complete emitted image size, including this header |
| 12 | 2 | Zero-initialized BSS immediately after the image |
| 14 | 2 | Flags, currently zero |
| 16 | 2 | Sum of all emitted bytes except this word, modulo 65536 |
| 18 | 2 | Nonzero module revision, distinct from ABI version |
| 20 | 2 | Class-specific request entry: clock set, A=hour/X=minute/Y=second |
| 22 | 10 | Reserved, zero |
| 32 | 16 | Existing `USVC` descriptor; flags zero and start/poll/stop required |
| 48 | variable | Code, constants, initialized data and private runtime helpers |

The independent host validator rejects wrong identity/version, reserved bits,
truncation/trailing bytes, overflow, bad checksums and vectors pointing outside
emitted code (including header/BSS). It never mutates its input. The checksum
detects accidental corruption, not malicious code. Runtime validation and
registration are **not implemented by this host validator**.

### Placement and lifetime gate

The measured image is **797 bytes plus 10 BSS bytes**, including its 48-byte
header and independent runtime helpers. The compatibility kernel currently
uses 531 bytes for `time.o` and 248 for the setter/TI assembly. Extraction alone
therefore does not pay for the image format, private helpers and dispatch glue.

A compile-only split identifies **518 startup-only registry bytes**, leaving
223 bytes of live registry code and the same 8-byte shared registry BSS.
The proposed lifetime is to place those startup instructions in the future
module reservation, then replace them only after startup has permanently
retired. The guarded/irreversible one-shot entry is a prerequisite; checking
only a mutable READY diagnostic is not sufficient. The module must not load
from inside a still-active startup frame.

`make time-module-placement` checks the real objects and normal/panic maps.
At the provisional `$9300-$96a7` slot it budgets **at most 364 new resident
bytes** after the measured extraction, before the actual manager, wrappers,
state and permanent guard are linked. That is an accounting ceiling, **not a
successful resident-integration link**. No application slot, stack guard,
VDC asset, VIC shadow or common-RAM gateway has moved. The normal startup
split is disabled; both the old time service and original boot lifecycle remain.

### Remaining integration and acceptance

1. Link the real startup overlay, irreversible guard and callable-entry
   dispatch within the measured budget. Retain frozen public clock vectors.
2. Use a disk-side loader/control command and the existing bounded `/etc/rc`
   runner. Validate the complete image and placement before publishing any
   callable entry; initialize BSS, run start, then publish READY. Rejection or
   interrupted loading must leave the module offline and the shell usable.
3. Define stop/duplicate-load/client behavior: never overwrite executing code,
   invalidate the time snapshot when unavailable, and make `date`/`xclock`
   handle unavailability rather than consume stale time. Scheduler sleep and
   deadlines continue independently. Qualify missing/corrupt files, restart,
   replacement without kernel relink, and normal input/disk/graphics behavior
   on VICE/1986 before offering physical-C128 test images.

Reproduce the current independent proof in `my-distrobox`:
`make time-module time-module-check time-module-placement`.
The exact sealed image runs under sim6502 through all 86,400 times of day;
173,433 entry calls check read/set/TI/BCD behavior, start/stop/restart, software
stack balance, image/BSS guards and non-mutating invalid-set rejection. An
altered range-check instruction is detected by a negative-control run. The
simulator uses RAM-backed CIA addresses: this is **not** hardware TOD latching,
interrupt, disk-loading or C128/VICE qualification. The normal D64/D71/D81
builds remain byte-identical to merged PR #48.

## Existing static descriptor contract

UDEKS services are discovered through compiler-neutral 16-byte descriptors.
The format is byte-oriented and little-endian; it is not a C structure.

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `USVC` |
| 4 | 1 | ABI major version (`0`) |
| 5 | 1 | ABI minor version (`1`) |
| 6 | 1 | Service class |
| 7 | 1 | Instance number within the class |
| 8 | 1 | Flags |
| 9 | 1 | Descriptor size (`16`) |
| 10 | 2 | Start-vector address; mandatory |
| 12 | 2 | Poll-vector address; zero if unsupported |
| 14 | 2 | Stop-vector address; zero if unsupported |

Lifecycle vectors use the cc65 C calling convention, take no arguments, and
return an eight-bit result in `.A`. Zero means success. A module publishes its
own versioned request interface separately; the lifecycle ABI does not expose
private module functions.

The initial flags are:

- bit 0: resident for the lifetime of the kernel;
- bit 1: critical to system bring-up.

Initial service classes are console (`1`), hardware capability discovery
(`2`), display (`3`), machine policy/time (`4`), input (`5`), terminal policy
(`6`), native shell (`7`), bounded Z80 worker (`8`), window manager (`9`),
managed-application dispatcher (`10`), and init/session policy (`11`).
The default image starts capability discovery, CIA time, the Z80 worker, VDC
text console, pointer input, the VIC-IIe graphics service, window manager,
keyboard, root-terminal policy, the managed-app dispatcher, and init in that
order. Init loads and polls `/bin/ush` while retaining the resident shell only
as a compatibility dispatcher for commands not yet extracted. The system remains at 1 MHz so
the VIC-IIe stays available.
The machine-clock and VDC framebuffer descriptors remain optional modules:
2 MHz requires an explicit VIC-blanking policy, and VDC bitmap mode requires
explicit display ownership. The VIC-IIe service is display class `3`, instance
`1`; startup is passive and `xinit` performs explicit mode acquisition.
The resident CIA time service is machine-policy class `4`, instance `1`; the
older optional machine-clock descriptor is the separate VIC-blanking 2 MHz
transition.

The display service's provisional resident-C request surface is specified in
the [framebuffer client API](framebuffer.md). It is not yet a compiler-neutral
or cross-CPU service request ABI.

The first terminal-policy instance consumes the keyboard FIFO after the input
service has polled and edits the fixed-focus root console. Its provisional API
and diagnostics are specified in the [line-editor contract](line-editor.md).

Input class instance `1` reserves control port 1 for a 1351 mouse and control
port 2 for a joystick, publishing their combined state through the
[pointer-input contract](pointer-input.md). It polls before input class instance
`0` scans the shared CIA keyboard matrix.

The static image emits descriptors and a pointer table in assembly so vector
addresses are linker-resolved without relying on compiler packing. The C
registry validates every descriptor before invoking it. Future disk-loaded
modules must submit the same bytes to the same validation path before being
registered.

Static linking during bring-up does not merge module responsibilities. ADR
0007 now makes this placement explicitly transitional and forbids adding new
policy or applications to the resident image. The
VIC-IIe display module owns hardware state and its 8502 assembly transport;
the window module owns composition and pointer policy; `xclock` and `xwave`
are standalone UDEX applications. A compact class-10 dispatcher loads them on
first use and calls their fixed lifecycle tables until a general scheduler
replaces the retained slots.

The registry publishes this 24-byte `SREG` diagnostic record at `$F090`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `SREG` |
| 4 | 1 | Status format (`1`) |
| 5 | 1 | State: starting (`1`), ready (`2`), or error (`$80 | code`) |
| 6 | 1 | Failure code, zero on success |
| 7 | 1 | Descriptors discovered |
| 8 | 1 | Services started |
| 9 | 1 | Services failed |
| 10 | 1 | Last service class |
| 11 | 1 | Last service instance |
| 12 | 1 | Last start result |
| 13 | 1 | Registry ABI major |
| 14 | 1 | Registry ABI minor |
| 15 | 1 | Last descriptor size |
| 16 | 1 | Last service flags |
| 17 | 1 | Static table count |
| 18–19 | 2 | Completed poll passes, little-endian |
| 20 | 1 | Index of the last service whose poll failed |
| 21 | 1 | Last nonzero poll result |
| 22 | 1 | Poll failures |
| 23 | 1 | Poll vectors invoked during the latest completed or failed pass |

Failure codes distinguish an empty table, invalid magic/version/size/class,
a missing start vector, and a start function that returned an error. The
decoder intentionally rejects inconsistent table, discovery, and started
counts even when the state byte says ready.

ABI 0.1 now invokes nonzero poll vectors cooperatively after all services have
started. A poll uses the same no-argument, eight-bit-result convention as
startup; a nonzero result fails the registry and enters the panic path. Stop
vectors, scheduling cadence, and unload semantics remain provisional.
