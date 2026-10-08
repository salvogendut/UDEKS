# UDEKS roadmap

UDEKS aims to make the C128's 8502, Z80, VDC, VIC-IIe, and banked memory useful
as one modular native system. This roadmap tracks **working capabilities and
their acceptance gates**, not every experiment. The architecture is in
[PLAN.md](PLAN.md); detailed past measurements remain in their topic documents,
commits, and [engineering handover](../HANDOVER.md).

As of 2026-09-29, the priority is **features before optimization**. A slow but
correct path is acceptable while a feature is being established. Performance
work should later be an atomic, measured change to one component, with a
preserved fallback—not a prerequisite for unrelated OS capabilities.

## Current baseline

**Current user-requested feature (2026-10-08):**
[#47 — writable root and file commands](https://github.com/salvogendut/UDEKS/issues/47),
branch `storage-0.4-file-commands`, worktree `build/storage-file-commands`.
Make the normal device-8 `/` mount read/write by default and add independent
disk-loaded `mv`, `cp` and `rm`. Explicit RO mounts and read-only bootfs recovery
remain supported. Initial commands reject implicit overwrite, wildcard removal
and directory removal; `mv` is same-filesystem rename, not copy-and-delete.

1. Define generic filesystem requests and measure placement; select a bounded
   copy mechanism (the current service has only one open descriptor).
2. Implement the service/SDK operations, three disk commands and normal-root
   default; preserve namespace, file types, permissions and meaningful errors.
3. Qualify success/failure and reboot persistence on disposable images in
   VICE/1986, then provide the C128/Pi1541 acceptance checklist.

**Branch progress:** normal boot now mounts `/` RW; explicit RO/remount and
bootfs recovery still work. Fresh images pass VICE D64/D71/D81 public
write/readback/reboot checks and native 1986 input/graphics/write regression.
The private DOS rename/copy/scratch backend passes VICE on all three drive
types, including collisions, missing files, write protection and exact binary
SEQ/PRG bytes. It is not installed in the live storage service; **`mv`, `cp`
and `rm` are not available yet**. The changed default needs user hardware
acceptance; earlier create-only acceptance does not cover the new commands.

**Next concrete delivery:** fit the generic filesystem operations into the
storage service and ship the three commands together. The measured service
has only 175 bytes of code headroom and no BSS slack, so placement is a real
integration prerequisite. Preserve the four app allocations and stack guards;
do not put raw DOS commands or filesystem policy into the command binaries.
Use DOS COPY for nonempty same-disk sources and the existing exclusive-create
writer for verified-empty sources (stock DOS COPY inserts CR for empty files).
Cross-device copy is outside this first command slice. Keep atomic replacement,
wildcards, directories and recursive deletion deferred.

This remains the next feature slice, before the first disk-loaded non-kernel service.

**Accepted checkpoint (2026-10-08):** the [sprite editor](XSPRDEF.md) now has
fast pixel updates, confirmed whole-bank Save/Load (`SPRITES.SPR`), stock-BASIC
export (`SPRITES.BSV`), a permanent sprite number and held-button draw/erase.
Generic adjacent-allocation borrowing accommodates the larger app without
editor-specific kernel routing: four ordinary apps, or one large app plus two
compatible peers. See the [SDK](GRAPHICAL-APPS-SDK.md#larger-native-apps-capacity-candidate-2026-10-07).
The user accepted each increment; [PR #46](https://github.com/salvogendut/UDEKS/pull/46)
merged as `1a45100`. The latest manual-test platform was unspecified.
Emulator evidence and limits are in XSPRDEF/HANDOVER. Overwrite, thumbnails,
keyboard editing, undo and multicolor remain deferred. This is not a broad
WM performance qualification. **Next architectural feature: the first
disk-loaded non-kernel service**, not another editor optimization.

**Completed feature (merged 2026-10-07):**
[#44 — create-only disk writes](https://github.com/salvogendut/UDEKS/issues/44),
branch `storage-0.3-disk-write`, [PR #45](https://github.com/salvogendut/UDEKS/pull/45).
The next architectural milestone is the first disk-loaded non-kernel service.
Guarded boot delivery and program-lifetime cleanup are VICE-qualified.
Step 2 now exposes opt-in create-only public writes, a file SDK and disk SAVE
command; all three VICE disk formats pass cold-boot/readback persistence.
Step 3 is complete: public failure/retirement checks pass on VICE 1541/1571;
1581 passes except mid-write eject (VICE process loss). Native 1986 D64/D81
input, NMI and reboot/readback pass. The user confirmed the manual checklist on
real C128/PI1541 on 2026-10-07. A follow-up native 1986 test now also passes
1581 mid-write ejection, error handling, reinsertion and reboot readback;
VICE's own failure remains undiagnosed. PR #45 merged as `ea25eff`.
Boot mounts remain RO.

**Completed feature (accepted 2026-10-05): generic graphical applications**,
[#35](https://github.com/salvogendut/UDEKS/issues/35). The first increment merged
as [PR #36](https://github.com/salvogendut/UDEKS/pull/36);
[PR #37](https://github.com/salvogendut/UDEKS/pull/37) removes the legacy
clock/wave application model.
Build a new app separately, copy its `.BIN` to disk, then launch it into any
free compatible slot without adding OS name tables or choosing an address.
This requires both generic instance/launch routing and slot-independent
executable loading; removing hardcoded names alone is insufficient.
See the [plan and acceptance criteria](GENERIC-GRAPHICS-APPS.md).
The four-native-client cutover is implemented: xclock, xwave, xcalc and xdraw
are separately linked relocatable programs. Four size-based allocations replace
the legacy clock/wave slots, with generic launch, instance names, close/reuse
and targeted foreground Ctrl+C. The same unknown-name binary runs in all four
allocations. VICE D64/D71/D81 and unmodified 1986 D64/1571 native input pass;
the user accepted the behavior and requested merge. The latest manual-test
platform was unspecified; physical-C128 confirmation of this cutover is not
inferred. See the [current layout and evidence](GENERIC-GRAPHICS-APPS.md#four-native-slot-cutover--2026-10-05).

Independent console commands already have a build/install SDK, argc/argv and
stdout/stderr; their loader remains synchronous. Native background-console
stdin/arguments are separate remaining work. D81 is the third boot build.
Wave holds its computation cache across moves and yields during resize
projection. A reported resize delay is reduced by app-local scale tables;
[measured dense repaint latency remains](GENERIC-GRAPHICS-APPS.md#resize-latency-follow-up--2026-10-05),
and renderer optimization stays separate. **Next: the first disk-loaded
non-kernel service.** Create-only writes (#44) are qualified and accepted.
The exploratory `.CBM` work on `additional-apps` / #32 stays separate.

**Accepted checkpoint; resumed above (2026-10-07):** [`xsprdef`, the session sprite editor](XSPRDEF.md),
[#41](https://github.com/salvogendut/UDEKS/issues/41). The user approved the
reviewed checkpoint for merge and asked to put further work aside. It edits
eight app-local monochrome definitions with magnified/1x views, confirmed
session saves, Clear and Invert. It is a generic disk app; UTRQ 0.13 provides
reusable bitmap tiles, not editor-specific kernel policy. The accepted follow-up
above adds UTRQ 0.15 pixel deltas, disk persistence, 0.16 PRG export and 0.17
held input. Thumbnails,
keyboard editing and multicolor remain deferred. Latest manual
acceptance did not specify a platform; no new physical-C128 result is inferred.

**Merged baseline:** four graphical apps (#30), [PR #31](https://github.com/salvogendut/UDEKS/pull/31),
merged as `9af159b`. Fresh builds run **xclock + xwave + xcalc + xdraw together**:
calculator and drawing have independent bank-1 allocations and an owner-checked
drawing/input bridge, with shell and running-panel integration.
See [scope and acceptance](DISK-GRAPHICS.md#four-application-support-30).
Two additional independently linked C tasks now execute from bank 1, with
private runtimes/stacks and working yield, sleep, exit and reload. Both disk
formats pass four-app VICE launch/close/reload and malformed/fifth-image rejection.
Native 1986 D64 mouse/keyboard input also passes. The four-app candidate is ready
for user testing on physical C128; exact images/results are preserved in
`bench/{artifacts,results}/2026-10-01-four-apps`.

**After the disk-write slice: the first disk-loaded non-kernel service.** Define one
existing service's load/start/stop and dependency contract, then replace its
preloaded copy with an ordinary disk image. Keep bootstrap/recovery working;
do not make a scripting language or expanded task capacity prerequisites.

**Accepted baseline:** [#26 — system root and coherent filesystem namespace](https://github.com/salvogendut/UDEKS/issues/26),
[PR #28](https://github.com/salvogendut/UDEKS/pull/28), merged as `b138b61`. Device 8 backs `/`,
programs live under `/bin`, startup policy is `/etc/rc`, and `/mnt` is free
for data media. Emulator qualification is recorded below; the user accepts
the functional test (latest platform unspecified). Downloadable snapshots
and checksums are available in [build/](../build/README.md).

**Deferred by user decision:** general `.SH` execution
([#27](https://github.com/salvogendut/UDEKS/issues/27)). Keep the suffix reserved
and the existing readable/listable mapping; do not add an interpreter merely
to justify it. The bounded `/etc/rc` command runner stays. Before resuming
scripting, define the language, execution semantics and memory budget; the
suffix does not promise POSIX `sh` or Bash compatibility.

**Completed and merged:** [#24 — disk utilities and command/service separation](COMMAND-EXTRACTION.md),
PR #25 at `d13a5c2`. Disk graphics merged as PR #23. Everyday utilities
and diagnostics now load from disk; the resident command catalog is removed.
**Functional retest accepted:** after repairing the boot probe's corruption of
graphics code at `$8000`, the user confirms the diagnostic disk boots on 1986
and C128 + Pi1541, and apps/windows work after mounting. The earlier hardware
hang's cause is unproven; the accepted diagnostic variant has boot messages on.
That release's default RC mounted device 8 at `/mnt`; #26 supersedes this
with bootstrap root mounting and an initially unmounted `/mnt`.
The finishing corrections are implemented: specific app-launch errors,
measured IEC/bootfs header status, a real mount-success message, and normal
boot progress enabled to match the accepted diagnostic setting.
Generic app loading and create-only disk writes are implemented and
user-accepted; service extraction is next. No scripting or graphics-optimization
detour is required.

- Native D64/D71 boot, an 8502 executive, a bounded Z80 worker, a VDC root
  console, and an independent VIC-IIe graphical display are working.
- `/bin/ush`, bootfs, fixed-address UDEX loading, basic Unix-like streams and
  commands, `xclock`, and Z80-assisted `xwave` provide a usable demonstration.
- Cooperative task switching, lifecycle requests, root/command execution and
  four native graphical allocations work. General allocation, IPC and preemption remain incomplete.
- The generic retained window cache is enabled in normal builds and has
  positive real-hardware feedback. Window release/background repair can still
  take seconds; that is an open limitation, not a claim of responsive graphics.
- Read-only IEC mount/list/read and foreground disk execution are merged.
  Merged PR #21 (issue #20) boots a disk-loaded shell, retaining bootfs recovery, with
  positive manual feedback (platform unspecified). Bounded shell-run `RC`
  startup and disk-only `free`/`df` are merged with positive
  manual acceptance (platform unspecified). General storage and installable
  services remain incomplete.

Hardware feedback validates particular tested builds and interactions, not
every C128 model, expansion, disk format, or failure path. `1986` and VICE are
independent emulator gates; neither substitutes for physical testing.

## Target boot and application model

The intended end state is **kernel first, then the shell**. Everything outside
the proper kernel—including applications and non-kernel service programs—must
be a standalone disk-loadable executable, not a permanent component of the
boot image. Bootfs and today's preloaded service/application bundles are
transitional mechanisms, not the final system distribution model.

Provide a shell-run startup script (provisionally `/etc/rc`) to perform mounts
and launch the desired services or applications. Keep startup policy in that
script and user space, not hard-coded in the kernel; graphical startup should
be optional. Define the minimal bootstrap read/load path needed to reach the
shell and its script before ordinary mounts exist, without using that need to
justify retaining unrelated services or applications in the kernel.

The acceptance target is a cold boot into a disk-loaded shell, followed by
script-driven initialization and on-demand program loading. Changing startup
mounts or applications must not require rebuilding the kernel.

## Roadmap position

| Roadmap area | Position |
| --- | --- |
| Foundation and CPU choice | Established; independently pinned toolchain still due. |
| Machine bring-up and dual displays | Working baseline; broader hardware/memory qualification due. |
| Kernel and tasking | Cooperative root/command tasks plus four native banked allocations; general allocation, IPC and preemption due. |
| Z80 secondary engine | Bounded task-safe worker API and cached wave computation work; broader operations and soak tests due. |
| Graphics and input | Four generic native slots, migrated disk clients, dynamic names, foreground/background launch, targeted Ctrl+C and name-based stop accepted for merge (#35/PR #37). No new physical-platform result inferred. Repaint latency and focused-window keyboard input are separate work. |
| Storage and applications | Disk shell, RC, graphics and disk commands (#21/#23/#25); root namespace accepted (#26/PR #28); create-only writes qualified and accepted (#44/PR #45). Next: disk-loaded service lifecycle. General scripting deferred (#27). |
| Release | No 1.0 claim; compatibility, recovery, documentation, and provenance due. |

## Next endeavours, in order

### Completed: Storage 0.3 — create-only disk writes (#44 / PR #45)

The [create-only backend](STORAGE-0.3.md) already passes exact empty/binary
write/readback/persistence checks on all three VICE drive types. All **three
delivery steps are complete**, with user approval to merge:

1. **Done — boot integration and ownership.** Normal disks install the guarded
   service; trusted context + generation identities distinguish native tasks
   and successive synchronous console invocations. Real EXIT, CANCEL and
   console-return paths close leaked handles before reuse. VICE D64/D71/D81
   pass; recovery and the four-native-app regression pass too. Public UTRQ
   stays 0.13, mounts stay RO, and no application/stack allocation is borrowed.
2. **Done — usable public writes.** UTRQ 0.14 route, explicit RW/remount
   options, counted binary SDK, disk SAVE.BIN and permission-aware `df`.
   Checked CLOSE, exact-empty/binary readback, duplicate rejection, background
   clock and reboot persistence pass on VICE D64/D71/D81. Boot stays RO;
   no append/overwrite/redirection.
3. **Done — functional acceptance and failure qualification.** The user confirmed
   the manual checklist in 1986 and on real C128/PI1541 (2026-10-07), including
   persistent binary/empty files, duplicate/RO rejection, graphics, RESTORE and
   console input. The missing 1581 mid-write-ejection behavior is now covered
   under 1986; retain VICE's failed-run caveat in the matrix. The follow-up
   evidence is included in PR #45, with explicit user merge approval.

Step-1 evidence: [boot ownership qualification](../bench/results/2026-10-07-storage-ownership/README.md).
Step-2 evidence: [public save/readback qualification](../bench/results/2026-10-07-storage-public/README.md).
Step-3 evidence: [failure, retirement and native 1986 qualification](../bench/results/2026-10-07-storage-acceptance/README.md).
RESTORE/recurring CIA2 NMI and native input pass on 1986 D64/D81. VICE 1541/1571
pass the full failure suite; 1581 mid-write eject remains unqualified because
the emulator process disappears. Physical C128/PI1541 functional acceptance is
user-confirmed; physical fault injection and 1581 media loss are not covered by
that report.
The separate [1986 ejection follow-up](../bench/results/2026-10-07-storage-eject-1986/README.md)
passes the missing 1581 media-loss/recovery test using two ROM-backed drives,
unchanged UDEKS/1986, and disposable media. VICE itself is not fixed or requalified.

**Acceptance:** exact empty/binary/multi-sector/final-partial-file contents;
meaningful disk-full, write-protect, missing-device, transport and close errors;
no corruption of existing files or active handles; working read/boot/recovery,
console, input and graphics afterward. All destructive qualification uses
copied/disposable images, never the user's original media. Do not claim atomic
rollback or power-loss safety; document possible partial files on failure.

Overwrite/truncate, append, delete/rename, formatting/fsck, multi-open, seek,
shell redirection, scripting, sprite-editor integration and performance work
are deferred. Detailed safety gates and scope are in
[#44](https://github.com/salvogendut/UDEKS/issues/44). Writes require explicit RW permission.

### Completed: generic graphical applications (#35 / PR #37)

All three implementation steps below are complete and emulator-qualified;
the user accepted the behavior and authorized merge on 2026-10-05. The next
feature is now disk writes, followed by service extraction, not graphics optimization.

1. Prove one real C executable can load and execute in different compatible
   slots, with an explicit format/relocation contract and measured memory bounds.
2. Replace per-app launch/control/panel wiring with executable lookup, free-slot
   selection and per-instance ownership/lifecycle records.
3. Supply an SDK/sample unknown to the OS, migrate existing clients, qualify
   independent windows and clean rejection/reuse, then offer a hardware test.
   Clock/wave now use the native path; the former two-slot intermediate is retired.

Keep this feature bounded by the existing concurrency limit. The detailed
[plan](GENERIC-GRAPHICS-APPS.md) records the placement gate and acceptance tests.

### Merged foundation: four graphical applications (#30 / PR #31)

1. **Placement gate implemented:** measure existing images, reserve independent
   bank-1 image/stack/context areas without taking shell, command or display
   memory. Check the actual normal/panic/Z80/service maps. Four-window host
   tests cover ownership, clicks, focus, dragging, capacity rejection and reuse.
   This does not yet enable four-app loading.
2. **Delivery, native execution and graphics bridge implemented:** two extra
   task allocations have independent runtimes/stacks; owner-bound retained
   drawing and click/close requests keep foreign pointers out of the compositor.
    Calculator and drawing run in bank 1 beside clock/wave.
3. **Implemented and emulator-qualified:** separate `XDRAW.BIN`, shell/panel
   lifecycle integration, four-app independent close/reload, invalid/fifth-image
   rejection, console use and targeted Ctrl+C. Both VICE disk formats and native
   1986 D64 input pass; a clean parallel build is byte-identical.
4. Physical-C128 qualification remains recorded as pending for this candidate;
   merging it did not turn emulator evidence into a hardware result.

### Following disk writes: one disk-loaded non-kernel service

1. Select one existing service and inventory its dependencies, fixed entry
   points and memory lifetime. Record which minimal boot/read path must stay
   available to load it and recover from failure.
2. Define a bounded image and load/start/stop contract; extract the service
   into an ordinary disk file without moving its policy into the kernel.
3. Qualify missing/invalid images, repeated start/stop and ownership cleanup,
   while the shell, input and existing apps remain usable. Preserve a test
   disk and ask for a short user check.

**Acceptance:** replacing only that service's disk image changes the running
service without rebuilding the kernel; failure leaves a usable recovery path.
Do not couple this slice to four-task scheduling, preemption, general shell
scripting, filesystem writes or performance tuning.

### Application-capacity target: four simultaneous graphical apps

The historical fixed loader permitted xclock **or** xcalc in slot 1, alongside
xwave in slot 2. The feature branch now places xcalc and xdraw in separate bank-1
allocations, using all four window descriptors for independently loaded apps.

Define application placement/loading with explicit image, state, stack and
callback ownership before expanding capacity. Acceptance: xclock, xcalc,
xwave and an independent fourth executable remain live on the same screen,
can be focused/dragged, and close/reload independently while the VDC console
works. A four-window demo inside one program is not this acceptance test.
Rejected loads must leave existing apps intact. Keep this feature separate
from xwave-specific optimization and subsequent service extraction.

### Completed: system root and namespace (#26)

Replace the fixed `/mnt`-only storage route with a bounded mount/path contract.
The system volume (default device 8) backs `/`; a separate volume can occupy
`/mnt` without taking away system commands. Standard D64/D71 disks stay flat
CBM DOS: virtual directories use filename suffixes, not a separate index or
a new disk format. Keep bootstrap/recovery
bootfs available, with deliberate lookup precedence and failure behavior.

**Suffix convention (user decision):** `.BIN` identifies UDEX executables,
`.SH` identifies shell scripts, and `.ETC` maps configuration into `/etc`.
Do not use `.USR` or `.RC` as namespace suffixes. The directory view hides
the classification suffix and presents lowercase logical names:

| Disk filename | Logical path | Handling |
| --- | --- | --- |
| `USH.BIN` | `/bin/ush` | Validate/load UDEX. |
| `STARTUP.SH` | `/bin/startup` | Reserved script kind; readable/listable, execution deferred. |
| `RC.ETC` | `/etc/rc` | Designated boot script; other `.ETC` files are data. |

Scripts share `/bin` with executables so normal command lookup can find both.
Listing filters the real disk directory; opening translates the logical name
to a physical filename. No per-application map needs updating when files are
added. Specify bounded lookup/listing, remount cache invalidation and detection
of ambiguous names such as `FOO.BIN` plus `FOO.SH`; directory order must not
silently select a different command. All physical names, including suffixes,
remain within 16 bytes. Extra `.ETC`/`.SH` files are not automatically executed.
Data mounts retain ordinary filenames without requiring these conventions.
Script dispatch/execution is deferred under #27, not required to accept the
namespace. The current release supports neither general `.SH` execution nor
Bash syntax. The existing `/etc/rc` runner is unchanged.

1. **Implemented:** [namespace contract](../abi/filesystem.md#root-namespace-contract-26),
   C resolver, suffix classification/inverse mapping and collision checks;
   host tests cover relative paths, `.`/`..`, limits, atomic rejection, and
   independent device-8 root/device-9 data routing. cc65 compilation passes.
2. **Implemented:** live root/data routing, disk-shell bootstrap, service-backed
   `cd`/`pwd`, file operations, command/app lookup, and `df`. Device 8 is mounted
   before reading `/etc/rc`; the script configures later mounts. Ordinary flat
   DOS files use the suffix convention; no new disk format.
3. **Accepted:** the user reports the candidate runs beautifully after the
   root-namespace test and unmount check (latest platform unspecified).
   VICE covers independent drives and recovery; 1986 covers native typing and
   repeated dragging. See [current filesystem contract](../abi/filesystem.md).
4. **Deferred (#27):** bounded `.SH` command dispatch/interpreter. Scripts
   already appear in `/bin` and can be read, but cannot yet be launched.
   Only `/etc/rc` is executed by the existing startup interpreter.

**Acceptance:** boot to a disk-backed `/`, list/run `/bin` programs, read
`/etc/rc`, and mount/list/read/unmount a standard data disk at `/mnt` using
commands from the system volume. `cd`, `pwd`, `ls`, `cat`, `df` and program
lookup must agree. Invalid requests must leave live state intact.

Placement is checked: policy uses bank-1 `$B000-$CFFF`, recovery bootfs is
bounded to 4 KiB, and cwd handling moved out of ush. Keep policy in C services/user space, preserve
public gates and recovery, and explicitly migrate old `/mnt/NAME` paths.
No writes, graphics optimization, expanded tasking or service extraction in
this slice. The sections below retain the broader milestone sequence/history.

### 1. Storage 0.1: read files from an external disk

**Current checkpoint (2026-09-30):** `mount 8 /mnt`, `ls /mnt`,
`cat /mnt/HELLO`, and `umount /mnt` are implemented. Normal disk images
include `HELLO`; all previous commands remain, with `ls`/`cat`/`mount`/`umount`
sharing one nonresident C executable. VICE shell tests cover errors and
graphics-active use; the 1986 raw-IEC keyboard workflow passes too. The user
has separately confirmed the earlier mount/list slice after restarting 1986.
The byte-counted sector reader now passes tiny-file EOF and media-error/recovery
checks in VICE and the keyboard workflow in 1986; 885 host tests pass.
**Merged:** PR #17 at the user's request (`92a2e36`). Physical C128 + PI1541
qualification remains unrecorded; merge authorization is not a test result. The exact
hardware test disks are preserved in `bench/artifacts/2026-09-30-storage-0.1`.
This is not full Storage 0.1 acceptance until that hardware result is recorded.
See [the hardware checklist](STORAGE-0.1.md#hardware-checklist).

Deliver the smallest useful vertical slice through a **C storage service**,
without moving device policy into the resident kernel. Define bank-aware
buffer ownership and a mount/handle contract, implement baseline IEC access
for a 1541/1571-compatible device (including PI1541), and expose directory
listing and file `open`/`read`/`close` through the existing stream boundary.
Add the small user-facing `mount`, `umount`, and `cat` commands needed to use
and verify that path.
Keep bootfs as the reliable fallback. Start read-only; do not make 1571 burst,
disk writes, a new filesystem format, or relocatable executables prerequisites.

**Acceptance:** from a cold boot, `ls` can distinguish bootfs and mounted media,
`cat` can display a file from that media, and error/no-device/media
change paths return control to the shell. Qualify D64/D71 in `1986` and VICE,
then read from PI1541 on a physical C128 without breaking graphics, input,
boot, or the Z80 worker. The implementation sequence and current gate are in
[Storage 0.1](STORAGE-0.1.md).

### 2. Storage 0.2: launch a program from disk

**Started:** issue [#18](https://github.com/salvogendut/UDEKS/issues/18), branch
`storage-0.2-disk-exec`, now based on merged Storage 0.1.
**Manual 1986 check passed:** the user confirms all suggested tests following
checkpoint `f0a9065`. `/mnt/DISKCOW hello` executes from mounted media,
preserves arguments/exit, and can be run repeatedly. VICE D64/D71 and native
1986 checks pass; malformed images and I/O failures return to the shell.
The preserved Storage 0.1 hardware candidate is unchanged.
The user subsequently confirmed the tests passed on a real C128 with PI1541
and authorized continuation, completing this slice's manual acceptance gate.
**Merged:** PR #19 (`9ab1efd`). This is not exhaustive model/device/failure-path qualification.
Do not divert this milestone into loader or graphics optimization.
See [Storage 0.2](STORAGE-0.2.md) for the short implementation/acceptance plan.

Use the same mount and stream contract to resolve and load a fixed-address
UDEX program from external media. Preserve the existing image validator,
ownership rules, exit/wait behavior, and bootfs fallback. Add per-process
`chdir`/`getcwd` only when paths are represented consistently across both
sources. Consider writes and a native filesystem format *after* read and
launch are reliable.

Then use this loading path for the shell itself and introduce the startup
script described above. Retire preloaded application bundles as their
disk-backed replacements become usable; extract the remaining non-kernel
services under milestone 3 rather than treating them as permanent residents.

**Active follow-through:** issue [#20](https://github.com/salvogendut/UDEKS/issues/20),
branch `boot-disk-shell-startup`. Normal boot now tries the ordinary DOS `USH`
file first, closes/unmounts its bootstrap access, then starts the persistent
shell. Missing/invalid files fall back to bootfs. The first user-test candidate
and source/recovery checks are described in [Boot 0.2](BOOT-STARTUP.md).
The user reports that this candidate looks good; the manual-test platform was
not specified. **Merged:** PR #21 (`ea14666`).
Current deliverable: bounded shell-run startup commands editable on disk,
plus the requested standalone `free` and `df`. Keep `free`'s fixed-pool
accounting explicit until a general allocator exists. The user now reports
"looks ok to me" for this slice; record positive manual acceptance without
assuming a platform. Continue retiring bundled applications before pursuing
milestone 3's remaining non-kernel program/service extraction. The final kernel-only distribution
is not complete; do not divert into unrelated optimization.

**Acceptance:** copy a known UDEX onto media, list it, launch it, observe its
exit status, and launch it again without reboot or memory corruption. Repeat
with a malformed image and a removed/unavailable device.

### 3. Tasking and service boundaries 0.2

**Immediate extraction slice:** issue [#22](https://github.com/salvogendut/UDEKS/issues/22),
branch `storage-disk-graphics`: load `xclock`, then `xwave`, from ordinary
disk UDEX files and remove their normal bootfs payloads. Preserve existing
fixed slots, windows and foreground/background lifecycle. Reject a file
aimed at the other app's slot and never stage over a live native child.
Accept when both disk-only apps coexist, stop/restart and remain interactive,
and missing/malformed files leave the console and running peer intact.
No rendering or IEC optimization belongs in this slice.

**Testable checkpoint (2026-09-30):** both graphical files are disk-only;
their normal bootfs copies are removed. VICE D64/D71 validates both launch
orders and failed-load isolation; native 1986 validates window interaction,
cancellation, console use and restart. See [candidate and short test sequence](DISK-GRAPHICS.md).
**Merged:** PR #23 (`2c88e07`) by user authorization; manual hardware acceptance
of that exact candidate remains unrecorded.

**Merged as PR #25:** issue [#24](https://github.com/salvogendut/UDEKS/issues/24),
branch `boot-disk-commands`: COWSAY/DATE/LS/CAT and UNAME/LSHW/LSMOD/LSCPU/Z80CTL
are ordinary disk files, alongside FREE/DF/XCLOCK/XWAVE. Recovery bootfs retains
only mount/unmount and ush. Disk ush owns builtin policy and graphics syntax;
numeric deferred requests replace the resident builtin registry. See
[the test sequence and remaining limitations](COMMAND-EXTRACTION.md).

**Next, after accepted root/namespace issue #26:** choose one existing non-kernel
service, define its load/start/stop and dependency contract, and load its ordinary
disk image on demand without rebuilding the kernel. Preserve a boot/read recovery
path. This is separate from expanding task capacity below. Issue #26 has
separated the system command source from data mounts: disk utilities now
come from `/bin` on the system volume, not `/mnt`.

The four-native allocation step is implemented; generalize it beyond these
bounded slots, add a message/handle mechanism, and move console, input, graphics, and
storage policy behind service interfaces rather than private kernel calls.
Keep cooperative scheduling as a valid intermediate step. Introduce
timer-driven preemption only after bank, cc65 runtime, stack, and device
ownership survive the multi-task tests. The C128 has no memory-protection
unit; isolation here means validated boundaries and recoverable ownership,
not hardware-enforced process memory.

**Acceptance:** four C tasks repeatedly use banked memory, streams, and both
displays while exchanging messages; cancellation and faults do not strand
shared resources. Then pass interrupt/stack soak tests on emulators and real
hardware before claiming preemption.

### 4. Reusable dual-engine services

Promote the Z80 beyond a single application: provide bounded copy/checksum
and one transform operation over validated bank-aware buffers, using measured
handoff thresholds. Keep the 8502 responsible for interrupts, I/O, and task
ownership; CPU handoff is scheduled cooperation, not simultaneous execution.

**Acceptance:** applications can request these operations through a stable
interface, with malformed-request and cancellation tests plus a long mixed
handoff soak run on emulators and physical hardware.

### 5. User-facing desktop and system tools

After the storage/task interfaces exist, add focused-window keyboard routing,
a file manager or editor, and a two-monitor collaborative demonstration.
`xmandel` remains a useful Z80/8502 stress application, but is not ahead of
disk-backed programs or task/service mechanisms. App-specific render caches
belong in their apps; generic composition belongs in the window service.

**Acceptance:** useful workflows run from disk, interact through windows and
streams, and survive application exit/restart while the VDC console remains
usable.

## Later, separately scoped work

- Improve worst-case window repaint and xwave rendering through isolated,
  measured optimizations. The current cache stays available; experimental
  bounded-repaint prototypes are not a new bootable baseline. Do not let this
  work block Storage 0.1–0.2.
- Add disk writes, filesystem recovery, media-change policy, 1571 burst,
  relocatable programs, and expansion-backed memory after their read-only and
  fixed-address foundations are sound.
- Complete VDC compositor tiers, broader VIC/VDC modes, peripheral inputs,
  audio, and hardware acceleration as their owning services mature.
- Pin the toolchain, publish reproducible build provenance, document drivers
  and SDK workflows, and test a C128/C128D/C128DCR compatibility matrix before
  a 1.0 release.

## Delivery discipline

Each endeavour should yield a bootable, user-testable slice. Host tests cover
pure policy; `1986` and VICE cross-check machine behavior; real hardware is
required for claims about devices, timing, and compatibility. Keep normal and
panic links within their established placement/ABI limits, preserve the
previous working path until the replacement passes, and record exact test
images and results. A private size study or emulator-only prototype is useful
evidence, but it does not by itself close a roadmap milestone.
