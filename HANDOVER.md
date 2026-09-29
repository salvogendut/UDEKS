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
implementation as `1b7a6e0`; PR #7 merged bounded xwave rendering as `6aadcf3`.
Work continues on `graphics-raster-integration` (issue #10),
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
The user reported the manual 1986 interaction check looked good. The next
[raster audit](docs/GRAPHICS-RASTER-AUDIT.md) confirms 49-byte whole-link savings
and approximately 12% lower line/24% lower fill timer counts in isolated 1986
and VICE probes. All pixels/dirty flags match an independent reference. Current
cooperative/IRQ paths do not reenter scratch, but future preemption needs
serialization. The historical candidate link moved the shadow to `$A1AF`;
production was unchanged at that checkpoint. Preserve the `$A1E0` staging
contract explicitly, regenerate import
bridges and qualify the integrated image before consuming the savings. Raw
CIA counts differ by about one per 65,536 events across the emulators; the
evidence retains that discrepancy and makes no physical-cycle claim.
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
PR #9 is merged as `5d089a4`. The user subsequently reported the real-hardware
checklist passed: "all good on real hardware" (2026-09-27). This closes the
drag-freeze functional hardware gate, not unrelated tasking gates or timing
qualification. Manual SDL confirmation remains outstanding. Rebase and
requalify `graphics-raster-audit` on this fix before integrating its scratch
optimization; its earlier checkpoint is not a qualification of this revision.

## Raster integration continuation (issue #10)

The scratch-only line/fill optimization is integrated atop PR #9. It removes
81 CODE bytes and adds 32 BSS bytes; a named 49-byte CODE reserve preserves
the frozen `$A1E0` shadow boundary. Normal private bridges are regenerated;
no common-RAM gate, UAPP runtime address or legacy row reservation changes.
The audit and standalone builders retain an automatic-local reference even
though production now uses static locals. Drawing remains cooperative,
non-yielding and non-reentrant; preemption needs service serialization.

Clean parallel builds are deterministic. Native D71/D64 drag stress, console
recovery and clock survival pass, as do VICE scheduler/app smoke and complete
bank-0/bank-1 bitmap equality. Primitive timer counts improve about 12% for
lines and 24% for fills. The same active-display native script reduces worst
partial/cached drag-release latency 348/619 → 290/541 PAL frames. Cached
repaint is still much too slow, so issue #6 remains open; this does not finish
Tasking 0.1. Exact evidence is in
`bench/results/2026-09-28-graphics-raster-integration/`.

Next: review/test this integrated disk on physical C128, then design a bounded
cached-compositor continuation with explicit ownership and cancellation.
Consume the 49-byte reserve only under placement gates; if it cannot cover
the state, make the service-placement decision explicitly. Do not introduce
recursive service polls into raster loops. General task allocation, per-task
VFS/descriptors/CWD, older tasking hardware gates and preemption remain pending.

## Focused cached replay (issue #6 continuation)

The `graphics-bounded-replay` branch builds on the unmerged raster-integration
branch. The focused xwave damage callback resets its draw cursor and returns;
normal application polls replay up to four cached vertices each without more
Z80 rows. An obscured wave still replays synchronously under the manager's
damage clip to respect windows above it. Host wireframe equivalence, D71/D64
native drag/cancel/console gates, VICE graphics/app smoke and bitmap equality
qualify this narrow increment. Last native drag waits for replay completion,
then checks the worker still recorded exactly 21 leases. Worst tested cached
drag release falls from 541 to 266 PAL frames, but the image takes additional
polls to fill: 674 PAL frames after the last release in the saved native
run. This trades complete-image time for interleaved input. Issue #6 and
real-hardware qualification remain open. See
[the bounded-replay note](docs/BOUNDED-REPLAY.md). The next design decision is
an occlusion-aware, cancellable compositor that bounds damage/chrome/obscured
client work too; do not treat this focused optimization as that compositor.

## Pixel-preserving move-cache spike (issue #6)

`graphics-window-cache-spike` records the next implementation seam in
[WINDOW-MOVE-CACHE.md](docs/WINDOW-MOVE-CACHE.md). A 6,656-byte candidate
bank-1 VIC-window lease at `$4200-$5BFF` can hold xwave's default packed
168×104 image (2,184 bytes) and a tested 220×160 resize (4,480 bytes).
The host-only capture/paste model checks all
source/destination bit alignments, edge masks, VIC row interleave, background
preservation and oversize refusal. This is **not** wired into production;
current boot images still use bounded vertex replay. A full 320×200 surface
does not fit. The standalone machine transfer prototype now passes eleven
cases in each of 1986 and VICE, comparing every pixel, dirty flag, cache guard,
service-page restore and MMU mapping. IRQs are masked and display disabled;
bank ownership under tasks/worker activity and compositor integration remain
unqualified. Its 99-byte common gateway fits the existing workspace, but
the C implementation + gateway source + state need 1,273 bytes against a
49-byte resident reserve, before manager/ABI bindings. Default paste takes
roughly 2–3 seconds at nominal 1 MHz, so do not ship it as a speed fix.
Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-transfer/`.
The measured assembly increment now passes the same eleven bank-transfer
cases plus all 64 alignment pairs/full-width/right-edge row checks in both
emulators. Default paste changes 1.94–2.76 M → 0.325–0.593 M CIA ticks
(4.56–6.87× by paired case), before screen commits. Wrapper + ASM + state
is 1,023 bytes, down 250 but still 974 beyond the resident reserve before
bindings. Its gateway/staging lease spans the complete operation and does not
yield; IRQs remain masked, so this is not a live-input acceptance result.
Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-asm/`.
The runtime placement audit is complete: `make graphics-cache-placement` in
the reference container reconstructs the scheduler payload and measures real
listings/objects. All 3,552 post-shadow bytes have an owner, including 141
packaged padding bytes and 50 unfilled handler-reservation bytes. MODULE is
full; its extra contract byte, guard and stacks are not free. The probe page
overlaps APP1. Evidence: `bench/artifacts/2026-09-28-graphics-cache-placement`.
Next: measure compact in-place ASM display-service raster replacements while
retaining public C entry points and exact semantics. Five routines use 2,023
live CODE bytes; no savings are claimed until replacement/state/helper costs
are measured. Keep savings padded to freeze the shadow/private bindings until
cache + bindings + bounded continuation fit. See
[GRAPHICS-CACHE-PLACEMENT.md](docs/GRAPHICS-CACHE-PLACEMENT.md). Then bounded
lease integration and active-IRQ/input/compositor gates follow.
The first compact fill candidate is now standalone-qualified in 1986/VICE:
clipping stays C; a 102-byte ASM span merges edge masks and marks logical dirty
pages. Full experimental link saves 86 bytes (83 CODE + 3 BSS), with unchanged
helper membership. Bulk fills improve 3.55–3.57×, small-fill matrix 1.29×;
display is off and IRQs masked. Eight PRGs/16 positive records include a fresh
dirty-map crossing, and two deliberate missing-flag records are rejected even
with correct pixels. Evidence: `bench/{artifacts,results}/2026-09-28-graphics-span`.
The unpadded experimental shadow at `$A18A` must never be booted.
The follow-on public pixel entry is also standalone-qualified: 190 ASM CODE,
zero BSS, signed clipping and exact cc65 stack cleanup, saving 87 linked bytes.
Its SP diagnostic was corrected to read into variables before comparisons;
the inline comparison itself pushed a cc65 temporary and falsely failed the
C reference. Sixteen full pixel/dirty/guard/stack records pass both emulators.
Evidence: `bench/{artifacts,results}/2026-09-28-graphics-pixel`.

Both mechanisms are now **installed in the display service**. All 173 net
saved bytes remain named resident padding; the shadow, UAPP, common gateways,
module/stack and scheduler allocations are unchanged. Private bridges regenerate
normally. Cache reserve now totals 222 bytes, leaving at least 801 more before
binding/continuation costs. No pixel move-cache is installed.
Clean parallel build is deterministic. Native D71/D64 pass 32 wave drags each
with a background clock and console cancellation; normal input and VICE
D71/D64 app/scheduler smokes plus complete shadow/VIC equality pass.
The same harness on the saved no-replacement D71 measures maximum partial
release 279→171 frames, complete release 266→167, cancellation 174→140;
remaining replay after the last release is 674→970, not an overall repaint
improvement. Physical C128 and visual resize/overlap tests are pending.
Exact testable disks and evidence:
`bench/{artifacts,results}/2026-09-28-graphics-primitives-integration`.
See [GRAPHICS-PRIMITIVES.md](docs/GRAPHICS-PRIMITIVES.md) for the user test.
The user reports the span/pixel build looks good; that checkpoint is committed
and pushed as `0406805`. This does not identify a physical-HW qualification.

The follow-on shared-raster step is now installed and emulator-qualified:
line stepping remains C but shares the ASM pixel entry; rectangles use four
fill spans; clear is 52-byte ASM. Twelve standalone PRGs/24 records compare
all pixels, dirty flags, stack balance and guards; host geometry oracle passes
1,000 randomized trials. The complete link saves another 294 bytes, held as
named padding; helper membership and frozen placements/ABIs remain unchanged.
Line primitives improve 6–8%, rectangle matrix 4.14×, clear about 10×.
Native D71/D64 32-drag and normal input/clock/console gates, VICE both-format
app/scheduler and full bitmap-equality gates, and deterministic clean build
pass. Same-harness maximum releases are 171/167→107/103 frames; cancellation
is **140→161**, not an improvement; remaining post-release replay is 970→655.
Physical/visual resize and overlap tests remain pending. Exact new test images
and evidence: `bench/{artifacts,results}/2026-09-28-graphics-shared-integration`;
standalone suite: `...-graphics-shared`. See
[GRAPHICS-SHARED.md](docs/GRAPHICS-SHARED.md).

Current cache reserves total 516; **at least 507 more bytes** are needed before
binding/continuation state. Cache remains uninstalled. Next: explicit
service-placement/shared-raster budget investigation with measured alternatives.
Do not promise more optimization can cover the deficit, shrink stacks, move
the shadow, remove commands or claim moves avoid redraw before integration.

The next placement/IRQ increment is now qualified as a **standalone private
bank-1 row overlay**, not a production cache: 213 bytes at bank-1 $4200 inside
a candidate 512-byte lease, packed image $4400-$5BFF (6144), measured/tested
resident binding194 including gateway source, zero resident BSS. That leaves
322 of the 516 reserve before policy, state, delivery and whole-link effects.
Common parameters/staging stay in the existing VIC gateway workspace; neither
$F400 nor shell/filesystem scratch is borrowed (outline tag invalidation is
explicit). Every row restores the kernel map and caller I/D flags; both
emulators pass 66 alignment/edge images plus a 220x160 snapshot, all pixels,
dirty flags and guards, stack balance and active IRQs. Removing only the live
SEI in a negative-control PRG is detected and rejected on both emulators.
Exact evidence: `bench/{artifacts,results}/2026-09-28-window-cache-overlay`.
See [WINDOW-CACHE-OVERLAY.md](docs/WINDOW-CACHE-OVERLAY.md) for reproduce/limits.
Next: measured bank-1 delivery/lifetime ownership, then explicit completed-image
notification and generation-owned bounded cache continuations in the window
service. Do not cache partial or newly raised obscured windows, infer completion
from end-paint, or claim production input/NMI/GUI/HW qualification from this proof.
No new user boot image or cache-enabled move path is available yet.

The subsequent delivery/lifetime increment is now experimental-qualified:
prefix the secondary payload at bank-1 $4200 with the exact 213-byte core;
USOV and activation bytes remain at $5000+, same end $6229, one stage-1 LOAD
address byte changes. The 512-byte core/identity slot survives both-format
VICE boot/xinit/clock/wave/console/shutdown/restart and native 32-drag gates
with background clock and console cancellation. No new resident bytes or
extra LOAD; ordinary disks are unchanged. Delivered core is not invoked.
Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-delivery`.

Pure C cache lease/generation/row policy is host-tested, not production-linked.
Actual cc65 record sizes are lease13/row9; measured bank-1 link is
213 core + 1828 policy + 526 helpers = 2567 bytes, unexecuted. Bank-1
$E700-$EFF0 is the shell's live stack, not scratch. Candidate code4200-4CFF,
private C stack4D00-4DEF, identity4DF0-4DFF, packed image4E00-5BFF (3584)
needs dispatcher/state/stack gates before freezing; default168x104 fits,
220x160 would redraw. Do not confuse it with the delivered 512-byte core
or earlier row-only 6144-byte image candidate.
Next: private C runtime/stack machine proof and measured dispatcher, then
explicit completed-image notification (UAPP ends at CFFF; no D000 append),
generation-owned bounded window-service continuations and whole-link/input/
compositor/HW gates. Current normal build still replays moved windows.
See [WINDOW-CACHE-DELIVERY.md](docs/WINDOW-CACHE-DELIVERY.md).

The private C runtime proof is now standalone-qualified in 1986 and VICE.
Real C policy/helpers execute from bank 1 behind a 118-byte dispatcher:
module2685 code at4200-4C7C, state28 at4CD0-4CEB, private C stack4D00-4DEF,
image4E00-5BFF3584. C gateway59/common source binding83 + row binding194 =277,
leaving239 of516 before marshalling/completion/delivery/NMI/continuation costs.
All26 published ZP bytes are saved/restored, twelve addresses link-asserted;
caller uses bank0EFF0, while bank1E700-EFFF remains independently protected.
547 dispatcher calls/132 rows/66 images and439 calls/208 rows/default168x104 pass full
shadow/dirty/runtime/stack/guard oracles. Three exact one-byte negative controls
detect unsafe IRQ mapping, shifted ZP restoration and using the shell stack,
even with correct pixels. Diagnostic repair is outside the candidate binding.
Lowest observed changed private stack byte4DDE is not a hard depth bound;
do not shrink the240-byte stack. IRQ counter is32bit, allfour I/D modes tested.
Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-c-runtime`.
No production binding, completion notification or cached move is installed.
Next: measure versioned UAPP completion + C manager marshalling/continuation
cost, qualify production delivery/validation and NMI ownership/deferral before
enablement. Preserve53 vectors throughCFFF; do not append atD000, cache partial
or newly raised obscured windows, borrowUSHstack or claim live input/task/Z80/
GUI/HW qualification. See [WINDOW-CACHE-C-RUNTIME.md](docs/WINDOW-CACHE-C-RUNTIME.md).

### Latest graphics checkpoint — 2026-09-28

This supersedes the earlier candidate budgets above. A bounded C command now
combines policy, one row transfer and acknowledgement in one private-runtime
lease. Both emulators pass alignment/edge cases and one capture reused for two
pastes after erasing the source, all pixel/dirty/runtime/stack guards and three
one-byte live fault controls. Candidate module: 3,116 bytes at bank-1
$4200-$4E2B; state 22 at $4EE0-$4EF5; private stack $4F00-$4FEF; packed image
$5000-$5BFF (3,072). Combined resident binding: 241 bytes, not installed.
Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-command`.

The explicit completion seam IS installed: UAPP 0.3 optional header pointer
$CF58, unchanged 53 vectors/ZP, version-gated xwave-only helper. Actual C host
tests and both-format VICE/native boot/input/drag/Ctrl+C/background-clock and
post-drag completion gates pass. Shadow/scheduler and bitmap-equality gates
pass. It spends 158 CODE bytes and no BSS from shared padding (294 → 136);
all primary placements remain frozen. Bootfs is exactly 11,708 bytes: no
application growth without a capacity decision.
Evidence: `bench/{artifacts,results}/2026-09-28-window-completion`.

Remaining padding is 358; the combined binding would leave 117 BEFORE manager,
NMI and delivery integration. Do not claim complete cache fit or skipped plotting.
Next: production-shaped manager continuation/marshalling budget, NMI ownership
and deferral, and exact C-module delivery validation. Preserve existing memory,
stack, service and scheduler contracts and redraw fallback. There is no new
user-visible cached-move build yet; this checkpoint needs no new manual test.
See [WINDOW-CACHE-COMMAND.md](docs/WINDOW-CACHE-COMMAND.md).

Final gate: 736 host tests pass; complete clean parallel `boot all` rebuild and
`placement-check` pass. Both rebuilt disk hashes match the qualified completion
images exactly. Evidence includes the shadow/install/layout blocks in
`bench/results/2026-09-28-window-completion-layout`. No VICE sessions remain.

### Latest graphics checkpoint — deferred NMI, 2026-09-28

This supersedes the 358/117-byte budget immediately above. The production
8502 NMI service is installed: exact eight-byte common stub at FFE2-FFE9,
pending FFF5 and wrapping/coalesced drains FFF6-FFF7. No I/O, MMU writes,
compiler ZP or C in the stub; the pointer IRQ drains only after mapping kernel
I/O and saving registers. Z80 return/bootstrap bytes remain unchanged.
Installation is boot-only before input readiness; RESTORE during boot is not
qualified, nor is RESTORE a reset/cancel command. Physical confirmation remains.

Standalone combined-C NMI stress passes in both emulators, with independently
counted arrivals in worker-flat leases and outside them, exact arrival/drain
totals and complete pixel/dirty/runtime/stack guards. One live STA→BIT opcode
fault retains correct pixels but fails the drain proof. Diagnostic observer
FF20 is NEVER production-linked; that address belongs to TASKGATE in the OS.
Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-nmi`.

Both normal disk formats pass VICE/native boot and continuous CIA2 NMI across
Z80 wave/clock/completion gates. Native additionally uses the real RESTORE
keyboard API and tests typing/history, mouse dragging, foreground Ctrl+C,
console recovery and background-clock survival. Evidence:
`bench/{artifacts,results}/2026-09-28-nmi-integration`, plus the independently
bound `bench/results/2026-09-28-nmi-integration-layout` clear/install/bitmap/
placement gate. Docs and reproduction/manual steps: `docs/WINDOW-CACHE-NMI.md`.

NMI object71 CODE + two JSRs6 =77, no BSS/ZP. Shared padding136→59; remaining
total281. Candidate binding241 leaves only40 BEFORE manager continuation/
marshalling and delivery validation. Actual-link tests prove unchanged primary
segments, all unchanged module footprints except the charged transport/pointer
changes, normal/panic agreement and actual linked call sites. Placement audit
rejects one-byte NMI/pointer growth. Bootfs is still full at11,708 bytes.

Final gate:745 host tests, complete clean parallel `boot all`, placement-check,
and rebuilt-image/input hash equality pass. D71 SHA256:
`afc0f96179c33babb732471596c2ff8006ffdfb4574778c0f6bee570d1ace8b0`;
D64: `06892e171b443af308adcf794979d621ba109559142a7677e942ac9168062786`.
No VICE sessions remain. Changes are uncommitted on graphics-window-cache-spike;
latest user said continue, not commit/push.

Manual test now useful: xinit → xclock & → xwave &, RESTORE during plotting
and after drag, verify mouse/console remain alive; foreground xwave → Ctrl+C
must still leave the background clock alive. RESTORE should not cancel wave.
This is resilience, NOT faster moves: cached GUI moves remain disabled.

Next: measure the production-shaped C manager continuation/marshalling and
identify service-local code savings or a reviewed relocation BEFORE enabling
the combined binding. Completion eligibility alone is not a generation-owned
cache; preserve explicit completion, reject partial/obscured images, bound rows,
handle damage/clock/resize/cancellation and retain redraw fallback. No borrowing
USH/private stacks, common gateways, module guards, app slots or scheduler
padding. Physical NMI confirmation can proceed while the budget work continues.

### Latest graphics checkpoint — manager budget, 2026-09-28

User reports the preceding build looks good; the test platform was not named,
so do not convert that into a platform-identified physical NMI qualification.
This section supersedes the 281/40-byte budget above.

Private C manager savings ARE installed: reset sharing58, chrome geometry
reuse145, intersection arithmetic18 =221. Manager7679 CODE,130 RODATA,88 HIGHBSS;
all other module footprints and primary segment bounds unchanged except the
compensating transport padding59→280. No added helper modules. Explicit private
fastcall annotations saved0 and were NOT applied; public calling conventions
remain unchanged. Host tests compare complete binary drawing/state traces
against the prior C source for geometry/flags/lifecycle/move/resize/close paths.

Remaining total padding502. Combined binding241 leaves261 BEFORE controller,
hooks, source/destination locks and delivery validation. A real isolated bank-0
link of the flow992 CODE+4 RODATA, caller state4 and binding241 is739 bytes
short even after spending ALL502. No new library helpers. Its shadow moves;
it is deliberately UNBOOTABLE and never packaged. Every split ld65 output was
retargeted, and source/provider/object/map/hash evidence is preserved in
`bench/artifacts/2026-09-28-window-manager-budget`. Do not mistake this sizing
map for the normal installed map or repurpose scheduler/app/stack/common space.

The four-byte C continuation (`move_cache_flow.c`/`window_cache_flow.h`) is
host-tested but NOT normal-linked: capture, same-content-generation repeated
pastes, stale/wrong-ticket rejection before touching the shared request, at
most one row per STEP, cancellation/handle reuse/generation wrap, bad geometry
and exhaustive unexpected result tags. It calls the actual C command/policy
in host tests. The original variable-mask result comparison crashed the
reference cc65 optimizer; explicit scalar comparisons compile with full-Oirs.
This is not yet a complete compositor integration: no locks, hooks, private
placement, delivery or live continuation machine qualification.

Both normal formats pass native typing/history/mouse drag/Ctrl+C/background
clock/completion/RESTORE/CIA2-NMI gates and VICE boot/Z80/clock/completion/NMI.
Independent clear/install/tail/bitmap equality gates pass; new audit rejects
manager footprint drift. Evidence: `bench/{artifacts,results}/2026-09-28-window-manager-integration`
and `bench/results/2026-09-28-window-manager-integration-layout`.
Final750 host tests, clean parallel boot/all, placement-check and rebuilt
disk/map/kernel/bootfs hash equality pass. D71:
`5dc9c2bfc00e5c221e77ebcc1737587f2681337841316a2a24f80f2cf1d35db0`;
D64: `1fae55695a76d5e69eb641ed7910f81d3cb88a8c1f31b4cf5aa8a6ca6a24ada6`.
No VICE processes remain. Changes remain uncommitted; user said continue.

Next: measure a direct IN-BANK C controller under the existing SINGLE private
C runtime lease, with only bounded marshalling/hooks resident. Do NOT move the
current flow unchanged: its call to the resident binding would nest/reset its
own MMU/runtime/software stack. Refactor the backend to direct in-bank C calls,
measure the complete module/helper/dispatcher closure, persistent flow/lease
state, guarded240-byte private stack and packed-image capacity. No new layout
is frozen; keep the default168x104 image (2184 bytes) viable and oversize redraw
fallback. Repeat full pixel/dirty/ZP/stack/I/D/IRQ/NMI and real fault controls
for any new placement before delivery and live GUI enablement. Kernel hooks
must freeze capture/paste geometry and invalidate before damage, repaint,
restacking, resize, destruction/reuse or shutdown. Same-generation reuse is a
content ticket, NOT a per-paste nonce; no queued/reentrant continuation calls.

Cached GUI moves remain disabled; no new manual test is needed here. Docs:
`docs/WINDOW-MANAGER-BUDGET.md`. New qualifier invocation uses
`tools/nmi_integration_probe.py --checkpoint 2026-09-28-window-manager-integration --work build/window-manager-integration`
with build/1986/vice actions. `make clean` removed generated work directories,
not the preserved evidence; rebuild before rerunning those tools.

### Latest graphics checkpoint — direct bank-1 controller, 2026-09-28

Standalone controller now FITS and is emulator-qualified; production pixel
cache remains disabled. Read `docs/WINDOW-CACHE-CONTROLLER.md` for layout,
private protocol, evidence and remaining gates. No new manual test yet.

`move_cache_flow.c` has an opt-in IN_BANK direct backend and a private fixed
single-owner STATE specialization; default caller-owned prototype unchanged.
It must not re-enter the resident binding from banked C. Generic and fixed
flows pass the same exhaustive host contract/fault tests; actual fixed C
dispatcher+flow+command+policy is separately host-tested. Address/capacity
parameters default to the older command proof unless explicitly overridden.

First generic full link overflowed CODE by202. Fixed-state flow637 CODE+4 RO
(generic994 CODE), controller209; entire core/helpers closure3977 at4200-5188.
151 code slack; lease13/row9/flow4 at5220-5239; state guard22 at523A-524F;
private C stack240 at5250-533F and16 top guard5340-534F; image5350-5BFF2224,
default2184 leaves40. This layout is qualified only for the standalone proof.
Do not shrink the stack or claim its observed offsetCC is a maximum depth.
The unchanged213-byte row core is verified byte-identical. Gateway217 and
uninstalled binding241 leave261 of502 resident padding before hooks/delivery.
No ordinary kernel-linked module or frozen primary allocation changed.

Private protocol0.1: OP F790 init/invalidate/capture/paste/step0..4;
owner/window handleF792, content ticketF793word, eligibleF795, geometryF7A1;
success result0 publishes phaseF791 and ticketF793, INVALID1/BUSY2 otherwise.
This is NOT the prior raw command phase-tag result protocol. Stale/wrong-owner
STEP must leave request and state unchanged; other rejection scratch is not
promised unchanged. Capture/paste use the module epoch; repeated same-epoch
pastes are deliberate, calls serialized, no queued/reentrant operations.

VICE3.10/1986: alignment132rows476calls66images, repeated capture+two
pastes312rows333calls after destroying original source. Full independent
8000pixel+32dirty oracle, original ticket rejection, cancellation/oversize
fallback checks, all26ZP, hardware stack, caller/worker/USH software stacks,
all I/D modes and IRQ/MMU checks. Actual CIA2NMI reaches worker+kernel and
exact drains=total: 1986alignment8906(worker128), repeated15194(worker104);
VICE8785(worker147),15096(worker109). Four exact live single-byte faults
(SEI/ZP restore/USH-stack/NMI-pending) are detected without pixel corruption.
Diagnostics FF20/FF80 observer/IRQ are NEVER production addresses.
Physical RESTORE/Z80 NMI routing still unqualified; no new hardware claim.

Evidence `bench/{artifacts,results}/2026-09-28-window-cache-controller` with
exact inputs/generated assembly/maps/PRGs/raw/provenance/hash verification.
Tool `tools/window_cache_controller.py` build/run(--engine1986|vice)/preserve.
ca65 source-directory lookup must not consume the older template layout:
copied gateway/core assembly now uses the new include and build asserts C/ASM
address agreement. Preserve refuses overwrite. Changes remain uncommitted.

Next: measure full normal/panic integration delivery of the WHOLE C module
and bounded resident marshalling/hooks/locks within remaining261, then live
GUI/input/task/Z80/completion/cancellation/pixel gates before enabling moves.
Freeze capture source/destination per continuation; invalidate before damage,
clock overlap, repaint, resize, restack, destroy/reuse, shutdown and cancellation.
No borrowing common gateway/stack/module guards, app slots, USH or scheduler
reservations. Bootfs remains exactly full. Normal disks should remain byte-
identical to the manager-integration checkpoint. Final754 host tests and full
clean parallel boot/all + placement-check pass. D71/D64/kernel/maps/bootfs
hashes exactly match the prior checkpoint. The regenerated standalone build
report (all linked/program/source hashes) is byte-identical to the preserved
report after clean. New evidence is safe; transient emulator result directories
were removed by make clean, but the controller build was regenerated. No VICE
sessions remain.

### Latest graphics checkpoint — whole controller delivery, 2026-09-28

Whole controller now cold-boots and survives lifetimes in ISOLATED test disks;
still UNINVOKED there. Ordinary production disks remain unchanged and cached
GUI dragging remains disabled. No new manual test needed. Read
`docs/WINDOW-CACHE-CONTROLLER-DELIVERY.md` before next work.

The complete3977-byte archived machine-qualified module4200-5188 overlaps the
canonical scheduler source5000. New experimental secondary envelope LOAD4200:
module bytes, zero slack5189-520F, VCC2identity0.1 at5210-521F, zero to5FFF,
EXACT canonical scheduler/context/gate payload at6000-7228. Installed scheduler/
context/task-tail homes unchanged; boot source retired before VIC bitmap reuse.
The zero prefix also initializes future state/stack/image, but they are NOT
invoked by these disks. Identity includes length/checksum/entry4200/dispatch42D5/
capacity2224. Every complete4128-byte code/identity capture compares byte-exact.

Measured relocation deltas only: stage1two LOAD/end bytes, scheduler-tail
installerthree source bytes, task activationtwo source bytes, console installer
one checksum byte. Installer lengths unchanged, zero extra resident delivery
bytes. Console checksum is regenerated over composer+new activation bytes and
the build rejects any console byte change beyond checksum operands. ca65 uses
isolated generated constants; no normal build output is overwritten.

Both formats VICE exact slot at boot/xinit/clock/wave/completion/utilities/
shutdown/restart. Native both formats history/input, backgroundclock,32 wave
drags, foregroundCtrlC and console recovery, then exact slot check. Log's
"cached" latency means cached vertices, NOT pixels. No bootchainNMI stress or
physicalHW claim here; standalone C execution/NMI proof is separate.

Tool `tools/window_cache_controller_delivery.py` build/1986/vice/preserve,
work `build/window-cache-controller-delivery`. Reuses mature read-only smoke
functions from `graphics_cache_delivery.py` with explicit CORE_BYTES sizing
(former hardcoded512 captures generalized). All source inputs, emitted artifacts,
experimental disk hashes, exact build-report hash and every raw/log/provenance
file are bound by run reports before archival. Preserve revalidates all expected
captures/formats/32-drag gates and refuses overwrite. No ROMs/full snapshots
preserved. QUALIFIED evidence
`bench/{artifacts,results}/2026-09-28-window-cache-controller-delivery-r1`.
Non-r1 archive is historical/incomplete: archive test caught an omitted
canonical scheduler input copy/hash (bytes were embedded in secondary.prg).
Do not overwrite it or treat it as the final qualification. r1 explicitly
binds/preserves the consumed canonical input and must pass all archive tests.

Next actual normal/panic resident acceptance+compositor integration. Padding
still502, binding241 leaves261 BEFORE runtime validation, hooks/locks/marshalling/
persistent ticket/state. No complete-fit claim yet. Validate code/version/layout
before invoking unvalidated bank-1 C; initial checksum must precede row-core
selfmodification. CommonF7xx workspace is overwritten by other VIC gateways,
so it CANNOT retain a ticket/phase across polls. All state bytes must be charged,
not tucked into someone else's guards. Capture source and paste destination
must be immutable through READY; early drag cancels capture and falls back;
second drag/content mutation/resize/restack/close/handle-reuse/shutdown/cancel
must not resume stale row work. Ordinary recomposition during a move must not
destroy the retained READY cache merely because the source pixels are gone.
Full normal input/task/Z80/CtrlC/completion/overlap/resize/NMI/pixel gates are
required before enabling GUI cache use. Changes remain uncommitted.
Final758 host tests pass, including complete r1 archive/source/output/raw/run
binding checks. Clean parallel boot/all + placement-check passes; normal disk
hashes remain5dc9c2bf… (D71),1fae5569… (D64). Rebuilt experimental report is
byte-identical to r1, proving all listed input/linked/disk hashes regenerate
after clean. Both test disks are rebuilt under the work directory; transient
raw/logs were removed by make clean, not immutable evidence. No VICE sessions
remain. No new manual test yet; this step qualifies delivery, not pixel moves.

### Latest graphics checkpoint — pre-C acceptance and ticket seam, 2026-09-28

Read `docs/WINDOW-CACHE-ACCEPTANCE.md`. Page-bounded validation and persistent
original-ticket reconstruction now pass STANDALONE machine qualification in
VICE 3.10 and 1986. Normal disks are unchanged; no compositor hooks or pixel-
cached GUI dragging are installed. No new manual test yet. Changes remain
uncommitted on `graphics-window-cache-spike`.

New `bench/window-cache-acceptance/{validator,binding}.s` and
`tools/window_cache_acceptance.py` build/run(--engine 1986|vice)/preserve.
Trusted 79-byte validator copied to $F68A maps worker-flat, compares all 16 VCC2
identity bytes, sums ONE page (<=256), restores kernel. No unvalidated C, ZP,
software stack or callback; 16 polls for 3,977 bytes, last 137. Whole initial
sum and exact header required before INIT. Bad header/payload disable the
service; guarded calls return $FF without C. Sum is not authentication or
compensating-change protection. Do not revalidate mutable core after acceptance.

Five explicitly charged writable CODE bytes: acceptance state, checksum/ticket
word, owner, phase. Checksumming reuses ticket until acceptance; successful
commands snapshot original generation/owner/phase while masked; rejects retain
them. STEP reconstructs original ticket and owner, not current common scratch.
The probe replaces common code and poisons checksum/page between validation
polls; poisons common ticket/owner/phase before EVERY row STEP. Full 8,000-pixel
and 32-dirty-byte oracle passes: 132 rows/480 calls/66 images and 312 rows/337
calls/two images. Four commands blocked before acceptance account for +4 versus
the previous controller proof.

Safe pending-NMI drain under kernel I/O after copy/before worker (validator and
raw binding). Without this, outer serialization masks IRQ during copy and a
copy-time pending NMI suppresses worker observations. Each JSR charged three
bytes, existing installed drain already budgeted. Diagnostic CIA2 period 768
avoids 512-cycle CIA1 phase-lock. Stress positives: native 12,104 NMI (302 worker)
and 20,749 (159); VICE 12,034 (273) and 20,757 (237), exact drains=totals.
All 26 ZP bytes, I/D, MMU, caller/worker/USH/hardware stacks and guards pass.
Observed private offset $CC is not maximum-depth proof. $FF20/$FF80 observer/
IRQ ONLY standalone; physical RESTORE/Z80 NMI routing still unqualified.

Bad payload/header single-byte controls reject after 16/one polls, six blocked
commands, zero rows/pixels, all 26 private bytes stay $6D, no private C stack use
(seed intact). Actual single-byte SEI/ZP/USH stack/NMI pending faults trigger
only expected fields and fail positive oracle while pixel output remains exact.
Separate original PRGs prove one-byte changes despite different probe variants.
Extended diagnostic seed/scanner exceed old 128-byte signed-X copy limit;
unsigned loops qualified. Label insertion must match `\nscan:\n`, NOT install_scan.

REAL FOOTPRINT: raw 244 (217 gateway + copy/drain), seam 309 INCLUDES 79 validator
source and five state bytes, total 553 vs 502 available => 51 SHORT BEFORE hooks.
All objects have zero BSS/ZP. No production link/fit claim. Next recover bytes
via measured private savings/shared-installer refactor, then all actual normal/
panic hooks/locks/marshalling before live GUI tests. Do not borrow frozen shadow,
scheduler/apps/USH/common workspace/guards. Existing manager fixed-layout tests
require a new host trace/emulator qualification for any further savings.

Capture source and paste destination frozen until READY. Early drag cancels
capture/falls back; content mutation/clock overlap/resize/restack/close/handle
reuse/shutdown/cancellation invalidate stale ownership before writing. Moving
retained READY image cannot be invalidated just because ordinary background
recomposition erases source pixels. Need complete input/task/Z80/CtrlC/completion/
pixel/overlap gates before cached GUI enabled. Normal moves replay vertices,
NOT cached pixels.

Immutable `bench/{artifacts,results}/2026-09-28-window-cache-acceptance`
contains exact sources/generated assembly/maps/PRGs/raw/provenance/report hashes.
Run records bind full build-report hash plus programs/raw; preserve verifies all
and refuses overwrite. Five new host tests check decoders/state/no-C rejection/
budget/actual one-byte faults/archive hashes. make check: 763 tests, py_compile
and checksums pass. Full clean parallel boot/all/placement-check pass. Normal
D71/D64/kernel/maps/bootfs hashes match previous checkpoint exactly. Rebuilt
acceptance report is byte-identical to archive after clean; linked/program/source
hashes regenerate. make clean removed transient work raw/logs, not immutable
evidence; isolated PRGs rebuilt. No VICE sessions remain.

### Latest graphics checkpoint — compact validated transport, 2026-09-28

Read `docs/WINDOW-CACHE-COMPACT.md`. Standalone footprint reduction qualified
in VICE 3.10 and 1986. Still no normal resident link, revised-module disk
delivery, compositor hooks or pixel-cached GUI moves. No new manual test yet.
Changes remain uncommitted on `graphics-window-cache-spike`.

`tools/window_cache_compact.py` measure/module/build/run/preserve builds an
isolated specialization, reusing the acceptance diagnostic. Work directory
`build/bench/window-cache-compact`; new assembly source
`bench/window-cache-compact/raw.s`. Generic/production C flow remains unchanged.
Generated fixed-flow C rejects capture/paste geometry pointers other than the
shared request, then omits self-copying that request. Flow CODE 637→570.
Actual C dispatcher already uses the shared pointer. Host checks prove foreign
or NULL geometry rejection before mutation, capture/two-paste rows, cancellation
and generation wrap. Other C policy/command/controller sources unchanged.

Gateway is 196 bytes instead of 217: outer guard now owns PHP/SEI/PLP, common
command still CLDs; omit zero loads before MMU preset strobes; compute logical
dirty end from OFFSET+(RAWCOUNT-1)*8 with both carries. Full pixels/dirty and
all low-byte/count carry combinations qualified. UNCHANGED 213-byte row core.
Gateway source is appended to bank-1 module at $5146-$5209 and included in the
INITIAL checksum. Module 4,106 bytes, six spare before VCC2 $5210. All private
state, guarded 240-byte stack and 2,224-byte image remain unchanged. Do not
expand module past identity or shrink those allocations to fit future hooks.

Trusted raw wrapper installs a 20-byte loader at $F75A-$F76D. Loader copies
accepted source from worker RAM to common $F68A-$F74D, restores kernel I/O,
returns before the command. Source copy cannot overwrite the executing loader;
assembler guards enforce gateway<=208 and loader end<=PARAM. Raw called ONLY
behind accepted state + serialized resident guard, never directly. Same pending
NMI drain and common-workspace ticket reconstruction rules as previous proof.
Immutable banked source is not the common self-modifying copied gateway.

FULLY CHARGED: raw51 + seam309 (includes validator79/state5) + diagnostic patch
helper11 =371 resident bytes. Recover182 from553, aggregate headroom131 from502
BEFORE real manager hooks. Raw's diagnostic call remains charged. No complete
normal/panic allocation/fit claim; sources have zero BSS/ZP. Earlier delivered
3977-byte module DOES NOT contain this banked gateway source. Deliver this new
module before invoking new transport in an OS image.

Validation now17 polls, last10 bytes. Initial test caught the old hardcoded16
poll bound; generator/record decode derive it from module size. Page arithmetic
also handles exact256 multiples (last count0 encodes a full page, not an extra
page). Parent acceptance tool now accepts optional module/gateway/raw/driver/
source/fault-selector inputs; default CLI remains the older proof. Historical
archive immutable; current tool source hash has changed. Decoder default still
16 for old snapshots, new runs/preserve pass measured page_calls explicitly.

Both emulators: alignment132 rows/480 calls/66 images; repeated312/337/2 after
destroying original source, full8000+32 oracle exact. Poisoned common parameters
and original-ticket reconstruction still pass. Bad payload/header reject after
17/one polls; private26 bytes stay6D, stack unused, pixels untouched. Positives
NMI exact drains: native11981(worker475)/20762(338), VICE11937(483)/20647(339).
Coverage includes the worker source-copy lease; do not claim C-only arrivals.
All26ZP/I-D/MMU/stack/guard gates pass; observed private offsetCC unchanged.
Physical RESTORE/Z80 NMI routing still unqualified.

Four exact single-byte faults still fail positive oracle and preserve pixels.
ZP/USH-stack faults now patch the COPIED gateway via diagnostic helper after
acceptance: baseline writes original bytes, mutated immediate writes bad byte.
Do NOT alter accepted source and then weaken checksum to obtain a runtime
fault. SEI/NMI-pending faults remain actual instruction changes. Intentional
SEI leak may race NMI accounting (VICE drains differs by1); its negative gate
does not require positive NMI equality. All positive cases do require equality.

Evidence `bench/{artifacts,results}/2026-09-28-window-cache-compact` binds every
source/generated C/ASM/module/map/program/compiler flag, report/program/raw
hash and emulator provenance. New four host tests qualify C pointer semantics,
carry/page boundaries, full charged budget/allocations and both-emulator live
fault/archive hashes. make check767 tests and checksums pass. Full clean
parallel boot/all/placement-check pass; normal D71/D64/kernel/maps/bootfs hashes
exactly match prior checkpoint. Regenerated compact report is byte-identical
to archive after clean. Transient raw/logs removed by make clean, immutable
evidence retained; diagnostic PRGs rebuilt. No VICE processes remain.

NEXT: cold-boot/lifetime delivery of this revised module, then real normal/panic
resident hooks/locks/marshalling link within padding (or further measured private
savings if needed). Do not call aggregate131 a proved link fit. Freeze capture
source and paste destination until READY; early drag cancels capture/falls back;
invalidate ownership before content/overlap/resize/restack/close/reuse/shutdown/
cancel. Retained READY pixels must survive ordinary move background repair.
Full live GUI/input/task/Z80/CtrlC/completion/overlap/pixel gates before enabling.

## Compact module delivery and real transport link — 2026-09-28

Read `docs/WINDOW-CACHE-COMPACT-DELIVERY.md` before the next increment.
NEW delivery proof qualifies the exact4,106-byte module INCLUDING its banked
196-byte gateway source. Earlier controller delivery was3,977 without source.
Normal production sources/links/disks are unchanged by this increment; cache
is still not installed or invoked. No new manual test. Do not merge partial
placement proofs into a claim of active GUI caching.

`tools/window_cache_compact_delivery.py` wraps the existing isolated recipe.
Parent build accepts qualified module_path/extra_inputs; module must be listed
in verified proof manifest. Wrapper verifies map/module/gateway hashes and
exact gateway suffix. Same scheduler source6000, LOAD4200, endpoint7229,
same strict operand/checksum deltas, zero new resident delivery bytes.
Cold boot D71/D64 in VICE3.10: exact4,128-byte slot through eight lifetime
checkpoints (boot/xinit/clock/wave/complete/utilities/shutdown/restart).
1986: exact slot both formats after32 wave drags each with clock running,
completed-wave cancellation and console-alive command. This is NOT a cached
move performance test. Test disks D71 sha5339634c... / D64 d2194468....
Full artifacts/results at `2026-09-28-window-cache-compact-delivery` bind
qualified compact inputs, canonical scheduler, all derived installers/maps,
disks, full raw captures, logs, provenance and run/report hashes. Four tests.

`tools/window_cache_resident_link.py` replays actual normal AND panic recipes
in isolation and retargets EVERY split file. Qualified sources raw51+seam309
(includes validator79 and state5)+diagnostic helper11 =371CODE; all added
objects zeroBSS/DATA/ZP/RODATA. Spend49scratch+42primitive+280shared padding;
131primitive padding remains. Outline8 untouched. These are ordinary CODE
segments: whole-link placement, not forcing each object into an independent
fixed padding hole. Every segment matches both baselines, exact shadow
A1E0-C11F8000, LOW/HIGHBSS, module/common/syscall regions unchanged. Runtime
helper module sets/sizes unchanged, UAPP ZP link assertions pass. Five seam
fields live in charged writable CODE with exact offsets0/1/3/4.

This closes REAL transport placement only. NO adapter/hook bytes charged yet.
Experimental binaries explicitly UNBOOTABLE because private provider addresses
move and derived import bridges are stale. Do not package/run them. No OS
entry/poll or manager callback references the new seam. State init is only
relevant once the integrated startup path exists. Artifacts
`2026-09-28-window-cache-resident-link` include real provider objects, source/
generated inputs, normal/panic maps, split binaries and before/after normal
provider/output hashes. Three tests. make check774 tests/checksums/pycompile
pass; container boot/all are up-to-date and placement-check passes. Normal
D71/D64 remain5dc9c2bf.../1fae5569.... No VICE sessions remain.

NEXT: real C compositor adapter/hook/lock sizing within131 residual padding
(or further measured private C savings if it exceeds). Then regenerate all
private bridges and package integrated isolated disks, acceptance/polls/init
and actual bounded row invocation. Source/destination frozen untilREADY;
early drag cancels capture/fallback. Invalidate before content/overlap/resize/
restack/close/reuse/shutdown/cancel, but keep READY image during own move's
background repair. Reconstruct original ticket after shared-workspace reuse.
Full live GUI/input/task/Z80/CtrlC/completion/overlap/pixel gates before enable.

## Integrated cached-move candidate — 2026-09-28

Read `docs/WINDOW-CACHE-LIVE.md`. This supersedes the previous NEXT sizing/link
step. User asked to continue until there is something testable: stop here for
manual visual/input feedback, not at another placement-only checkpoint.

Private sources live in `bench/window-cache-manager/{adapter,native}.inc` and
`tools/window_cache_manager.py`; packaging/qualification in
`tools/window_cache_live.py`. The generated private repository is
`build/window-cache-live/repo`. Normal build sources/outputs are not switched
to cache hooks. Exact disks to test: `udeks-cache.d64/.d71`, NOT the private
repo's ordinary boot disks. Preserve at
`bench/artifacts/2026-09-28-window-cache-live/build/` with matching results.

Local register pointers save521 bytes with complete host trace equivalence.
487 bytes of adapter/hooks yield netmanager−34: CODE7645, RO130, HIGHBSS88.
Full transport377 (371closure+6commandwrapper), no new BSS/ZP/helper; pad159.
All normal/panic segments remain exact, shadowA1E0-C11F. All private bridges,
checksum installers, managed apps and bootfs rebuilt through actual recipes;
both incremental and cleanparallel test disks agree. Normal D71/D64 remain
5dc9c2bf.../1fae5569.... Runtime/module/delivery allocation unchanged.

At most4 STEP rows/poll; each row releases MMU/runtime/IRQ ownership, dirty
pages commit once/batch. Source/destination locks prevent writes while capture/
paste is active. Early drag cancels capture/fallback. Move retains owner image
through background repair. Lower clock repair also skips cached owner and
pastes retained pixels; no app replay. Resident phase82 marks frontend repair
busy while banked phase remains2; next PASTE sets3 and finishes2. New clicks
defer during paste, pointer IRQ/keyboard/task polls remain active. Content/
resize/restack/create/destroy/reuse/reset/cancel take invalidation/fallback.

Both native formats:16 moves, all8 horizontal alignments, every17472 pixel
matches shadow AND VIC, painter count and21 Z80 leases unchanged, active clock,
partialpaint fallback, partialpaste CtrlC, oversized resize fallback, handle
reuse, typed/history/echo/shutdown/restart, RESTORE/CIA2 NMI pressure, guards.
VICE both formats: captured17472 pixels/full8000 shadow=bitmap, immutable source,
guard, NMI drain/handoff, shutdown/restart. Native VICE input/drag NOT qualified.
Private xwave status uses callback handle BEFORE initial painting, because
window_create calls painter before assigning the app's global handle; initial
diagnostic handle would otherwise stay0 when cached moves never call painter.
Native runner's PC Minus was C128 Plus; choose positional Equals for C128 Minus
so xinit-q test remains strict. Sibling1986 source is untouched.

Runtime slot is not byte-identical to uninvoked delivery: row core has two
selfmod address operands and4 scratch bytes. Live oracle permits only those8
bytes, validates operands against exact last row, and compares everything else
(controller/gateway/header/slack) exactly. Tests inject pointer/opcode/header/
padding changes to ensure failure. Full VSF containsROM and is NOT archived.

Sample release60–81 PALframes plus settledpaste139–164, roughly4–5s combined:
reuse is proved, responsiveness is NOT accepted. Next after manual feedback:
reduce synchronous background/clock and dirty commit cost, then consider normal
promotion. Physical RESTORE/Z80 routing remains open. No commit/push this turn.

Final qualification: make check781 tests/checksums/pycompile pass; normal
container boot/all are up-to-date and placement-check passes. git diff--check
passes. Test artifacts/results are preserved with immutable SHA256SUMS and
report-to-run bindings; no VICE sessions remain. Normal disk hashes unchanged.

## Live-cache manual feedback — 2026-09-28

User: "it all looks good to me." Record positive manual feedback for the
presented live-cache candidate; do not infer the platform, exact cases, physical
RESTORE/Z80 routing or a latency measurement. Preserved evidence is unchanged.
Normal cache hooks are still not enabled, and no commit/push was requested.

NEXT engineering gate: measure background-repair versus paste/commit cost,
including number of256-byte dirty-page copies per move. The current4-row batch
can recopy a tiled bitmap page across adjacent batches. Evaluate bounded
commit/row alternatives against the existing native-input/CtrlC/clock/fullpixel/
guard gates before normal promotion; do not just raise batch size without
measuring console latency. The previous "stop for manual feedback" is satisfied.

## Band-boundary repaint follow-up — 2026-09-28

User authorized the repaint work. Read `docs/WINDOW-CACHE-REPAINT.md`.
New tool `tools/window_cache_repaint.py` generates reference/tiled private links
via the live builder; baseline and old manual artifacts remain immutable.
New test disk is under `bench/artifacts/2026-09-28-window-cache-repaint-tiled/build/`
or `build/window-cache-repaint/tiled/udeks-cache.d64/.d71`. NOT private repo's
ordinary boot disks. Normal cache hooks remain disabled.

Keep max4rows/poll; end pasted batches at8scanline boundary and commit only
there/final/error. Read lastSTEP offsetF780 low3bits before another gateway;
IRQ/NMI don't borrow it. Partialbands staydirty. Source/destination locks and
row runtime/MMU/IRQ restoration unchanged. No newstate/helper/ABI/modulebytes.
ManagerCODE7677 (+32vsacceptedcandidate), RO130/HIGHBSS88, transport377,pad127.
All normal/panic segments and shadowA1E0-C11F remainexact; bridges regenerate.

Read-only native page-entry/stack-derived return breakpoints count real page
copies/cycles, continuing the same partialframe. Paired D71/D64 medians:
pastecopies56→22.5, copycycles709451.5→288659.5, pasteframes156.5→129.5,
release+paste220→194.5, CtrlC211→156. No maskinginput/IRQ or OS patches.
Worstpaste164→313 due coincident clockminute repair; DON'T claim worstcase
improvement or accept responsiveness. Clockpaint counter in log attributes it.
NEXT: visible-damage/occlusion-aware clock/background repair, not a larger row
budget; preserve pixel/input/cancel/guard/ownership gates and hardware gates.

Initial tiled run exposed realshutdown bug: D011ANDCF copied live rasterhigh
to targethigh; sampler target482 (>PAL312), phase1stuck, OS Return held although
physicalkey released. Fixed normal `vic_graphics.s` toAND4F, oneimmediatebyte
2328, no footprintgrowth. Both comparisonvariants usefix. Native tiledshutdown
at295 retains226 and keyboard/restart pass; reference238→200. Sanitized failure
disk/kernel/map/runner/log/state preserved; NO ROMbearing VSF in archives.
Source/arithmetic and failed-vs-fixed onebyte-diff tests lock the correction.
Normaldisks NOW d99463d6.../65a37c26... due this correctnessfix; older unchanged
hash statements describe earlier checkpoints. Newcache disks d1be51f9.../
af502122.... Incremental/cleanparallel tiled builds match.

Final measured clock attribution: native tiled move7 has2 clock paints during
release/paste and313 pasteframes; all other paired moves have1. Its actual
page-copy count69 includes extra clockbackground plus a second presentation;
do not filter that sample out. All paired and tiled native records pass both
formats; VICE both variants/formats pass capture/bitmap/NMI/restart. Archives
`2026-09-28-window-cache-repaint-{baseline,tiled}` preserve complete source/map/
disk/run bindings andcomparison; failure/manifest locks originalCF kernel to
fixed4F by exactonebytediff. No ROM-bearing snapshots archived.
make check787 tests/checksums/pycompile pass; normalboot/all/placement-check and
gitdiff--check pass. No VICE remains. No commit/push or cache-default promotion.

User feedback 2026-09-28: "looks ok" for the presented tiled repaint candidate.
Platform and individual test cases were not specified; this is positive manual
feedback, not physical-C128, RESTORE/NMI, or worst-case performance qualification.
Next engineering gate remains visible-damage/occlusion-aware clock/background
repair. No commit/push or normal-cache promotion is implied by this feedback.

2026-09-28 visible clock/background repair candidate:
`tools/window_cache_occlusion.py`, doc WINDOW-CACHE-OCCLUSION.md. Separate disks
only, normal images untouched. Generic geometry fast paths: disjoint damage
does not paste; fully hidden damage does not draw; full-width/bottom-covered
damage repairs only its exposed upper strip. Other overlaps keep bounded
background/paste fallback, now with damage limited to the requesting window.
Hidden clients receive one empty-clip callback to acknowledge the update;
otherwise clock previous-minute state would cause repeated repairs per poll.
No app-ID policy, app binary, public ABI, BSS or banked module changes.
Register private window parameters pay the cost. Linked manager CODE7695,
RO130/HIGHBSS88, transport377, heldpad87; all normal/panic segments/helpers
unchanged, shadowA1E0-C11F. Cleanparallel disks match incremental: D64d4e2a96c...
and D71e27ebf93.... Normal still65a37c26.../d99463d6....

Matched native date changes after exact native mouse drags (D71==D64):
clock fully hidden (109,40) 278→119 frames, 40→0 pagecopies;
upper4-row strip (109,65) 278→126, 44→2;
complex overlap (144,88) 267→254, 40→33. One callback/change, no repeat over120
frames, no wave painter/Z80 reacquisition. Every8000-byte case canvas matches
reference and bank0/bank1; retained17472pixel oracle passes. Original16moves
worst sampled settledpaste313→163, medianfullmove194.5→194 (NOT general speedup).
Complex overlap still~5s: next optimize selective partial-overlap repair.
Physical/input/RESTORE gate and normal cache promotion remain separate.

Host pixel oracle117 geometries + disjoint/highX/three-layer/uncovering;
nativeinput/earlydrag/16moves/partialpasteCtrlC/resize/guards/console/restart;
VICEbothformats capture/pixels/NMI/restart, NOT nativeVICEdrag qualification.
Read-only profiler ignores only identical-frame/register/SP entry redispatch
after IRQ/NMI (3 candidate,0 reference), preserving all interrupt cycles. Clock
timing ends only after leaseREADY AND emptydirtymap AND pagecallreturn.
Archives `2026-09-28-window-cache-occlusion{,-reference}` bind source/maps/disks/
runners/provenance/logs/pixels/comparison, no ROM-bearing snapshots. No push or
normal cache promotion; prompt user to test candidate disks next.

Final gate: make check793 tests/manifests/pycompile pass, normalcontainerboot/all
and actualobjectplacement-check OK, gitdiff--check OK. No VICE remains. User
reported "looks good" on 2026-09-29 for the presented occlusion candidate.
Platform and individual cases unspecified; record positive manual feedback,
not physical/input/RESTORE or universal responsiveness qualification.
Next engineering step remains selective partial-overlap repair. No commit/push
or normal-cache promotion is authorized by this feedback.

2026-09-29 prefix/row-range repair is implemented and emulator-qualified as
another isolated candidate; see docs/WINDOW-CACHE-PARTIAL.md. First qualified
the banked provider independently (`tools/window_cache_partial.py`), then its
C compositor adapter (`tools/window_cache_partial_manager.py`). Preserve both
archives under bench/{artifacts,results}/2026-09-29-window-cache-partial{,-manager}.

Private command0.2 adds op6, PARAM F78A first/F78B end-exclusive/F78C-D prefix
width. Validate before mutation; retain original geometry and source stride;
only rows[first,end) and the left prefix are restored. Outside pixels unchanged.
Range metadata3 initialized DATA bytes are charged INSIDE the module, not a new
allocation. Private fixed-lease policy rejects wrong pointers; generic normal
policy remains unchanged. Core213/common gateway196 byte-identical to prior
proof. Module3971, identityslack141, gateway source50BF (loader-derived; removed
VICE's hardcoded5146 source range). VCC2 layout0.1 unchanged; checksum/header and
validator rebuilt for exact new provider. Do not mix provider/validator versions.

Standalone host tests cover alignments/widths/ranges/rejection snapshots,
corrupt metadata, full paste after partial, cancel/recapture. Compiled1986/VICE
all64bit alignments +52prefix rows17..66 pass completepixel/dirtymap oracle,
IRQ/I-D/ZP/HW-SWstack/shell/guards/NMI and six negative controls. Raw/state
decoders have mutation tests and hash-bound source/maps/executables/results.

Manager reuses clipped top/bottom/right and marshals only AFTER callbacks finish
(sharedVICworkspace can be clobbered); resetclip before the command. Host tests
match all screen pixels/117placements +disjoint/highX/three-layer/uncovering and
deliberate callback argument clobber. CODE7750 (+55), RO130/HIGHBSS88 unchanged,
transport377, heldpad32. All normal/panic segments/helpers exact. Clean private
parallel build equals incremental D64 13433b995d.../D71 fded272e8e.... Normal
still65a37c26.../d99463d6.... No source change in1986; no normal cache promotion.

Native bothformats: hidden119frames/0pages and upperstrip126/2 unchanged;
partial-overlap254/33 ->195/23 (~23%faster). Whole8000byte canvases match the
saved occlusion reference, same emulator provenance. One callback/change, no
repeat120frames, no wave painter/Z80 reacquisition. Same native earlydrag,
16moves, partialpasteCtrlC, typing, resizefallback, guards/NMI/restart pass.
VICEbothformats capture/fullpixels/NMI/restart, NOT nativeVICE dragging.
195frames remains~3.9s: no general responsiveness claim. Next after manual
feedback: bound/reduce synchronous lower-window composition, not more row
budget or larger cache. Prompt user to test this disk; physical/input/RESTORE
and default-promotion gates stay separate. No commit/push requested this turn.

Final qualification: make check803 tests +all preserved manifests/pycompile
pass; normalcontainer boot/all up-to-date and actualplacement-check OK;
gitdiff--check OK; no x128 sessions remain. Candidate archives/comparison/
clean-build proof saved. Subsequent feedback below supersedes the untested status.

2026-09-29 user rejected prefix candidate: considerable xclock drag-start delay.
Native reproduction exposed a missing case: xclock over completed xwave takes
265 PAL frames before outline (5.3s), clock alone17. Old suites moved xwave,
not xclock-over-wave. This is synchronous 8502 background wireframe replay,
not a new Z80 job or a mouse-driver regression. User approved temporarily blank
background while dragging, repairing it after release.

Isolated deferred candidate qualified; docs/WINDOW-DRAG-START.md. Existing
compositor gains private erase-only selector255; begin invokes no painters.
Valid CACHED_MOVE preserves image ownership; release repairs full old/new union.
Manager7762 (+12), RO130/HIGHBSS88, transport377, heldpad20; all normal/panic
segments/helpers unchanged. Cleanparallel private disks identical; normal still
65a37c26.../d99463d6.... Native D71/D64 clock-alone17 unchanged, overlap265→16
frames (~0.32s); gate<=30, mouse outline movement, no newZ80, fullshadow/VIC,
CtrlC+console typing+shutdown. Full prior native16move/cancel/resize/guards/NMI/
restart and VICEbothformats pass. Host releasecanvas matches prior after move,
resize, destruction during drag and cachedwave move; forcedclock canvases exact.
Release/background composition remains synchronous: no universal speed claim.
Archives2026-09-29-window-drag-start include timing source/runners/logs vs previous
prefix archive and clean-build proof, no ROM snapshots. D644872d6aa...,
D71e3eaa384.... Prompt user to test this separate disk next; no commit/push,
physical qualification or normal cache promotion authorized by this feedback.

Final gate for deferred drag: make check808 tests/manifests/pycompile pass;
normalcontainer boot/all up-to-date and actualobjectplacement-check OK;
gitdiff--check clean; normal disk hashes unchanged; no x128 sessions remain.

User feedback on deferred-drag candidate: "ok much better now, continue".
Record positive manual drag-start feedback, platform unspecified, not physical
qualification or normal-cache promotion. Next reduce the synchronous exposed
background replay after release; preserve fast outline start and input gates.

Architectural direction from user: projection/wireframe optimization belongs
to xwave, NOT the entire windowing system. Preserve this boundary in future
work. App owns samples/projection/render caches; manager stays generic about
composition/damage/clipping/stacking. The app-local projection prototype and
its tools/tests/evidence remain separate from this window-manager milestone.

2026-09-29 merge scope approved by user: commit the generic manager foundations,
tests and opt-in evidence; exclude the xwave projection experiment and its
app-transform build hooks. Do not enable caching/deferred dragging in normal
builds as a side effect of merging. Keep the minimal xwave image-completion
notification needed by the generic UAPP contract, not an app-specific cache.
Next: default-build delivery/integration as explicit manager work, then fresh
native keyboard/mouse/CtrlC/resize/RESTORE and physical acceptance gates.
See docs/WINDOW-MANAGER-MILESTONE.md for scope and outstanding limitations.

Scoped clean-worktree merge gate: make check808 tests/manifests/pycompile pass;
fresh parallel make boot/all and realobjectplacement-check pass. Default disks
are byte-identical to the previously qualified normal image (D6465a37c26...,
D71d99463d6...). Xwave projection tools/tests/images and build hooks excluded;
default cached/deferred dragging remains disabled. User approved this scope.

2026-09-29 issue #12 / graphics-window-manager-integration: the next manager
step now has a regular source-built WINDOW_CACHE=1 configuration. It promotes
the accepted generic compositor and bank-1 controller under the window service,
regenerates identity/checksum/page/gateway bindings from the actual link, and
rejects any normal/panic segment drift before packaging. Manager7762/RO130/
HIGHBSS88, charged transport377, heldpad20, shadow$A1E0-$C11F; no published
runtime or scheduler destinations move. Disk LOAD$4200 is distinct from USOV
temporary source$6000; a boot regression caught and corrected conflating them.

Default WINDOW_CACHE=0 remains off. Fresh source-only parallel builds and
1->0->1 switching reproduce both selected disks and the old default hashes.
No archived binary or app-transform path is needed. Xwave projection work stays
local/separate; no app BSS or projection table is added by this integration.
Runtime-only probes avoid the local xwave private-builder hooks.

Actual selected D71/D64 pass native1986 input/history, early/cached moves,
overlap repairs, oversize resize fallback, partial-pasteCtrlC, console typing,
guards/NMI and shutdown/restart; VICEbothformats fullpixels/NMI/restart pass.
Evidence under bench/{artifacts,results}/2026-09-29-window-cache-integration.
Selected D64c00d8936..., D7100ab0c99...; stable manual copies remain under
build/window-cache-integration/udeks-cache.{d64,d71}. See
docs/WINDOW-CACHE-INTEGRATION.md for build commands and manual acceptance.
Background release repair stays synchronous/slow; native VICE mouse and physical
input/RESTORE acceptance remain open before changing the default policy.

Final selected-build gate: make check825 tests/manifests/pycompile pass
(including the four still-local xwave projection tests; integration does not
use that prototype). Actual selected clock-only/clock-over-wave drag starts
are17PALframes in both formats, with a <=30 guard, outline motion, drained
repaint/fullshadowVIC, CtrlC+typing+shutdown. Timing evidence is separate from
the full compositor suite. A fixed300frame sample caught a subsequent periodic
clock commit; the read-only observer now waits for the dirty map to drain.
Immutable integration manifests bind inputs/runners/logs/pixels/clean switching.
Default build outputs restored to65a37c26.../d99463d6..., actualplacement OK;
integrated manual copies retained. No commit/push or default promotion yet.

2026-09-29 user feedback on the selected integration: "it looks ok on real HW".
Record positive overall physical-machine manual feedback. No itemized hardware
log, format/hash confirmation or explicit RESTORE/input-afterward result was
provided; do not infer those or authorize a default change/commit/merge from
this report alone. RESTORE + subsequent input confirmation was requested;
the subsequent report below resolves that gate. Keep xwave work separate.

2026-09-29 follow-up hardware confirmation: the user pressed RESTORE while
dragging a window on real hardware and input still worked afterward. Together
with the preceding positive overall feedback, this closes the requested manual
integration acceptance gate. Do not ask for that check again or infer exhaustive
physical NMI-source/Z80-handoff coverage. WINDOW_CACHE=0 remains unchanged until
promotion is approved. Recommended next: promote the accepted configuration,
commit/push the scoped window-manager work and review/merge via PR, keeping the
local xwave projection experiment out of that scope.

2026-09-29 user approved default promotion, scoped commit/push and PR merge.
WINDOW_CACHE now defaults to1; explicit0 retains the old compositor. Integration
contains no xwave projection tools, table, app changes or prototype evidence.
Historical opt-in qualification archives are immutable. Verify a fresh scoped
default build against their accepted D64/D71 hashes before publishing. Requested
hardware acceptance is complete, not exhaustive physical NMI/Z80 coverage.
Next manager work: bounded release/background composition, which is still
synchronous and slow; keep application-specific rendering outside the manager.
Scoped promotion gate:821 host tests pass; clean parallel default boot/all/panic
and placement-check pass. Default→0→default without clean reproduces selected
D64c00d8936.../D7100ab0c99... and prior65a37c26.../d99463d6... exactly. The kernel
dfef7e6d... and module758965e4... match the archived qualified integration.

2026-09-29 next manager work: issue #14, branch graphics-bounded-repaint in
build/window-manager-bounded-repaint. Original workspace's local xwave prototype
is preserved on main and excluded. Initial increment is a read-only native
entry/return observer for release/background service gaps; normal code/disks
unchanged. Plan and placement/painter-contract gates are in
docs/WINDOW-REPAINT-CONTINUATION.md. A deferred whole void-painter callback is
not a bounded stage. Qualify generic manager-owned stages and any optional
painter continuation separately from application rendering optimization.
First baseline complete on default disks in1986 (reference-containerSDL): D71
andD64 produce identical18case records. Clock-only keyboardgap941873 buscycles;
median of16wave per-move maxima1228648.5; clock-over-wave5862866 (~6s nominalPAL),
with one managercall5838505. Observer/source/runner/map/disk/provenance preserved
under2026-09-29-window-repaint-baseline; no ROM snapshots archived. Seven new
tests; scoped fullsuite828. Normal OS/app code and disk hashes unchanged.
Next: host-tested generic damage/continuation/cancellation seam plus a measured
placement budget; synchronous painter compatibility must not be called bounded.

2026-09-29 continuation reference implemented in window_repaint.h and
src/services/window/repaint_policy.c, NOT production-linked. Caller-owned job
unions pending damage, clears <=4rows/action, selects visible windows by rank,
emits chrome/client or retained-restore work and commits in resumable steps.
No callbacks/app/cache pointers stored. Generation+scene+phase+rank+handle+cursor
receipts reject stale/replayed ack; scene_changed fences work before table
mutation and unions active/pending/old-new extents. Validate BEFORE any drawing,
with no yield until that bounded operation ends. Abort is whole-surface shutdown,
not window-close; exhaustion fails closed, no generation/cursor wrap.
17 strict host tests pass including independent full320x200 mock pixel equality
after interruption/move/resize/restack/destroy/reuse and queued partial damage.
This is not actual VIC/painter or cc65 execution qualification. Compiler budget
make repaint-policy:CODE4643, ownBSS/DATA/ZP0; target sizeofjob22,ticket9,work15,
windowview9. Runtime closure/backend/scene temporaries are not yet charged.
Evidence2026-09-29-repaint-policy binds source/object/assembly/dumps/toolchain.
Scoped suite847 tests. Normal OS/app code and default disks unchanged.
Next: compact service adapter replacing existing composition, not adding this
4.6KiB generic draft to the 20-byte reserve. Prove state placement and equivalence
before resident linking; never borrow guard/stack/shadow bytes silently. Real
clip/workspace resets, paint/completion interlocks and cache/busy cancellation
remain adapter work. Optional bounded painter contract is still a separate gate.

2026-09-29 compact adapter preparation: tools/window_repaint_compact.py derives
a PRIVATE candidate from the selected manager, eliminating active (rank-zero
is free), redundant bitmap surface and the currently unread owner field. Public
signature/surface validation preserved; no new ownership guarantee. Guard future
owner/surface readers. Keep top_window's live test when active_count=0; destroy
saves old_z before retiring rank and calls close after retirement.
Six host tests cover library parsing and complete occlusion/partial-paste canvases and sparse
slots, all256 owner bytes, move/resize/close-during-drag, reuse/reset/callback and
diagnostic traces. Both whole links measure CODE7762->7645 (117), managerHIGHBSS
88->76 (12); linked helper modules unchanged. Potential HIGHBSS$E2D6-$E2E1
and CODE117+existing20=137. Full genericjob22 still ten larger than new state
before specialization/reuse; NO overlay assumed safe. Existing glyph/title/
chrome1315 and paint/compose697 are replacement code, not automatically free.
make repaint-compact runs in referencecontainer; every split output isolated.
Evidence2026-09-29-repaint-compact has objects/listings/normal+panic maps/providers
and hashes. Experimental images UNBOOTABLE (shadow$A16B, bridges not regenerated).
Production manager/disks remain unchanged. Next actual adapter step: compact
state layout plus bounded manager-owned stages checked against reference; prove
clip/paint/cache/busy/drag lifetimes before normal linkage. No new HW test yet.
Scoped make check855 tests pass, including eight new tests and all evidence
hashes/pycompile. Normal boot/all/panic/placement checks pass; D64c00d8936...,
D7100ab0c99..., kerneldfef7e6d..., module758965e4... still accepted hashes.
No VICE session was launched; the original main/xwave prototype is untouched.

2026-09-29 next prototype: repaint_lane.h/C owns an explicit18-byte HIGHBSS job
(current6,pending6,epoch2,cursor2,packedphase/selector2). One epoch replaces the
separate revision; ALL validated manager scene/content/cache mutations must
fence via changed BEFORE editing. This is not a public parser/UAPP ABI. No
pointers/drag/guard/cache scratch reused. State plan76compact-oldDamage6+18=88;
old damage globals still present in compile-only sizing source, not integrated.
Target ticket6/work12/view9; views/backend continuation/software-stack costs
additional. Fresh init only when quiesced; epoch/cursor exhaustion fails closed.
7 differential host tests match generic reference status/rects/receipts/cursors
and final canvases including40seeded changes and cancellation/reuse in all phases.
chrome.inc renders one opaque row with <=3spans and250directpixel calls, exact
original borders/font/buttons/strokes under many sizes/flags/titles/clips. C
raster.inc validates BEFOREpixels, clears<=4rows or renders1chromeRow or commits
<=1dirty256bytepage; successful steps resetclip thenack. Error/stale atomic
rejection leaves caller workspace untouched; poll-driver cleanup remains.
CLIENT/RESTORE return BACKEND_REQUIRED without callbacks/lease/ack; real providers
and busy/app-paint interlocks are NOT implemented. Backend test uses mock row
client and modeled pages, not real app/VIC/IRQ/NMI execution or timing.
make repaint-lane measures laneCODE2641/HIGHBSS18, chromeRow1468, raster1175.
Compiler omitted uncalled static backend initially; now private exported bench
entry with object-presence guard, NO UAPP entry. Synccompatloop70 remains in
sizing translation unit, not real polling. Optimistic code shortfall3171 even
granting all five old chrome/paint/compose bodies and137reserve; helper closure,
new call sites/adapters/cleanup costs additional. Evidence2026-09-29-repaint-lane.
Next: modular window-service code placement/transport or measured replacement
proof with byte-accurate lifetimes/restoration, then bounded client/cache provider
and real poll/cancellation interlocks. Normal disks remain accepted/unchanged;
no new manual test or application-specific/xwave optimization in this work.
Scoped make check868 tests/manifest/pycompile pass; 13 new tests. Normal parallel
boot/all/panic/placement checks pass; accepted D64c00d8936..., D7100ab0c99...,
kerneldfef7e6d..., module758965e4... hashes unchanged. Strong stale test reaches
a glyph row before replacing title with an invalid pointer; no dereference or
pixel/dirty/clip/progress mutation occurs. No emulator sessions launched.

2026-09-29 banked placement/transport checkpoint: make repaint-bank and
tools/window_repaint_bank.py build a standalone module, NEVER an OS disk.
Pure-C lane2641 + dispatcher160 + fixedentry3 + all linked helpers482 =3286
at bank1$D100-$DDD5. Proposed state$DFE0-$DFF1=18; upperguard14; codeSpare522.
Exact none.lib/map/objects/generatedcallerAssembly/programs and all inputs are
preserved in bench/{artifacts,results}/2026-09-29-repaint-bank with SHA manifests.
Binding84 including copiedgateway59 atcommon$F68A; packet82 at$F780-$F7D1,
diagnosticreturnedSP2 at$F7D2. Bank-owned lane is authority; packet snapshot is
debug-only. No pointers crossbank. Packet/gateway are transient serialized leases,
NOT persistent scratch; copy receipts/work out before VIC/cache overwrites them.
Reuse existingprivateCstack$5250-$533F ONLY with cache idle; do not annex its
22/16byteguards, image$5350-$5BFF, cacheState26, bootfs$A000-$D0FF, shellStack,
task slots/backup, sprites, workerCode, transientStackGuard or frozen shadow.
Binding holdsIRQmask from publication through kernel map/runtime restoration.
Real cc65 module runs workerFLAT$7F underI/O; restores26ZPbytes, hardwareSP,
softwareSP and callerI/D before returningkernelIO. No callbacks/polls/Z80 inside.
1986 andVICE both pass1415commands, explicitsemantics and hostpackedstream
checksum$CF65 (noncryptographic, not soleequivalenceproof). IRQ28486/28592;
lowestobservedchangedprivateStackOffset211 ($5323), notworstcasestackbound;
lowest64bytes unchanged. Both detectexactnegativecontrols: shiftedZPrestore,
CLIinsideworkerlease, andsoftwareStackHigh$53->$EF. No normaldecoderfalsepass.
Guardscan coverscacheState/allstackguards/cacheimage plus80screenbytes/boundary
bootfspage/workerShellStack. Scan reusesdiagnosticIRQbytes AFTER stoppingIRQ;
unsignedcopy for>127bytes andrelativebranchescorrecttwoharnessbugs. cc65caller
successcheck restructuredtoavoidfalsebooleq afterCMP5; generatedassemblysaved.
Sevenhosttests plus3evidence/decoder tests; scoped make check878 passes.
Normal parallelboot/all/panic/placementpasses; acceptedD64c00d8936/D7100ab0c99/
kerneldfef7e6d hashes unchanged. No x128 processes remain; rootxwaveworkuntouched.
NOT qualified: productiondelivery/admission, NMI/RESTORE, liveapps/taskpaging,
Z80cooperation, realpixels/inputlatency orphysicalhardware. CandidateunderIO
regionneedsexplicitproductionreservation; standaloneuploaderisnotfreeinstaller.
Codebudgetstillshort: row1468+backend1175+binding84=2727 vsoptimistic2113,
atleast614 BEFORE additionalhelpers/callers/painter/cache/busy/teardowncosts.
Next: measuredcompactresidentraster/sharedprimitives (or explicitbankedpart),
then delivery/admission/serialization/NMI andboundedproviders/poll gates.
No visiblecandidateyet, so no newmanualtest. See docs/WINDOW-REPAINT-BANK.md.

2026-09-29 compact resident raster checkpoint (issue14): make repaint-raster
and tools/window_repaint_raster.py build isolated normal/panic closure links and
a standalone native program. Normal production source/link/disks unchanged.
bench/window-repaint-raster/chrome.inc shares twelve explicitly allocated scalar
HIGHBSS bytes, NOT drag/cache/guard scratch; compact manager76+12=original88.
Title pointers automatic, never retained between row steps. Serialize drawing;
no poll/callback/IRQ renderer inside it. One-row chrome/helpers975 vs old1468;
backend755 vs old1175 =913 saved. Backend validates banked receipt BEFOREpixels,
rejects forged geometry/page/row cursors, resetsclip beforeack; CLIENT/RESTORE
still delegated. Real C receipt wrappers127 + privatebinding84 + NEW linked
helpers72 (memcpy60/return0 4/ult8) yield componentCODE2013. Oldbodies1976+reserve137
give100 PROVISIONAL headroom, NOT fullfit: actualpoll/view/admission/provider/
busy/teardown uncharged. Both complete normal/panic links growCODE654 while
legacypaint/compose/syncwrapper remain; all fixed segments/HIGHBSS298 unchanged,
RODATA/DATA/BSS/shadow sizes unchanged. Sizing images UNBOOTABLE/stalebridges,
never package. Exact none.lib, objects/listings/generatedsources/splitoutputs/
providerobjects/maps/inputs archived with SHA manifests under
bench/{artifacts,results}/2026-09-29-repaint-raster.
Native program links real C/ASM pixel/span raster, real receipt wrappers and
EXACT prior qualified bankedpolicy. LOCAL work copy protects from reused common
RPC/gateway scratch; caller serialized kernelIO required. RPCscratch can change
on rejection, pixels/dirty/clip/progress cannot. CLIENT mockrow, COMMIT bank0
memorymodel, not liveapp/VICgateway. Eight edge/fullscreen/flag/title scenes pass
both engines; independent Pythonoracle additionally matches OLD fullwindow C
with yellowclient pixels clearing resizegrip. Exact final8000bytes match:
8efa40f4c55d395b9681363a2d872a625ea5a36532cad5a38b6d3ecc266423c7.
Scenechecksums49629/45346/1790/64949/64211/8171/57/57329 supplementfullcanvasproof,
not sole equivalence. Staletitlepointer1 rejected on glyphrow without mutations.
IRQ1986 427181/VICE425942; observedprivateStackOffset211, not worstcasebound.
Heavyfullimage/guardscans and16000frame terminationbudget NOT latency acceptance
or realrenderer speed. Runtimechecks preserve MMU/ZP/hwSP/swSP/I-D/guards/cache/
bootfsboundary/USH; stopIRQ before retiring diagnosticIRQbytes forguardscan.
No liveapps/taskpaging/Z80/NMI/RESTORE/productiondelivery/physicalHW qualification.
Runs verifyinput/outputhashes before/after and bindraw/programpair tobuildreport.
Scoped make check887 tests/manifest/pycompile pass; normalparallelboot/all/panic/
placementpasses. AcceptedD64c00d8936/D7100ab0c99/kerneldfef7e6d hashes unchanged.
Own VICE sessions closed, no x128 processes remain; rootxwavework untouched.
Next: measureactualdelivery/admission/poll/provideradapter and furthercode
recovery if100bytes insufficient; qualifygraphics/private-stack serialization
andNMI/cancellation cleanup BEFORE real linking. Then visiblelatency/manualtest.
No new testdisk yet. See docs/WINDOW-REPAINT-RASTER.md.

2026-09-29 private frontend checkpoint (issue14):
bench/window-repaint-frontend/frontend.inc is NOT wired to actual manager
poll/lifecycle. It packs current visible manager views (sparse handles/ranks,
wrap-safe geometry), sends private INIT/REQUEST/CHANGED/ABORT and runs at most
one manager raster step. Copy packet.work into caller LOCAL storage BEFORE
raster/receipts can reuse common scratch. CLIENT remains BACKEND_REQUIRED with
receipt unacknowledged; no legacy callback, job-draining loop, cache provider or
retained flag slipped into the budget. INIT requires fresh/quiesced lifetime;
REQUEST preserves current work, CHANGED must succeed BEFORE any scene edit,
ABORT only for whole-surface retirement. Deferral does NOT authorize an edit.
Caller lease value1 is a trusted assertion, NOT implemented lock/admission.
Reject other lease values, graphics inactive, cache admission !=$80 and phases
other than EMPTY/READY (including frontend-busy$82/unknown). Poll defers while
dragging; control can fence/cancel. Deferral leaves packet/lane/output/clip/pixels
untouched. Invalid table geometry may edit view-packing scratch, but never calls
policy or changes lane/output/clip/pixels. Production admission/paint-lease flags,
callers, NMI drain and teardown interlocks still absent/unqualified.
Sequential register-local view packing avoids mulax9 helper. Gate48 + control98
+ poll440 =586 added CODE. Manager object8719/HIGHBSS88; no frontend globals or
extra BSS/DATA/ZP. Both full normal/panic links grow CODE1240 while legacy paths
remain, same newhelperclosure72 (memcpy60/return0 4/ult8), no removed helpers.
All frozen segments/HIGHBSS298 and RODATA/DATA/BSS/shadow sizes unchanged.
COMPONENT lowerbound2599 vs retired-body/reserve2113 => at least486 SHORT;
call-site/admission/delivery/NMI/busy/teardown/providers additional. Prior100-byte
headroom was drawing-only, NOT fullfit. Possible extra retirements: damage_set87,
damage_add163, intersection316, cache_paint_image156 =722. NOT counted as free:
real drag/cache/callback users still need replacement, with measured new costs.
tools/window_repaint_frontend.py / make repaint-frontend replay isolated links;
UNBOOTABLE moved-shadow/stalebridges, never disk package. Exact sources/providers/
library/generatedC-ASM/objects/splitoutputs/maps archived under
bench/{artifacts,results}/2026-09-29-repaint-frontend with complete SHA manifests,
including nested manifests. Compiler versions measured directly. Earlier
unpublished pre-version-measurement evidence kept recoverably in
build/window-repaint-frontend-{artifacts,results}-preversion, not committed.
Four new host tests use real table/dispatcher/lane/receipt/backend with modeled
rowclient/pagecopy: complete overlapping old-reference canvases, sparse rank
order/highX/hidden4slot views, <=4rowclear/1chromerow/1pagecommit, repeated delegated
receipts, packetclobber-after-local-copy, pending requests, poisoned title/slot
fences, geometrywrap, exhaustion/abort and all cache/lease/graphics/drag conflicts.
Two budget negative/source tests +3evidence tests. No new native/emulator/liveapp/
paging/Z80/NMI/physicalHW/inputlatency qualification claimed. Existing native
raster evidence retains ONLY its previous scope; no VICE sessions launched.
Next: real damage/clip/cache call-site replacement, prove actual helper retirement
and complete fit, then checksummed delivery/admission, serialized private-stack/
gateway ownership and NMI drain in restored kernel map. SEI is not NMI proof.
Only after real poll/providers/placement/interlocks pass, produce visible disk.
Scoped make check896 tests/manifest/pycompile pass; normalparallelboot/all/panic/
placement pass; D64c00d8936/D7100ab0c99/kerneldfef7e6d accepted hashes unchanged.
Root main/xwave work untouched. See docs/WINDOW-REPAINT-FRONTEND.md.

2026-09-29 private scene-prefix checkpoint (issue #14):

The four potential legacy helper retirements still have real drag, overlap,
cache and callback users. None of their 722 bytes is reclaimed. Instead,
bench/window-repaint-scenes/poll.inc copies exactly eight value bytes per slot,
never titles or callbacks. Banked C validates geometry/format and derives
sparse handles/current views. Private packet 0.2 uses marker $84 plus four zero
reserved bytes, retaining its 82-byte size and receipt/work offsets. Old/new
PEEK reject one another. Compiler-emitted 13-byte target layout sidecars and
intentional prefix/packet shift controls gate the copy. Host tests explicitly
model packed 16-bit fields; native host pointer layout is not target-wire proof.

Poll 212 versus 440 saves 228 resident bytes; gate/control remain 48/98.
Manager CODE 8491, HIGHBSS 88; no new persistent state. Complete normal/panic
CODE growth 1012, new resident helper closure 72. Fixed segments/HIGHBSS 298 and
RODATA/DATA/BSS/shadow sizes unchanged. Component 2371 versus 2113 is still at
least 258 SHORT, excluding callers, admission/delivery, NMI, providers and
busy/teardown. Sizing links are UNBOOTABLE (moved shadow/stale bridges), never
package them. Legacy helper bodies remain unchanged.

Bank entry 3 + lane 2641 + dispatcher 564 + all helpers 512 = 3720 bytes at
$D100-$DF87, 88 code bytes spare. State $DFE0-$DFF1, 14-byte guard and existing
26-byte saved/restored runtime ZP set unchanged. Four local nine-byte views
charge 36 bytes to the existing 240-byte private C stack, no retained views or
new BSS/RODATA. Observed lowest changed stack offset 169 versus previous 211;
not a worst-case bound. No callbacks/polls/Z80 within the bank lease.

Actual new poll/decoder plus real C/ASM raster pass both 1986/VICE: eight
old-reference scenes and four malformed protocol cases, rejecting without
lane/pixel/clip changes. Exact final 8000-byte SHA-256:
8efa40f4c55d395b9681363a2d872a625ea5a36532cad5a38b6d3ecc266423c7.
IRQ counts 440821/439734; runtime/guards survive. The 12767 PAL diagnostic frames
include heavy full-image/guard scans, NOT latency or speed qualification.
Native client/page-copy/graphics/cache admission remain models; lease value 1
is not an implemented lock. CLIENT stays delegated/unacknowledged. No retained
flag, legacy whole painter, live apps, task paging, Z80, NMI/RESTORE, production
delivery or physical-HW claim. Earlier transport faults were NOT re-run.

Exact inputs/providers/libraries/objects/maps/layout controls/PRG/raw records
and emulator provenance: bench/{artifacts,results}/2026-09-29-repaint-scenes.
Runs bind program/report/raw hashes, check drift before/after, and refuse to
overwrite evidence. make repaint-scenes builds the isolated proof; tool run
engines 1986/vice, then preserve. make check passes 905 tests; normal parallel
boot/all/panic/placement pass. Accepted D64 c00d8936, D71 00ab0c99 and kernel
dfef7e6d hashes unchanged. Own VICE sessions closed, root main/xwave work
untouched. No new manual disk. See docs/WINDOW-REPAINT-SCENES.md.

NEXT: recover remaining resident code and measure real call-site/provider costs.
Retire legacy helpers only with their users; do not annex guards, common app
stack overlap or bootfs to invent fit. Then qualify checksummed delivery,
admission, paint leases and NMI drain in the restored kernel map, followed by
live poll/providers/interlocks and finally a visible disk/latency gate.
Keep xwave-specific work separate.

2026-09-29 private geometry checkpoint (issue #14):

The C-only title-row specialization saved only 17 bytes and was discarded.
The retained candidate replaces the still-used `damage_set`/`damage_add` C
bodies (250 CODE bytes) with 169 bytes of private 8502 assembly. Both isolated
normal/panic whole links recover 81 CODE bytes and retain unchanged fixed
ranges, HIGHBSS, RODATA/DATA/BSS/shadow sizes and 72-byte new helper closure.
Their CODE growth falls from 1012 to 931. No legacy helper is retired or
persistent state allocated. Against the current 2371-byte component, the
measured extra 81 bytes reduce the optimistic deficit from 258 to **177**;
real callers, providers, admission, delivery, NMI and teardown remain uncharged.
The sizing links are UNBOOTABLE and not packaged.

The standalone PRG runs real ASM and independent C arithmetic over 100
rectangle pairs, including edge/wrap values. Both 1986 and VICE pass. VICE
caught a missing diagnostic BSS clear; the corrected startup now initializes
BSS on both emulators. Record decoder rejects malformed completion/failure/
case-count bytes. This is not a live manager, mouse, NMI, hardware or latency
gate. Exact sources, all split links, toolchain and hash-bound raw results are
preserved under bench/{artifacts,results}/2026-09-29-repaint-geometry; see
docs/WINDOW-REPAINT-GEOMETRY.md. Root xwave work remains untouched.

NEXT: measure further *real* caller/provider costs and recover the remaining
resident deficit; do not grant unretired helper bodies or reserved stack/guard
bytes as free. Qualify delivery/admission and NMI-safe serialized ownership in
the restored kernel before producing a live manual-test disk.

2026-09-29 real caller/provider audit (issue #14):

The selected manager has ten synchronous `compose_damage` calls, seven
`damage_set`, two `damage_add`, two cache-paint routes and two direct
`window->paint(handle)` calls. Public painter callbacks return `void`, and
there is no bounded progress cursor or explicit deferred/retry window status.
The full xwave callback loops over its plotted prefix despite its separate
four-vertex foreground poll. Create/destroy/drag/repaint currently rely on
synchronous repaint/callback ordering. Source-locked audit/tests now fail if
those representative call counts or ordering seams change unreviewed.

First shared damage-box-to-lane marshaller compiles to 78 CODE bytes and no
state/data. Complete isolated normal/panic links add exactly 78 with no new
helpers or fixed-range changes. Optimistic shortfall returns from 177 to
**255 bytes BEFORE any actual caller**, provider, admission, delivery, NMI or
teardown. It does not fence any mutation or own a lease. Source/build/library/
link hashes preserved under bench/{artifacts,results}/2026-09-29-repaint-callers;
see docs/WINDOW-REPAINT-CALLERS.md. Production images unchanged; isolated
links UNBOOTABLE. No fresh emulator/manual gate for this uninstalled adapter.

NEXT: define and host-test a private bounded client-step provider and explicit
pre-edit/deferred scene-change semantics. A generic INVALID return on busy
destroy risks lost cleanup; merely moving an old `void` painter to another
poll does not bound it. Only then measure real call sites/provider/admission,
and qualify NMI-safe ownership, delivery and an eventual visible disk.

2026-09-29 private client-step contract (issue #14 continuation):

`bench/window-repaint-provider/provider.{h,c}` and
`tests/test_repaint_provider.py` prove a one-row CLIENT step with ticket
validation, selected handle/rank/visibility and clip/cursor checks, pure
preflight deferral, clip reset before acknowledgement, and `MORE`/`DONE`
progress. The host harness completes 83 rows and rejects stale/malformed
records without pixels, clip or lane mutation. This is deliberately private
and compile-only: existing `void` xclock/xwave painters are unchanged and no
UDEX app bridge or NMI-safe lease is established. A generic callback-table
version cost 1,396 cc65 CODE bytes; the fixed dispatcher still costs 1,124
CODE bytes with no state at `-Oirs`, so it is not resident-placement viable
given the pre-existing >=255-byte shortfall. See
docs/WINDOW-REPAINT-CALLERS.md. Next: pre-edit/deferred semantics plus a
substantially smaller provider/banked placement proof; do not ship a test disk
until full normal/panic links, ownership and NMI gates pass.

2026-09-29 pre-edit/deferred scene-fence prototype (issue #14):

`bench/window-repaint-edit/fence.{h,c}` and `tests/test_repaint_edit.py` prove
the old/new damage union, no lane or scene mutation on unavailable admission,
old-ticket withdrawal before a drag geometry edit, create/destroy ordering,
and fail-closed exhaustion using the real private lane. cc65 `-Oirs` emits
495 CODE bytes, zero owned state; not a full-link fit. The public window API
has no retry result and cannot silently map contention to INVALID or NONE;
actual callers and application cleanup remain unchanged. The `available`
boolean is only a test stand-in, not a lease/NMI solution. See
docs/WINDOW-REPAINT-EDIT.md for the caller migration table and remaining gates.
No new test disk or hardware prompt yet. Next is an explicit retry/admission
protocol plus smaller placement candidates, followed by normal/panic links.

2026-09-29 synchronous admission spike (issue #14):

`bench/window-repaint-admission/{admission,transaction}.{h,c}` (transaction
only has `.c`) models a dedicated 1-byte FREE/EDIT/RASTER/CLIENT/CACHE owner.
Nested acquisition defers; wrong release fails unchanged; edit begin retains
ownership across the actual caller mutation and failed begin releases it.
Host tests use the real lane and source-lock the installed NMI stub to its
record-only five instructions. cc65 `-Oirs`: admission 79 CODE + 1 HIGHBSS,
transaction 80 CODE. A separate trusted-bounds fence saves 495→298 CODE and
matches 1,800 valid-case reference runs, but **cannot yet be installed**:
the present create check uses `x + width > 320`, susceptible to 16-bit target
overflow. The existing ASM damage primitives plus 78-byte marshaller may be
a smaller alternative; no full link has measured either path. Existing app
begin/end paint spans worker work and is explicitly outside this synchronous
lease. Public retry/versioning, all real callers, cache/IRQ/NMI ownership,
provider bridge and resident placement remain gates. See
docs/WINDOW-REPAINT-ADMISSION.md. No new disk/manual test. Next: harden/audit
caller geometry and compare a no-second-union path in complete normal/panic
links before attempting live integration.

2026-09-29 create-bound hardening and no-second-union link gate (issue #14):

Both generic and cached manager variants now use subtraction-based create
bounds, rejecting target 16-bit wraparound. The two equivalent source
compactions recover the guard's bytes, preserving the frozen normal/panic
boot layouts; host regressions exercise both real create paths, including
right/bottom edges. The existing 1986 integration probe passes D71 and D64
with cached moves, pixel oracle, cancellation, console and graphics restart.
The host VICE Flatpak probe passes both formats with exact window pixels,
NMI handoff and graphics restart. A private admission transaction reuses the
existing ASM damage box and control marshaller. Its host test covers defer,
commit and release. Complete isolated normal/panic links add 130 CODE and one HIGHBSS
byte, but strict placement rejects that byte at `$E2E2` (selected-task cc65
context). The measurement-only config intentionally trespasses there and is
UNBOOTABLE. Optimistic resident shortfall is now 385 bytes before actual
callers/provider/delivery. See docs/WINDOW-REPAINT-ADMISSION.md and
tools/window_repaint_admission_link.py. Do not produce a live candidate from
that sizing image. Next: recover legitimate state placement or redesign
admission, then solve the remaining CODE budget and public retry semantics.

2026-09-29 private bank-0 admission placement follow-up (issue #14):

`REPAINT_ADMISSION_BANK0_BSS` relocates only the owner byte out of full
HIGHBSS. Reproducible complete isolated normal/panic **strict** links now
pass with +130 CODE, +1 ordinary BSS, unchanged HIGHBSS/fixed segments and
an 8,000-byte VIC shadow shifted by one byte to `$A654`. The original
HIGHBSS variant still fails at reserved `$E2E2`. A source-locked test checks
the existing binding's IRQ-masked banked call and record-only NMI stub; this
does not prove all re-entry paths. The owner is only accessible in bank 0,
so try/release and caller mutation must remain synchronous under that map;
no banked policy, worker or callback may inspect it. This resolves the single
byte's placement, NOT the >=385-byte optimistic CODE shortfall, public retry
contract, provider bridge, actual callers or delivery. Both sizing links are
still UNBOOTABLE; no manual disk yet. Next: measured CODE recovery and
verified caller/entry ownership before any production integration.

2026-09-29 clipping micro-recovery gate (issue #14):

The still-used `set_damage_intersection` helper was tested for local C
compaction. Reusing width/height as endpoint temporaries and registering
left/top saves exactly 23 CODE bytes in complete isolated normal/panic links,
with unchanged state/helpers/fixed segments; a 4,096-case host oracle passes.
This only reduces the optimistic admission-era shortfall from 385 to 362
bytes, before actual callers/providers/delivery. Do not install this tiny
rewrite into the frozen production manager. The helper's two legacy paint
uses and one cache-paint use identify the structural retirement seam: the
316-byte intersection and 156-byte cache-paint bodies are not yet reclaimable
while their callers remain. See docs/WINDOW-REPAINT-CODE-RECOVERY.md. Next:
implement and measure genuinely bounded client/cache replacement and public
deferred completion, then retire superseded users in a complete link. No new
bootable repaint candidate or manual test yet.
