# Generic disk-loaded graphical applications

Status: four-native-client cutover implemented, 2026-10-05; physical acceptance pending.
[Issue #35](https://github.com/salvogendut/UDEKS/issues/35).
Initial branch `graphics-generic-apps` merged as PR #36 (`c704250`).
The clock/wave follow-up is on `graphics-native-clients`, still under #35.
This is the next feature priority, before service extraction.
It replaces application-specific slot wiring, not the four-window capacity limit.

## Four-native-slot cutover — 2026-10-05

Implemented on `graphics-native-clients`: **all four shipped graphical apps are
ordinary relocatable disk programs**, with no app-name routing in ush, the
resident session, loader or running panel. `name &` picks the smallest FREE
compatible allocation; `name` owns the foreground and Ctrl+C closes only that
instance. `name -q` cooperatively stops the first matching live instance.
Repeated names are permitted. The retired named CONTROL app operations now
return ENOSYS; the old managed loader entry rejects flag-2 loads.

| Task | Bank-1 allocation | Image + BSS maximum | ZP / hardware-stack pages |
| --- | --- | ---: | --- |
| 3 | $2300–$34FF | 4,352 bytes | $D5 / $D6 |
| 4 | $3500–$3FFF | 2,560 bytes | $D7 / $D8 |
| 5 | $8000–$8FFF | 3,840 bytes | $D0 / $E2 |
| 6 | $C600–$CFFF | 2,304 bytes | $00 / $01 |

Admission order is 6, 4, 5, 3, based only on capacity. The complete file,
including relocation metadata, must fit the allocation. Its final page is
reserved after installation: 16-byte lower guard, **160-byte private C stack**,
16-byte upper guard and private exit trampoline. Image+BSS and graphics source
pointers may not enter that page. Stack depth is a real SDK limit, not hardware
protection. All four contexts use the accepted scheduler and frozen gates;
the MMU initializer preserves the 8502 port at $00/$01.

Removing the legacy callbacks frees the bank-1 foreground backup and old
external C stacks. Both graphical service modules are copied out of bank-1
$C600–$D0EF before *any* native client is admitted; their installed flag is
never reset. Only then may task 6 and task 5's zero page reuse that delivery
area. The temporary bootstrap context at $E2E2 has already been retired by
scheduler activation before task 5 uses its hardware-stack page. Bank-1
physical pages $00/$01 are otherwise unused after boot; foreground task 2
still starts at $0200 and uses its separate relocated CPU pages.

Retained images now share **2,304 bytes in bank 0 at $1300–$1BFF**, packed in
slot order. Replacement/close compacts the pool; malformed or over-capacity
updates leave all live images unchanged. PRESENT stays at most 384 bytes;
PATHS stays at most 1,280 bytes per image, but four maximum-sized path images
cannot coexist. Pool exhaustion returns ENOMEM. The normal four-app set fits.
The base graphics service occupies $0C00–$12FF; the existing 1,008-byte retired
VDC glyph-source overlay is unchanged. Console commands, recovery bootfs,
filesystem, cache, VIC bitmap and Z80 code retain distinct ownership.

Wave resize now waits for outline release and projects sixteen table-scaled
vertices per cooperative yield. The app caches all 525 heights and retains all 524 edges:
moves/raises replay service data; resize never resubmits the Z80 height job.
Dense geometry repaint is still synchronous, not a new pixel-blit guarantee.

VICE D64/1541, D71/1571 and D81/1581 pass the bundled four apps, calculator
arithmetic, drawing input, clock/time oracle, full wave path/sample oracle,
held-outline/no-duplicate resize, exact worker leases, console use, fifth-app
rejection, shutdown and reload. Four renamed copies of the same independently
built HELLO binary also run simultaneously, each with independent input,
guarded stacks and names; malformed loads preserve peers and freed slots
accept another name. These are injected VICE WM events; native mouse and
physical-C128 confirmation are separate gates. Unmodified 1986 revision
`81485cc7` also passes raw-IEC D64/1571 boot, actual keyboard/1351 drag and
resize, calculator/drawing input, held-outline/worker reuse, independent reload,
foreground Ctrl+C, canvas equality and all four private stack guards.
Physical-C128 confirmation remains due. Test the fresh
`build/boot/udeks.d64`, `.d71` or `.d81`; published `build/udeks.*` snapshots
remain unchanged. Reproduce with `make four-native-probe` after the container
build and `make graphical-example`.

Final qualification: 1,158 host tests pass, both actual-build placement gates
pass, and an isolated parallel build reproduces all three disks byte-for-byte.
Exact images/captures and reproduction notes are preserved in
[`bench/results/2026-10-05-four-native`](../bench/results/2026-10-05-four-native/README.md).
Next gate is physical-C128 acceptance, then review/merge #35; the next roadmap
feature is one disk-loaded non-kernel service, not another graphics optimization.

### Resize-latency follow-up — 2026-10-05

The user reported the new size appearing only after further clicks/repaints.
The extended probe reproduced a long delay **without any subsequent input**:
755 PAL frames with clock/wave, and 1,399 with all four apps. This was not a
lost focus event. The prior probe checked eventual geometry but did not measure
the delay, and resized before launching calculator/drawing.

The app now constructs exact integer scale tables once per size and projects
16 vertices per yield, instead of doing two multiply/divide calculations per
vertex and yielding every four. It still preserves all 524 edges, restarts on
a newer size, pauses during dragging and never re-runs the Z80 height job on
resize. No kernel, scheduler, graphics ABI or WM changes are involved.
Its image+BSS is 3,748 bytes, within the 3,840-byte slot-5 limit.

The same native-1351 workload takes **418 / 594 PAL frames** after release
(8.36 / 11.88 seconds versus 15.10 / 27.98). This is a latency reduction, **not
instant resizing**: synchronous retained-vector painting still dominates the
remaining delay and is separate future work. Both VICE and native 1986 tests
now resize with all four clients active and wait without further clicks. The
VICE test also compares the visible topmost wave pixels against the resized
mathematical grid, not just the retained request data. The 1986 test bounds
projection/publication delay and retains the input, guards and no-extra-worker
checks. Baseline evidence above is unchanged; follow-up evidence is in
`bench/{artifacts,results}/2026-10-05-wave-resize`.
Follow-up qualification: 1,162 host tests, both placement gates, VICE on all
three disk formats, and unmodified 1986 native input pass. During projection
the measured maximum input-poll gaps were 8/9 PAL frames; this does not bound
the separate synchronous painting phase. Fresh `build/boot/udeks.*` images
contain the change; published snapshots have not been replaced.

## Earlier checkpoints (historical layouts)

The dated sections below describe earlier builds, not current allocation ownership.

## User-visible target

Build a new C graphical application using a documented SDK, copy its executable
to the system disk as `NAME.BIN`, then run `name &` from ush. UDEKS selects a free
compatible allocation, tracks the instance, and retires its window/input/task
resources on close or exit. Adding a program must not require editing or
rebuilding the kernel, shell, running-app panel or a resident name table.

The same executable must work in different suitable slots; users and app authors
must not select a slot or link separately for a task number. A free slot smaller
than an application's image/BSS/stack requirements is not a usable allocation.
Full, malformed or incompatible loads must give a useful error without changing
live peers. This remains a trusted cooperative system, not hardware protection
against arbitrary machine code.

## Original coupling (being removed)

- `user/bin/ush.c` recognizes app names and translates them to numeric control
  IDs in `include/udeks/service_control.h`.
- The banked graphics service previously selected only `xcalc`/`xdraw` and
  the running panel had fixed labels. Those paths now use generic admission
  and per-instance names; the legacy named CONTROL adapters remain.
- `src/services/shell/shell.c` still has compatibility job bits and foreground
  controls. Unknown `name &` requests now take the automatic native loader.
- Calculator and drawing link at bank-1 `$2300` and `$3500`, respectively.
  Absolute code/data references cannot simply be copied to a different base.
- Clock and wave use legacy bank-0 callback modules, not the native task model.
  Four window descriptors therefore do not yet mean four interchangeable app slots.

The existing owner-checked UTRQ graphics interface, retained commands and private
task contexts are reusable. Allocation policy, loading, instance tracking and
presentation belong to service/user code; do not move app policy into the kernel.

## Relocation checkpoint (committed as `fbdc72d`)

UDEX 0.2 carries a bounded page-relocation table generated from real ld65 o65
records. The same compiled C file runs at bank-1 `$2300` and `$3500`, with
private state, initialized pointers, BSS and recursive software-stack frames
surviving yield/sleep. Both D64/1541 and D71/1571 VICE runs pass rejection,
concurrent execution, exit, reap and reload. Flat-link oracles independently
match both relocated images byte-for-byte. See the
[format and build instructions](../abi/executable.md#page-relocatable-native-images-02-development).

The proof image is 963 image + 7 BSS bytes; its file is 1,175 bytes including
header and 97 high-byte patches. The current loader must stage the whole file
inside the allocation, so relocation overhead also counts against capacity.
This is not yet a graphical SDK example or a generic shell command.

No resident-core or public syscall change was needed. Loader delivery uses
measured slack in two bank-1 service reservations:

| Region | Linked bytes | Reservation |
|---|---:|---|
| Existing loader | 1,787 | `$D900-$DFFF` (1,792) |
| Relocation validator/patcher | 366 | `$1880-$19FF` (384) |
| Extracted access helpers | 106 | `$1F00-$1FFF` (256) |

Storage is now bounded below `$1880` (1,650 bytes, 14 spare); lookup below
`$1F00` (1,169 bytes, 111 spare). Link/build and actual-map gates enforce these
bounds. CPU zero pages/stacks at `$D100-$D8FF`, common gates, both app
allocations and the Z80 remain untouched. The four existing apps pass the
VICE D64 and native keyboard/mouse 1986 regression (existing fixed-address
apps, not a second emulator's relocation proof). An isolated parallel build reproduces both normal disks,
the new executable and all changed service outputs byte-for-byte.

Exact images, captures and reproduction notes:
`bench/{artifacts,results}/2026-10-04-relocatable-apps`. Existing historical
evidence and published `build/udeks.*` snapshots are unchanged.

## Current checkpoint: ordinary unknown-name background launch

`name &` now resolves the disk executable, chooses a FREE fitting task 3/4
allocation, activates it and publishes a service-owned instance name. The
panel reads those names (nine display characters); close/EXIT frees the owner
and another executable can reuse it. No new kernel, shell or panel app ID is
needed. Duplicate instances are allowed; window/task identity controls events
and retirement. Old `xcalc -q`/`xdraw -q` requests reject unrelated occupants.

The independent 597-byte `HELLO.BIN` sample is installed as both HELLO and
SECOND without rebuilding the OS. [Build/install/test guide](GRAPHICAL-APPS-SDK.md).
Both VICE disk formats pass normal shell launch, independent state/clicks,
drag/close/reuse, malformed and oversized image rejection, unchanged live
peers, console use and desktop shutdown. The existing four-app VICE D64 and
unmodified 1986 native-input regressions also pass; the latter is not a second
emulator qualification of the new example. Exact candidate/evidence:
`bench/{artifacts,results}/2026-10-04-generic-launch`.

Current measured bytes: loader 1,791/1,792; access 236/256; relocation 366/384;
graphics module 1,525/1,536; helper 216/224; high module three spare bytes;
resident BSS ends `$9AFE` (one spare byte). No runtime stack, guard, CPU page
or app allocation moved. Serialized root-service scratch is static to avoid
extra persistent cc65 frames. The new metadata belongs to the graphics service.

At that checkpoint foreground remained pending. The follow-up below implements
bare generic launch/Ctrl+C. **Next:** instance/name-based control and native-client
migration, then explicit clock/wave compatibility. Generic `-q`, native arguments
and all-four-slot interchangeability remain incomplete. Plan the next service
placement before adding resident code.

## Implementation sequence

### Clock/wave migration follow-up (2026-10-04)

The user explicitly asks to remove the two legacy application slots. This is
a native-task and service-boundary migration, **not xwave algorithm tuning**.
Preserve the four-window baseline until its replacement passes; merely putting
clock and wave in today's two generic allocations would reduce concurrency.

1. **Independent clock candidate.** Build `user/bin/xclock_native.c` separately
   as `NCLOCK.BIN`. Use ordinary UDEX 0.2 admission, private C runtime/data,
   common read-only TIME snapshot, retained graphics and cooperative events.
   Qualify the identical file in both allocations, concurrent instances,
   `date` changes, dragging, foreground Ctrl+C, reload and coexistence with
   the existing legacy apps. The first candidate uses the existing fixed-size
   graphics API; it is not yet the replacement for the resizable `xclock`.
2. **Close the public-service gaps.** Add owner-checked resize/geometry events
   and choose a bounded generic retained-image representation for wave. The
   current 48-command buffer cannot represent the existing 524 wireframe edges;
   do not hide a wave-specific renderer in the window manager or drop edges to
   claim migration. Expose a bounded worker request through the task boundary
   instead of calling bank-0 UAPP/Z80 functions from a native task. Preserve
   height reuse on moves and the established dual-engine computation.
   **Resize portion implemented:** UTRQ 0.10 acknowledges last-rendered
   dimensions and reports current geometry without consuming pending clicks.
   The independent clock scales in both native slots; VICE all three formats
   and 1986 D64/D81 native input pass. No sizing policy or algorithm lives in
   the window manager. **Worker portion implemented:** UTRQ 0.11 exposes
   bounded NOP/sample/surface requests without UAPP calls or a desktop. Two
   independently relocated console tasks copy results privately and coexist
   with clock/wave. **Retained portion implemented:** UTRQ 0.12 packed polylines
   hold all 524 wave edges in 1,128 bytes. The independent native wave samples
   the Z80 once per load, reprojects cached heights on resize, and reuses the
   service-owned paths on moves/raises. See the checkpoint below.
3. **Measure and realize four compatible native allocations.** Account for
   code/BSS, relocations, private CPU pages/stacks, retained images, storage,
   Z80 and console execution together. Reclaim legacy callback/backup resources
   only once their users have migrated. Normal/panic map gates and negative
   overlap checks must precede switching the disk defaults. Today's slots are
   not magically four slots, and a binary need not fit the smallest allocation.
4. **Cut over and remove compatibility wiring.** Migrate clock/wave and the
   calculator/drawing adapters to the generic path; update `ush`, control,
   panel and packaging without app-specific routing. Replace shipped images
   only after four-app launch, resize, drag, stop, slot reuse, console and
   worker-isolation tests pass on VICE/1986, followed by a physical-C128 test
   candidate. Keep historical evidence immutable.

The native clock and its drawing model belong entirely to disk-program code.
`make native-clock` does not link the kernel or change boot media. The first
gate and its resize extension pass: both native slots on VICE D64/D71/D81 and
unmodified 1986 D64/D81 native keyboard/1351 input. The
[SDK test recipe](GRAPHICAL-APPS-SDK.md#native-clock-migration-candidate)
keeps NCLOCK separate from the production apps until full native migration.

### Retained paths and native-wave checkpoint (2026-10-04)

Resize follow-up: outline geometry no longer generates RESIZED events while
the handle is held. NWAVE projects four vertices per cooperative YIELD and
publishes only after rechecking the final size. A later resize restarts that
private projection; partial streams never reach the service. The D64 VICE
probe holds the outline, checks that no submission occurs, then requires
exactly one submission on release. The complete grid/worker/clock/cleanup
regression passes, as do 1,149 host tests and both placement gates. Evidence
for this working checkpoint is in `build/native-clients/resize-release-vice-d64`.
Dense retained rasterization on release is still synchronous; this does not
claim a general renderer latency fix.

`make native-wave` builds NWAVE.BIN without relinking the OS: 2,221 file bytes,
1,741 image bytes and 1,681 BSS bytes. It fits the larger native allocation;
it does not fit the smaller one. The generic loader makes that decision; there
is no wave name/slot rule. Launch wave first, then NCLOCK in the smaller slot.
The unchanged 21×25 sinc sample field and all 524 wireframe edges are preserved.
The worker is called once per row, with a cooperative sleep between rows.
Resizes reuse the private 525 samples; moves/stacking do not rebuild app data
or submit Z80 work. Generic retained geometry still needs rasterization when
the compositor repaints; this is not the postponed wave optimization project.

Placement is a **lifetime overlay**, not new RAM or reduced app capacity:

- Boot assets are fixed at bank-0 `$96A8-$9AFF`. The 16-byte header and 88-byte
  tile maps remain live. Only the 1,008 custom-glyph bytes at `$96B8-$9AA7`
  retire after successful upload into VDC RAM.
- On the first native launch, the graphics service copies its base image from
  bank-1 `$C600-$CBFF` to bank-0 `$0C00-$11FF`, then its 1,008-byte extension
  from bank-1 `$CC00-$CFEF` over the retired glyph source. Both copies precede
  publication/admission. The pending filename survives the transfer scratch.
- The extension has separate emitted PATHSTATE (60 bytes) and GRAPHICSPATHS
  (938 bytes) segments. cc65 static locals must not share a segment with their
  executable entry labels. Combined use is 998/1,008 bytes.
- Those bank-1 delivery bytes then become two 1,280-byte retained images at
  `$C600-$CAFF` and `$CB00-$CFFF`. Installation is never replayed after close
  or desktop shutdown. Console reentry bypasses retired glyphs once installed.
- Filesystem policy ends at `$C50C` and is bounded below `$C600`. No app
  allocation, stack, CPU page or common gate moved. Resident BSS ends `$9693`
  (20 bytes before assets); the base graphics image uses 1,535/1,536 bytes.

Actual-map gates enforce both lifetimes, normal/panic equality, glyph-only
bounds and exact secondary delivery. Host tests cover malformed-stream atomicity
and every edge against an independent projection. VICE D64/1541 and D81/1581
cover real drawing, grow/shrink/regrow, worker lease counts, font/metadata
preservation, the stepped console guard, console commands, four-app compatibility
and cleanup/reload. VICE D71 runs the complete two-clock regression. A fresh
parallel build reproduces all disks/modules/apps. Evidence:
`bench/{artifacts,results}/2026-10-04-native-wave`.
No new physical-C128 or 1986 qualification is claimed for this checkpoint.
Four interchangeable native slots and default clock/wave replacement remain next.

### Original generic-loading sequence

1. **Prove slot-independent execution.** Define a bounded versioned executable
   and SDK contract with a measured placement plan. Evaluate relocation or
   equivalent address-independent loading using real cc65 C code, not only an
   assembly stub. Relocate code, initialized pointers, entry and BSS references;
   leave hardware/common-ABI addresses untouched. Reject malformed metadata and
   overflow before publishing ownership. Keep existing UDEX compatibility
   explicit; do not silently reinterpret its fixed load address.
2. **Generic launch and instance lifecycle.** Resolve the executable from `/bin`,
   select a fitting FREE allocation from runtime descriptors, then validate,
   load, initialize and publish the task/window owner. Keep per-instance name,
   task and foreground/background state. Replace native app-name switches and
   fixed panel labels with those descriptors. Preserve console commands, `&`,
   close, targeted Ctrl+C, graceful exit, cleanup and slot reuse. Decide whether
   any temporary launcher command is needed without mistaking it for the final
   ordinary `name &` interface.
3. **SDK, migration and end-to-end acceptance.** Supply an independently built
   sample app unknown to the OS and migrate calculator/drawing to the generic
   path. Define and carry out the clock/wave compatibility or migration needed
   for all four advertised slots; two generic slots plus two named legacy apps
   is an intermediate milestone, not completion. Keep xwave algorithm/performance
   work separate. Update packaging to accept extra `.BIN` files without adding
   per-app kernel or disk-builder branches.

Each increment should deliver a meaningful runnable capability, with a map gate
before placement changes. The merged baseline has only 45 bytes of resident
headroom, 16 bytes in the high module, 53 in the shell, and no space in the
`$D900-$DFFF` loader. Remeasure before implementation. Replacing old dispatch
may recover space; silent growth into adjacent ownership is not an option.
Do not promise relocation is a trivial name-table change or compensate for
placement pressure with more hardcoded applications.

## Acceptance

- An app absent from the OS source/catalog can be built separately, copied to
  the disk and launched without rebuilding the system.
- The same binary runs correctly in at least two different compatible slots,
  including C globals, pointer-bearing data, BSS, calls, software stack and
  yield/sleep across context switches. Suitable free slots are selected
  automatically, independent of filename and launch order.
- Multiple different generic apps keep independent data, windows, titles and
  input through drag/focus/close/restart. Duplicate-instance policy is explicit;
  ownership is task/instance based, never inferred solely from a name.
- Invalid images/relocations, unsupported versions, missing files, no fitting
  slot and an over-capacity launch leave every live peer and retained image
  unchanged. Every rejection cleans up partial loader resources.
- The running panel reflects actual instances; console I/O, foreground Ctrl+C,
  background launch and desktop shutdown remain usable.
- Existing apps continue to work during migration. Completion includes a clear
  four-slot compatibility model, not a claim that a large binary fits every slot.
- Host tests, actual-link memory checks, VICE D64/D71, native 1986 input, then a
  concrete physical-C128 test candidate. Preserve exact artifacts and evidence.

## Related work and boundaries

The follow-up to `1699e82` adds bare foreground native launch with cooperative
Ctrl+C, deferred desktop initialization on CREATE, and a standalone console
SDK/proof (arguments, streams, return status, BSS reset with four windows).
All three VICE formats now qualify those paths; D81 adds real 1581 geometry,
not an extension rename. Console commands use the existing synchronous UDEX
0.1 loader, not native task slots; native arguments/background console I/O are
not complete. Instance/name-based stop and migration of the named apps remain
the next #35 increments. See [the SDK](GRAPHICAL-APPS-SDK.md).

- PR #31 / issue #30 provides the merged four-app baseline; its historical
  qualification records remain immutable.
- Issue #32 (`additional-apps`) exposed this limitation. Its `.CBM` container
  and PNG/JPEG converter commit `6b61f5c` remain on their own branch/worktree;
  do not discard, merge or modify that exploration as an incidental step.
- No larger concurrency ceiling, preemption, scripting, graphics optimization
  or wholesale service extraction is required for this feature.
