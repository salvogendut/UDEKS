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

- Native D64/D71 boot, an 8502 executive, a bounded Z80 worker, a VDC root
  console, and an independent VIC-IIe graphical display are working.
- `/bin/ush`, bootfs, fixed-address UDEX loading, basic Unix-like streams and
  commands, `xclock`, and Z80-assisted `xwave` provide a usable demonstration.
- Cooperative task switching, lifecycle requests, and the initial two-task
  arrangement work. General allocation, IPC, and preemption are not complete.
- The generic retained window cache is enabled in normal builds and has
  positive real-hardware feedback. Window release/background repair can still
  take seconds; that is an open limitation, not a claim of responsive graphics.
- Bootfs remains the bootstrap fallback. Read-only IEC mount/list/read works;
  issue #18 adds the first explicit-path disk-execution slice. General storage,
  disk-loaded shell/startup policy and installable services remain incomplete.

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
| Kernel and tasking | Cooperative two-task path works; general scheduling, IPC, and preemption due. |
| Z80 secondary engine | Mailbox and xwave computation work; reusable operations and soak tests due. |
| Graphics and input | Working shell/windows/apps; repaint latency and focused-window input remain open. |
| Storage and applications | Read-only IEC merged; foreground disk execution accepted in 1986 and on C128 + PI1541. Disk-loaded shell/startup is next. |
| Release | No 1.0 claim; compatibility, recovery, documentation, and provenance due. |

## Next endeavours, in order

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
**Next:** merge the foreground disk-execution slice and move to disk-loaded
shell/startup policy. This is not exhaustive model/device/failure-path qualification.
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

**Acceptance:** copy a known UDEX onto media, list it, launch it, observe its
exit status, and launch it again without reboot or memory corruption. Repeat
with a malformed image and a removed/unavailable device.

### 3. Tasking and service boundaries 0.2

Generalize the current two-task allocation to at least four C tasks, add a
bounded message/handle mechanism, and move console, input, graphics, and
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
