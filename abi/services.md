# UDEKS service-module ABI 0.1

## Disk-time candidate — issue #49 (2026-10-08)

The first extraction target is the **time-of-day service**, not the scheduler's
monotonic tick counter. Its C start/poll logic, assembly clock setting and BASIC
`TI` synchronization now build as an independent `build/services/time/TIME.SVC`.
As of 2026-10-09 it is **loaded by normal boot** through `/etc/rc`; the old
resident implementation is no longer linked. Older kernels without the
operation-28 capability must not load this image: `$93D0` was live resident
memory there. The disk loader probes support before touching the slot.

The module links its own required cc65 code helpers; it does not import private
kernel function addresses or require a kernel-map-generated bridge. The fixed
runtime zero-page layout matches UAPP 0.1 (`sp=$06`, `ptr1=$0e`, `tmp1=$16`,
`regbank=$1a`). Calls must be serialized in the root context with a valid
bounded software stack, binary arithmetic mode and kernel-I/O map. The console
SDK temporarily binds that root ZP layout to the foreground caller's stack,
then restores its private runtime. IRQ scheduling must neither
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
registration are **not implemented by this host validator**; the separately
CPU-tested core below enforces them at the real request gate in normal boot.

### Candidate lifecycle core (not a published ABI)

`src/services/module/time_slot.s` implements one bounded slot. Its internal
control operations are status/no-op, begin, commit and stop. Commit receives
the actual transferred byte count separately from the header, rejects partial
or trailing data, validates every header/vector/checksum field, clears only
the declared BSS, caches validated vectors, runs start, and publishes last.
The standalone disk loader bounds every write; this core cannot undo an
out-of-bounds write performed before commit. The candidate request boundary
and trusted retirement hook now enforce foreground ownership and cleanup.

Loading/unavailable slots cannot execute a time request or poll callback.
Duplicate begin/published commit is busy. Malformed commit retires the load to
offline without executing code or changing CIA registers. Stop invalidates the
snapshot even if the callback fails; a poll failure unpublishes the optional
service and marks its snapshot erroneous, rather than panicking the kernel.
The scheduler's tick source is unrelated. Cached vectors avoid redispatching
through a subsequently modified header; this is not protection against code
writing arbitrary RAM on a machine without an MPU.

The normal boot's startup veneer now uses a private permanent latch instead
of public `SREG` diagnostics: 0=not attempted, 1=inside startup, 2=returned.
Both successful and failed first results are cached. Re-entry during phase 1
returns nonzero; later calls never enter retired startup instructions, even
with damaged diagnostics or an unusable cc65 software stack. Module begin is
permitted only after phase 2 with a successful result. The veneer, manager and
startup overlay are all production-linked in the default disk-time build.

### Candidate request and disk command

`UDEKS_DISK_TIME` adds **UTRQ 0.19, operation 28** behind the unchanged `$CF30`
entry. Descriptor and flags must be zero; count is exactly 3. Payload byte 0
is action **0 status, 1 begin, 2 commit, 3 stop**; bytes 1–2 are the actual
received file length (LE), used by commit and ignored by the other actions.
Success is COMPLETE, result 1, errno 0, with payload[0] holding state 0 offline,
1 loading or 2 published. The other payload bytes are not returned data.
Sequence is preserved. Errors use the existing ERROR/result-zero/errno shape.

Only a synchronous foreground invocation is accepted: the router derives tag
9 from current native task **0** plus the trusted running-foreground state.
Native tasks, root bootstrap/no foreground, and corrupt native IDs are denied
with EINVAL; no caller-supplied owner field is consulted. Wrong count, reserved
fields, action, state transition or operation-specific version is EINVAL;
unsupported envelope/signature/state/version is EPROTO. Startup not yet retired
successfully is EAGAIN; duplicate loading/published installation is EBUSY;
malformed image is ENOEXEC; callback failure is EIO. Existing operations keep
their former routing. This is trusted code/lifetime ownership, not protection
from arbitrary memory writes by a malicious program.

There can be only one such foreground invocation at a time. Its trusted tag-9
retirement at `$C883` aborts a loading lease before allocation reuse. Other
retirements leave it alone; a successfully published service survives its
loader's exit. No new task, sleep or blocking request is introduced. A hung
foreground program still needs the existing reset/recovery path—retirement
cleanup does not turn it into a cancellable native task.

`make service-command` builds independent **`SVC.BIN` (2,198 file bytes,
2,182 payload + 69 BSS)** within the existing 2,560-byte console allocation:
`svc status`, `svc stop`, and `svc load [FILE]` (default `/TIME.SVC`). The file
is an ordinary flat-disk file; no new suffix directory mapping is needed.
The command probes support before touching the slot, opens read-only, obtains
the lease, bounds every chunk, requires clean EOF **and successful CLOSE**,
then commits the actual length. It never retries disk errors, preserves the
first error while closing/aborting, and cannot replace a published service
without an explicit stop. The kernel independently validates before execution.

The SDK preserves `$02-$1F` (does not write CPU ports `$00/$01`), maps its
private `sp=$02` to module `sp=$06` for the synchronous call, normalizes D,
and restores the caller's runtime/decimal flag afterward. It validates reply
sequence, result and state. Direct raw requests need the same valid root-layout
runtime; passing ordinary console ZP directly to a C callback is unsafe.
The command/SDK have no private kernel-map imports.

### Placement and lifetime gate

The measured image is **710 bytes plus 7 BSS bytes**, including its 48-byte
header and independent runtime helpers. Fixed-field counters and a byte-valued
BCD lookup keep its implementation in C while avoiding unnecessary generic
pointer arithmetic/multiply helpers. Conversion still occurs between the TOD
hours latch and the final tenths read. This independent module is now the
normal time implementation; scheduler ticks remain outside its lifetime.

`make service-layout-check` (also `time-module-placement` / `time-overlay-check`)
qualifies the **actual normal/panic kernel links**, including compatibility
wrappers, request handling and library selection. Both variants place resident
BSS through `$93CD`, leaving **2 bytes** before the candidate slot `$93D0-$96A7`.
The manager is 479 CODE + 20 RODATA + 1 BSS = **500 bytes**, plus the explicitly
retained **57-byte C clock-read wrapper**. The independent module uses 717 of
the slot's 728 bytes, leaving 11. These sizes supersede the old `$9300`/548-byte
manager estimate and its 174-byte deficit at checkpoint `ed7a1f7`. The new
request adapter consumes 48 of the 50 bytes qualified at `9e56af5`. Two tiny
internal leaves occupy existing `$CF33-$CF3F` / `$CF43-$CF4F` vector padding;
all published entries and the SYSCALLS reservation stay fixed. The candidate
ownership/retirement router uses 101 of its existing 128 bytes at `$C880`.

`SERVICEBOOT` really links at `$93D0-$95D5`: **518 startup-only registry bytes**,
with 223 live registry bytes and unchanged shared registry state. Only after
startup's private latch indicates returned-success may loading overwrite this
code. Checking mutable READY diagnostics or loading from an active startup
frame remains forbidden. Cached poll/set/stop vectors are published only after
validation and successful start; start itself runs directly through the freshly
validated header while execution is serialized.

The linker asserts the resident/overlay/VDC bounds. A real negative link
adding one byte too much BSS fails; map checks also reject changes to any app,
stack, VIC, VDC, zero-page or common-RAM reservation. `$CF40` and `$CF60` retain
their published JMP addresses and conventions. The provisional base is not a
frozen new external ABI.

Normal `make boot` regenerates every private binding from the selected maps.
The audit rejects resident `time.o`, requires the manager/wrapper and startup
overlay, and checks the emitted clock vectors. The older isolated overlay
experiment is historical: do not splice its raw kernel into boot media.

### Coherent boot integration and manual acceptance

`make boot` (`service-boot` is an alias) in the reference container packages
`SVC.BIN`, `TIME.SVC` and a bounded `/etc/rc` which invokes the loader after
resident startup has returned. It never substitutes raw overlay bytes into a
baseline disk. No missing-module case silently falls back to resident time.

The normal images are `build/boot/udeks.d64`, `.d71` and `.d81`.
`service-rebuild-check` reproduces them from a fresh source copy;
`service-migration-check` proves an existing resident-time build upgrades
without cleaning. Both require exact three-format disk hashes.
D64 omits only `xsprdef`, with 19 free blocks. D71 uses both standard BAMs and
D81 repacks the full file set. D64 is independently built on side one, not
truncated from a D71 with second-side files. Boot payloads are otherwise the
same. Always use a disposable copy, since root defaults to read/write.

VICE cold-boots all three formats and exercises actual loading, `date`, clock
creation, stop/reload, busy refusal, missing files, and revision-2 replacement
without relinking the kernel. Additional D64 missing/corrupt startup files
leave the shell usable and recover through an ordinary `svc load` invocation.
Close/read-error injection remains a host-loader gate; these runs do not claim
physical disk ejection or arbitrary interrupt stress qualification.

Manual C128/Pi1541 checklist (D64): after `BOOT`, expect `time: ready`, then:

```text
svc status
date -s 12:34:00
date
xclock &
svc stop
date
svc load
svc load
xclock &
```

Drag the clock before stopping and after reloading it. Stop must remove the
clock window; `date` must print `date: time service unavailable` and exit 1.
The first reload succeeds, the second reports busy without disturbing time.
While offline, a new `xclock` exits 5 without making a stale clock; normal task
retirement owns its window cleanup. Scheduler ticks/sleep remain independent.
Finish with `xclock -q` and `cat /hello`; console input must still work.

Native 1986 D64/1571 input/1351 drag, stop/reload and console recovery pass.
[Default-boot evidence](../bench/results/2026-10-09-default-time/README.md) records
the exact images and scope. The user authorized the default cutover and merge
after automated tests; no new physical-C128 result is claimed. The slot/address/format remain provisional; this
is not a generic allocator for arbitrary service classes.

Reproduce integration with host VICE:
`python3 tools/service_boot_probe.py --format d64` (also `d71`/`d81`), and
`--mode missing` / `--mode corrupt`. Test-only replacement files are added only
to disposable images. Reports preserve disk hashes and installed image bytes.
`--mode shell-missing` / `--mode shell-corrupt` on D64 additionally exercise
bootfs recovery without RC: `mount 8 /mnt`, then `/mnt/svc.bin load /mnt/TIME.SVC`.
Recovery intentionally has no normal `/bin` search/root mount. Explicit paths
also permit `/mnt/date.bin` and `/mnt/cat.bin /mnt/hello`; the mount stays read-only.

Reproduce the independent proofs in `my-distrobox`:
`make time-module time-module-check time-slot-check service-request-check service-command time-overlay-check`.
The exact sealed image runs under sim6502 through all 86,400 times of day;
174,459 entry calls check read/set/TI/BCD behavior, all 1,024 raw TOD byte
encodings, counter rollover, start/stop/restart, software
stack balance, image/BSS guards and non-mutating invalid-set rejection. An
altered range-check instruction is detected by a negative-control run. The
simulator uses RAM-backed CIA addresses: this is **not** hardware TOD latching,
interrupt, disk-loading or C128/VICE qualification.

`time-slot-check` executes the actual manager and startup veneer: 436
independent-validator cases, all 256 startup result values, recursive entry,
corrupt diagnostics, BSS bounds, start/poll/stop failure, duplicate/aborted
loading, sealed-module reload and the retained clock-read C calling convention
(2,142 protected calls). Disabling checksum
rejection in the binary fails the negative control. Simulator code does not
overlap the manager fixture; the root cc65 ZP/stack is isolated from the harness.

`service-request-check` executes the real `$CF30` envelope/dispatch, `$C880`
router, bootfs reply handlers, manager, independent SDK and exact sealed C
module together: 1,832 calls covering malformed requests, native/bootstrap
rejection, abandoned loads, publication surviving loader exit, private ZP and
decimal-mode restoration, and real start/poll/stop/reload. Removing the stack
bridge fails a negative control using a poisoned wrong-stack region. Unrelated
kernel calls trap; storage transport is a fixture. This is not disk, IRQ or
hardware-CIA qualification. Host tests run the actual `svc.c` through 17 I/O
failure/EOF/close/overflow/old-kernel scenarios with mocked request/file endpoints.

After container `make boot`, host `make service-start-probe` boots a disposable
D71 under Flatpak VICE. It runs ordinary `date` set/read, `xclock`, and disk
`cat`, then proves the new guard returns without re-entering startup after
atomically zeroing SREG and replacing the old entry's first opcode with JAM.
The probe terminates only its own emulator. This qualifies the **guard and
unchanged resident clock path**, not module loading. Only checkpoint `2ff8c01`
was byte-identical to PR #48; the guard changes current boot-image bytes.

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
The default image starts capability discovery, the resident time-slot bridge, the Z80 worker, VDC
text console, pointer input, the VIC-IIe graphics service, window manager,
keyboard, root-terminal policy, the managed-app dispatcher, and init in that
order. Init loads and polls `/bin/ush` while retaining the resident shell only
as a compatibility dispatcher for commands not yet extracted. The system remains at 1 MHz so
the VIC-IIe stays available.
The machine-clock and VDC framebuffer descriptors remain optional modules:
2 MHz requires an explicit VIC-blanking policy, and VDC bitmap mode requires
explicit display ownership. The VIC-IIe service is display class `3`, instance
`1`; startup is passive and `xinit` performs explicit mode acquisition.
The disk-loaded CIA time service is machine-policy class `4`, instance `1`;
the resident bridge stays offline until RC loads it. The
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
