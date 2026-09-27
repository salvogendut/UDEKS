# UDEKS active handover — Tasking 0.1

This is the active implementation plan as of 2026-09-27. It is intended
to let a future development session resume without reconstructing the current
architectural priorities from the commit history. The detailed architecture
remains in [`docs/PLAN.md`](docs/PLAN.md), the capability gates remain in
[`docs/ROADMAP.md`](docs/ROADMAP.md), and ADR 0007 remains authoritative about
the resident-core boundary.

## Decision

The next milestone is **Tasking 0.1**. Do not add another application or grow
the resident compatibility dispatcher before this milestone is complete.
UDEKS already proves native boot, independent displays, loader-managed UDEX
programs, a persistent `/bin/ush`, overlapping VIC-IIe windows, responsive
pointer input, and bounded Z80 work. Its present limitation is that init still
polls special lifecycle entries and the two graphical programs still occupy
special retained slots rather than ordinary scheduled tasks.

Tasking 0.1 will replace that special-case control flow with a bounded
cooperative 8502 scheduler. Timer-driven preemption is explicitly deferred
until context switching, stack ownership, task exit, and slot reuse are
qualified.

## Constraints that must not change

- The 8502 remains the resident executive. The Z80 remains a synchronous,
  bounded worker; the CPUs share the bus and are not presented as concurrent.
- Kernel mechanisms are primarily assembly. Scheduling policy, task tables,
  validation, and later services should be C where timing permits.
- UDEX programs depend only on published fixed gates and public headers, never
  resident C symbols.
- The initial scheduler is bounded and allocation-free in interrupt context.
- Fixed-address UDEX 0.1 remains supported during this milestone. Relocatable
  executables are a later storage milestone.
- Existing VDC console, VIC-IIe graphics, mouse, joystick, window management,
  shell, `date`, `ls`, `cowsay`, `xclock`, and `xwave` behavior must remain
  usable after every migration step.
- Z80 leases must stay short enough for input and cancellation to remain
  responsive. A task may logically wait for a lease, but the design must not
  claim that the 8502 executes while the Z80 owns the bus.

## Current transitional mechanisms

- `/bin/ush` is a persistent bank-1 program entered through the returning
  `$FF13` common-RAM gate. Its cc65 zero-page context is saved at
  `$E2E2-$E2FF`, and its software stack begins at `$EFF0`.
- Bank-1 task requests use the shared record at `$F359-$F37E` and the `$FF16`
  request gate. ABI 0.3 adds lifecycle operations to the original synchronous
  console/filesystem operations; blocking `WAITPID` now snapshots ownership
  privately while the shared record is released.
- Transient UDEX commands run synchronously in a saved loader slot.
- `xclock` and `xwave` are standalone UDEX images, but flag bit 1 still selects
  a six-vector managed-application lifecycle and two fixed retained slots.
- Init and the static service registry cooperatively call poll vectors. This
  is useful scaffolding but is not the final scheduler or IPC model.
- Foreground/background ownership and `Ctrl+C` still cross the compatibility
  shell path instead of targeting a general task or process-group object.

Do not delete these paths in one rewrite. Put each existing participant behind
the task model, validate it, and only then remove the replaced special case.

## Current implementation status (2026-09-27)

- Step 1 has a versioned lifecycle ABI, host-tested lifecycle state module,
  and diagnostic/validation seam. The installed scheduler now resets the
  resident task table, registers persistent `/bin/ush` as running task 1, and
  publishes the resulting `UTSK` record before entering the retained poll
  path. A bounded C round-robin selector is linked into the scheduler page and
  host-tested across empty, sparse, wrapped, and yielded run queues; the
  installed context-save/resume tail calls it between cooperative task runs.
- Step 2 is qualified in `1986`, VICE, and physical C128 hardware; ADR 0008
  freezes relocated page-zero/page-one ownership and the bounded copy
  fallback. The follow-on `UCCS` spike now also switches two real cc65 tasks
  64 times with live C frames and distinct software stacks, byte-identically
  in `1986` and VICE at 1/2 MHz. Its physical-C128 run remains outstanding.
- Step 3 has Task Request ABI 0.3 operations for `YIELD`, `EXIT`, `WAITPID`,
  `SLEEP`, `CANCEL`, and `SPAWN`, plus a pure host-tested policy layer.
  Production `YIELD`, non-returning `EXIT`, and immediate, nonblocking, and
  blocking `WAITPID`, bounded `SLEEP`, child-only `CANCEL`, plus task-2
  `SPAWN`, are implemented.
- The placement prerequisite for steps 3 and 4 is qualified. Stage 1 can
  deliver a scheduler image to `$1C00-$1FFF`; crt0 and probe are split boot
  outputs; the boot-only capability service is linked at `$0200`, installed
  before crt0, and safely overwritten by applications after startup. ADR 0009
  records the accepted capability relocation. These placements now support
  the installed scheduler and lifecycle handlers described below.
- `boot_console.o` is now a split boot image at `$1600`, and VICE proves it is
  safely overwritten by `xwave`; ADR 0010 remains proposed until the
  independent `1986` pass. The final boot-only gather is also split and runs
  in place at `$A1E0`, leaving the complete `$C120-$CEFF` tail available for
  lifecycle/scheduler integration.
- Lifecycle placement is active: `SCHEDOVR` carries the zero-padded 1 KiB
  scheduler page and the installed lifecycle tail at `$C120-$CDBC`. Stage 0
  loads it into bank 1 with KERNAL `SETBNK`/`LOAD`; a 192-byte one-shot
  common-RAM installer validates and copies it, clears its BSS, and the
  scheduler entry replaces that installer with the permanent task gate.
  D71/D64 cold boot,
  exact page/tail installation, VIC repaint, and application-slot reuse pass
  in VICE. ADR 0012 remains proposed pending `1986` and physical C128 runs.
- The production-shaped save/select/restore tail now fits behind the frozen
  `$FF10/$FF13/$FF16` entries: its separate link occupies `$FF05-$FFC3`, 191
  of the exact 192 reserved bytes. It captures A/X/Y/P/SP and the continuation
  before remapping, preserves the resident kernel stack, and restores the
  selected task's relocated page zero/page one and CPU context. The boot image
  installs it after startup. Eight 11-byte records plus reset/save/select
  callbacks occupy the exact `$CDBD-$CEFF` 323-byte window, while fixed
  callback vectors consume the page's final six bytes at `$1FFA-$1FFF`.
  `SCHEDOVR` ABI 0.3 appends the exact, build-locked 234-byte context image and
  192-byte gate; its checksummed bank-0 tail also installs the 1,163-byte
  lifecycle handler at `$C900-$CDBC`, outside both application slots. The
  normal checksum covers the
  six fixed page vectors, and the boot-console installer checksums and installs a
  42-byte post-startup activator at `$1BAA` and copies it directly to its
  `$F68A` common-RAM run address. Persistent `/bin/ush` now polls, yields, and
  resumes through the `$CF30` carry contract. D71 and D64 VICE probes observe
  repeated context switches and accept `xinit`; the xwave slot-reuse probe
  also remains green. Task 1 owns bank-1 pages `$D1/$D2`, above bootfs and
  outside the loader's `$8000-$8A00` backup. Dedicated D71/D64 tasks also
  prove that `EXIT(37)` becomes a zombie, releases the request record, and
  cannot resume. D71/D64 probes also prove live-child `WAITPID|NOHANG` returns
  zero, zombie status 37 is reaped with result one, the complete child slot is
  cleared, and a repeated wait returns `ECHILD`. The two-task D71/D64 probe
  additionally proves that blocking `WAITPID` releases the shared request,
  the child can issue `EXIT(37)`, and the parent resumes with result one and
  its original sequence `$44`.
- The first `SPAWN` increment is qualified: the common loader exposes a
  scheduler-private `$F919` load-only entry, validates a flag-zero bootfs UDEX,
  and copies its image/BSS into bank-1 APP1 without entering it. The loader is
  exactly 1,520 bytes in its frozen `$F910-$FEFF` reservation. D71 and D64
  probes load `/bin/cowsay` byte-exactly and clear a pre-seeded 32-byte BSS;
  lifecycle allocation and context admission are now layered on this seam.
- Full `SPAWN` is qualified on D71 and D64. The handler validates the request
  before loading, initializes task 2's `$D3/$D4` relocated pages and private
  context, and publishes its `RUNNABLE` slot last. A common `$F280` launcher
  converts the child's normal return into `EXIT(A)`. A persistent parent runs
  a compiled cc65 child through two spawn, blocking-wait, status-37 reap
  cycles with original sequences `$44/$66`, proving the real compiler stack,
  task-slot, and APP1 reuse.
- Bounded `SLEEP` is qualified on D71 and D64. The raster IRQ advances an
  overlay-owned 16-bit clock at 60 logical ticks/s on PAL and NTSC; the
  resident service pass wakes expired TIMER waiters. Zero and 601 ticks are
  rejected, while the maximum 600-tick request blocks and resumes with its
  original sequence after at least 600 logical ticks.
- Child-only `CANCEL` is qualified on D71 and D64. Zero, self, free,
  unrelated, already-zombie, and full-width out-of-table targets are rejected
  without mutating the target. The resident regression covers `$0100`, `$0101`,
  `$0102`, and `$FFFF`, preventing low-byte aliasing of zero/self/live-child
  IDs. Cancelling a blocked child clears its private wait snapshot, preserves
  status 130 in a
  zombie, and lets the parent reap that status through `WAITPID`.

## Implementation plan

### 0. Preserve a known-good baseline

Before changing context or task code, record a short repeatable smoke sequence:

1. boot to the `/bin/ush` prompt;
2. exercise mixed-case input, history, `date`, `ls`, `cd`, and `cowsay`;
3. run `xinit`, then `xclock &` and `xwave &`;
4. move, resize, focus, and close both windows with mouse and joystick;
5. confirm console input remains clean and `Ctrl+C` stops only the foreground
   graphical job;
6. stop graphics with `xinit -q` and launch the programs again.

Automate the portions supported by `1986`, retain VICE as the independent
oracle, and keep a concise real-hardware checklist. Record failures before
changing scheduler code so input or display regressions are not mistaken for
tasking defects.

### 1. Freeze the task ABI and task control block

Add a compiler-neutral task ABI document before exposing new gates. Define a
bounded task table whose minimum fields are:

- task ID, parent task ID, state, flags, and exit status;
- executable CPU, bank/MMU profile, validated image/BSS/allocation bounds, and
  entry address;
- saved 8502 registers, program counter, processor status, hardware stack
  state, cc65 software-stack pointer, and compiler-owned zero-page bytes;
- standard descriptors, current working-directory handle, controlling
  terminal/session owner, and foreground/background ownership;
- wait reason and bounded wake data for child exit, input, timer, or Z80 work;
- stack bounds plus canary state.

Initial states should cover `FREE`, `NEW`, `RUNNABLE`, `RUNNING`, blocked wait
states, `STOPPED`, and `ZOMBIE`. Exact numeric values and the table size must be
chosen only after a current linker-map/common-RAM audit. Publish a small
diagnostic record so emulator tests can observe current task, runnable count,
switch count, rejected transitions, and canary failures.

### 2. Qualify one real context switch

**Qualified 2026-09-26.** `bench/context-switch` implements the spike, and
[ADR 0008](docs/decisions/0008-context-switch-placement.md) records the chosen
relocated page-zero/page-one ownership with a bounded save/copy fallback. The
r5 image passes in `1986`, VICE 3.10, and on a physical C128. Canaries and
validation are in-image; integration with the kernel panic path arrives with
the scheduler.

Implement the smallest assembly spike that switches between two synthetic
8502 tasks and proves that all of the following survive independently:

- A, X, Y, P, PC, and hardware SP;
- the live page-one stack contents or a qualified per-task relocated page one;
- cc65 zero-page `$02-$1F` and the software-stack pointer;
- the selected MMU profile and task-visible bank;
- interrupts arriving immediately before and after a switch.

Use the spike to choose between relocated page-zero/page-one ownership and a
bounded save/copy strategy. Record that decision before integrating it into
the kernel. Add canaries and fail through the existing panic path on corruption.
The old `$FF13` returning gate remains available until `/bin/ush` passes through
the new switch path.

### 3. Add cooperative lifecycle operations

Extend the public syscall/request boundary with versioned operations for:

- task creation or loader-backed `exec`;
- `yield`;
- `exit(status)`;
- `wait`/`waitpid` with a nonblocking option;
- bounded sleep against monotonic kernel time;
- task-directed cancellation sufficient for the first `Ctrl+C` path.

Use Linux-compatible descriptor and errno conventions where they fit. Reject
invalid task IDs, illegal state transitions, overlapping allocations, bad
stacks, and unsupported CPU/format combinations without altering scheduler
state. Returning from a normal UDEX entry is equivalent to `exit`.

### 4. Introduce the cooperative scheduler

Implement a deterministic round-robin runnable queue. Scheduling occurs only
at explicit safe points in Tasking 0.1: `yield`, a blocking syscall, task exit,
or return from a bounded service pass. IRQ code may mark work ready but must
not preempt a task yet.

The idle path must continue polling the minimum transitional service registry
until those services become task endpoints. Sleeping or blocked tasks must not
consume runnable turns. A Z80 request is admitted only through the existing
bounded worker policy; completion or failure returns the owning task to the
appropriate state.

### 5. Migrate programs without a flag day

Migrate in this order:

1. represent init and the existing `/bin/ush` poller in the task table while
   retaining the old entry gate;
2. run `/bin/ush` through the qualified task context path and retire its manual
   init poll;
3. represent synchronous utilities (`date`, `ls`, and `cowsay`) as child tasks,
   publish exit status, and reclaim their allocation after `wait`;
4. replace the special `xclock` and `xwave` dispatcher slots with ordinary
   retained tasks using their existing application/window lifecycle adapters;
5. remove the obsolete compatibility paths only after equivalent behavior is
   covered by emulator smoke tests.

UDEX 0.1 lifecycle flags may remain as loader hints during migration; task
identity and scheduling state must not remain encoded as application-specific
global variables.

### 6. Move shell job ownership onto tasks

Make `/bin/ush` launch programs through the general loader/task interface.
A foreground child owns the controlling VDC terminal until it exits, stops, or
is cancelled. A trailing `&` leaves the child runnable and returns the prompt
immediately. `Ctrl+C` targets the foreground task rather than a command name or
window. Preserve the conventional exit result of 128 plus the interrupt number
where practical.

After the underlying operations are stable, add small Bash-like `jobs`, `fg`,
`kill`, and `ps` commands. Do not add them as resident kernel builtins.

### 7. Replace global session state

Move descriptors and the working directory into the task/session model.
Implement public `chdir` and `getcwd` operations, inherit descriptors and cwd
on child creation, and remove the transitional root-session directory token.
This step should preserve the existing behavior of native `cd`/`pwd` and the
standalone `ls .` program while eliminating their private coordination state.

## Tasking 0.1 acceptance gate

The milestone is complete only when:

- `/bin/ush`, `xclock`, and `xwave` are represented and dispatched as ordinary
  tasks rather than manually polled special cases;
- foreground and background launches behave consistently, `Ctrl+C` affects
  only the foreground task, and exited children are waitable and reclaimed;
- repeated utility and graphical-program launch/exit cycles reuse their slots
  without stack, zero-page, MMU, window, or display corruption;
- the VDC console remains responsive while VIC-IIe windows are moved and while
  `xwave` performs bounded Z80 computation;
- invalid lifecycle requests return stable errors and do not corrupt the task
  table;
- host scheduler-policy tests pass, context/canary diagnostics remain clean,
  and the smoke sequence passes in `1986`, VICE, and on a physical C128;
- documentation and diagnostic records describe the implementation actually
  shipped in the boot images.

Timer-driven preemption is not part of this gate. It becomes the next tasking
revision only after a cooperative soak test demonstrates safe context, stack,
and bank ownership.

## Work immediately after Tasking 0.1

1. Complete per-process VFS semantics and implement baseline IEC serial device
   discovery and read operations; do not start with 1571 burst mode.
2. Resolve `/bin` from a storage-backed filesystem while retaining bootfs as a
   recovery source.
3. Add message queues/endpoints and extract input, terminal, display, window,
   time, and engine policy from the resident image in the ADR 0007 order.
4. Implement timer-driven preemption and the longer interrupt/task soak gate.
5. Build `xmandel` as a tiled Z80-compute/8502-present scheduler, cancellation,
   and storage-load stress test rather than as another privileged demo.

## First concrete change for the next session

PR #3 merged the lifecycle foundation as `00060f4`; PR #5 merged the event-wait
implementation as `1b7a6e0`. Work continues on `xwave-responsive-rendering`,
tracked by [issue #6](https://github.com/salvogendut/UDEKS/issues/6);
issue #4 retains its manual and hardware qualification gates.
[the event-wait proposal](docs/EVENT-WAITS.md)
defines the initial stdin-readiness scope, private request ownership,
placement constraints, and regression gates. ABI 0.4 `POLL` is now installed,
and idle native ush blocks on INPUT rather than repeatedly reading/yielding.
The pure C policy remains compile-only; its bounded assembly equivalent
reuses the WAITPID/SLEEP snapshots without extra BSS. Remaining space is
141 core bytes and 50 handler bytes; the resident/VIC-shadow boundary and
published task/runtime addresses are unchanged.

The compiled-C POLL probe passes on D71/D64: validation, finite wrap, infinite
wake, chunked/empty reads, stopped wake/continue, sequence restoration and live
stack locals. Seeded subscriptions qualify multiple waiters and ready/expiry
precedence. INPUT cancellation clears its snapshot. The shell/graphics smoke
checks stable idle suspensions and xinit/xclock/xwave plus console utilities.
Native ownership suppresses the resident compatibility shell's competing
input read, while preserving deferred EXEC and foreground job handling.

Independent 1986 machine-input smoke now passes on D71/D64: exact submitted
text, backspace/history, 1351 outline dragging, foreground Ctrl+C, background
clock survival and subsequent console input. The tracked emulator sources are
unchanged. The smoke exposed an inherited `$D02F` selector/arbitration bug;
the scanner now leaves extended columns idle with the resident layout unchanged.
See [the input report](bench/results/2026-09-27-event-waits-1986/README.md).
Initial xwave painting delayed a release scan by 689 frames in the baseline.
The [bounded-rendering increment](docs/XWAVE-RESPONSIVENESS.md) now permits
Ctrl+C during row 0 and completes with 21 cached row leases. Cached compositor
replay and closing-window redraw remain synchronous; issue #6 stays open.
Complete physical-C128 and manual SDL/host input and
performance gates for issue #4. Then generalize
task allocation and migrate shell jobs/graphical applications to ordinary
lifecycle tasks. Do not claim Tasking 0.1 complete or discharge the older
ADR 0010/0012 and integrated-context hardware gates from these VICE results.

## xwave drag-freeze correction (issue #8)

On `fix/xwave-drag-freeze`, repeated native dragging reproduces the reported
freeze on the PR #7 disk. The reference cc65 outline-mask expression stores
outside its record and overwrites the lifecycle dispatcher at `$F415`.
An equivalent complement/right-shift expression fixes the generated store;
eight saved CODE bytes are reserved to preserve the frozen `$A1E0` shadow
placement. No 1986 source changes are required. D71/D64 partial/cached drag
stress, Ctrl+C and subsequent console input pass; VICE boot/scheduler/shadow
smokes pass. See the [regression report](bench/results/2026-09-27-xwave-drag-freeze/README.md).
Manual SDL and physical-hardware confirmation remain outstanding. Rebase and
requalify `graphics-raster-audit` on this fix before integrating its scratch
optimization; its earlier checkpoint is not a qualification of this revision.
