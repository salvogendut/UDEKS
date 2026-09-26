# UDEKS active handover — Tasking 0.1

This is the active implementation plan after commit `92fa636`. It is intended
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
- Bank-1 task requests use the synchronous record at `$F359-$F37E` and the
  `$FF16` request gate. The record currently supports `READ`, `WRITE`, `EXEC`,
  `WAIT`, and `PROMPT`.
- Transient UDEX commands run synchronously in a saved loader slot.
- `xclock` and `xwave` are standalone UDEX images, but flag bit 1 still selects
  a six-vector managed-application lifecycle and two fixed retained slots.
- Init and the static service registry cooperatively call poll vectors. This
  is useful scaffolding but is not the final scheduler or IPC model.
- Foreground/background ownership and `Ctrl+C` still cross the compatibility
  shell path instead of targeting a general task or process-group object.

Do not delete these paths in one rewrite. Put each existing participant behind
the task model, validate it, and only then remove the replaced special case.

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

Create `abi/tasks.md` and a host-tested task-state transition module without
changing boot behavior. Then add the read-only task diagnostic record and show
the existing init, shell, and managed applications in that table. This creates
an observable seam for the assembly context-switch spike while keeping the
current system bootable.
