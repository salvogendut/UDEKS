# UDEKS roadmap

This roadmap is organized around demonstrable capability gates. Dates are not
assigned until the bring-up measurements expose the true hardware costs.

## Phase 0 — Foundation

- [x] Select `GPL-3.0-or-later`.
- [x] Select cc65/ca65/ld65 for the 8502.
- [x] Select SDCC plus RASM for Z80 development.
- [x] Establish source layout, build entry points, and host checks.
- [x] Draft the mailbox ABI and architecture plan.
- [x] Accept ADR 0004: assembly-oriented microkernel with predominantly C
  service modules.
- [x] Install cc65 in `my-distrobox` and validate the initial 8502 link.
- [ ] Pin the release toolchain independently of distribution package updates.
- [x] Install VICE 3.10 C128 and `c1541` via Flatpak as the independent
  oracle/tooling.
- [x] Record exact emulator/tool versions and artifact/result checksums.

**Exit gate:** a fresh reference container can build byte-identical 8502 and Z80
scaffold images and run `make check`.

## Phase 0.5 — Executive CPU decision

- [x] Build one measurement harness that can run equivalent 8502 and Z80 cases.
- [x] Qualify initial 8502 native-vector and Z80 IM1 CIA interrupt paths in
  `1986`, with raw entry-through-prologue latency samples.
- [x] Measure minimal, kernel-tick, and jump-table interrupt-service paths in
  `1986`, including paired post-prologue-to-resume costs.
- [x] Measure qualified CPU, compiler-runtime, and full task-context
  save/restore primitives in `1986`.
- [x] Measure syscall dispatch, event-queue traffic, and validated MMU/CIA/VDC
  register transactions in `1986`.
- [x] Measure real `$D505` ownership round trips and complete mailbox
  transactions in both CPU directions in `1986`.
- [x] Measure end-to-end copy, checksum, and transform offload thresholds in
  both directions from 16 bytes through 2 KiB in `1986`.
- [x] Preserve the exact result-set PRGs and hashes for later VICE and physical
  C128 runs.
- [x] Run the corrected r2 suite in VICE 3.10 and preserve all 19 canonical
  result blocks plus focused repeats.
- [x] Rerun all 19 corrected r2 configurations in `1986`, preserve the raw
  blocks and focused repeats, and compare them with VICE.
- [ ] Measure compiled-C and handwritten-assembly workloads separately.
- [ ] Broaden memory-access and device-I/O coverage beyond the initial slices.
- [ ] Exercise VDC-only, VIC-active, and dual-display conditions on PAL and NTSC.
- [ ] Cross-check corrected `1986` and VICE results against at least one real
  C128.
- [x] Publish the current raw emulator results, tool versions, test binaries,
  hashes, and interpretation.
- [x] Accept ADR 0002: 8502 resident executive with a bounded, selectively
  scheduled Z80 worker; update the execution plan and mailbox direction.

**Exit gate:** the corrected logical suite agrees across `1986` and VICE, and
ADR 0002 names the executive and secondary engine with preserved evidence.
Display-pressure and real-hardware work remain mandatory validation gates and
may revise workload policy without reopening the CPU roles unless they expose
a material contradiction.

## Phase 1 — Machine bring-up

- [x] Define the proposed stage-0/stage-1 loader contract and fixed bootstrap
  addresses in ADR 0003.
- [x] Make the direct-load 8502 entry establish the kernel MMU profiles, top
  common RAM, and initial page-zero/page-one locations explicitly.
- [x] Qualify all four MMU profiles, bank-private RAM, common RAM, and relocated
  page zero/page one in VICE and `1986`.
- [x] Implement and validate native D71 stage 0 and stage 1 in VICE and `1986`.
- [ ] Accept ADR 0003 after its display-memory and physical-hardware gates pass.
- [x] Bring up a polled VDC text console as a modular C service over bounded
  assembly transport, qualified in VICE and `1986`.
- [x] Add a stack-independent assembly panic screen and emulator-visible
  diagnostic record, including a fault-injected service-startup test image.
- [x] Detect PAL/NTSC, VDC revision/family, 16/64 KiB VDC RAM, and REU/GeoRAM
  presence without treating an upgradable hardware feature as a chassis ID.
- [ ] Add physical-model configuration and expansion-capacity discovery after
  the resource allocator can grant destructive-test ownership.
- [x] Produce the first bootable D71 image.

**Exit gate:** a stock configuration boots to the same diagnostic console in
`1986`, VICE, and real hardware.

## Phase 2 — Memory and interrupts

- [ ] Accept ADR 0003 as the permanent bank/common-RAM map after its emulator
  and hardware validation gates pass.
- [x] Prove atomic preconfiguration-register MMU switching from common RAM.
- [ ] Expose the qualified MMU-switch primitive through the kernel API.
- [ ] Implement IRQ/NMI entry, CIA tick, and monotonic time.
- [ ] Define kernel, task, and interrupt stack bounds with canaries.
- [x] Establish and initialize the first cc65 software stack at `$EFF0` for C
  service execution; task-specific stacks and canaries remain pending.
- [ ] Implement bank-aware allocators and buffer ownership.
- [ ] Verify VIC-visible and VDC-transfer buffers on PAL and NTSC.

**Exit gate:** interrupt soak tests run for one hour without stack, bank, or
display corruption.

## Phase 3 — Executive kernel

The active execution sequence and acceptance criteria for this phase are in
the [Tasking 0.1 handover](../HANDOVER.md).

- [x] Freeze the initial 8502 syscall table and program-entry ABI.
- [x] Link a bounded common-RAM gate that preserves resident and bank-1 cc65
  zero-page contexts around a cooperative task poll.
- [x] Add a synchronous common-RAM request record with task-side nonblocking
  `read`, bounded `write`, Unix descriptors, and Linux errno values.
- [x] Qualify the cooperative context-switch core and select relocated
  page-zero/page-one ownership
  ([ADR 0008](decisions/0008-context-switch-placement.md)).
- [x] Freeze Task Request ABI 0.3 lifecycle operations and errno behavior, and
  host-validate lifecycle transitions plus mutation-free request policy.
- [x] Qualify the scheduler delivery path and reclaim the VIC shadow, crt0,
  probe, and boot-only capability placements without breaking D71/D64 boot or
  application-slot reuse ([ADR 0009](decisions/0009-boot-only-capability-relocation.md)).
- [ ] Accept the boot-console relocation after its VICE-qualified D71/D64 and
  slot-2 reuse path also passes in `1986`
  ([ADR 0010](decisions/0010-boot-console-relocation.md)).
- [x] Extract the final resident boot-delivery gather into the lower VIC
  shadow, preserving the frozen `$2003` entry and the scheduler checksum gate.
- [x] Prove that the lifecycle state and request-policy modules fit the
  reclaimed scheduler page/tail overlay and bind to an identical resident
  cc65 runtime in normal and panic maps; installation remains part of the
  lifecycle-handler increment.
- [x] Load the checksummed scheduler page/tail `SCHEDOVR` payload into bank 1
  from both D71 and D64, install it through the bounded `$FF05-$FFC4` one-shot
  gate, and replace that gate with the permanent task gateway before entering
  the kernel. VICE is qualified; `1986` and physical hardware remain the
  acceptance gates for ADR 0012.
- [x] Register persistent `/bin/ush` as running lifecycle task 1 at startup,
  publish its `UTSK` state, and retain the proven `$FF13` poll path while the
  cooperative resume mechanism is introduced.
- [x] Add the bounded round-robin runnable-task selector and host-test empty,
  sparse, wrapped, and post-yield selection without exposing a premature
  synchronous `YIELD` syscall.
- [x] Qualify relocated page-zero/page-one switching with two compiled cc65
  tasks retaining live C frames, private software stacks, and stack canaries
  for 64 switches in `1986` and VICE at 1/2 MHz. Physical hardware remains
  pending; production `$FF16` integration is qualified separately below.
- [x] Fit a production-shaped save/restore tail behind the frozen
  `$FF10/$FF13/$FF16` entries: 191 bytes in the exact 192-byte common-RAM
  reservation. Its separate resident binding also fits eight context records
  and callbacks in all 323 post-overlay bytes, plus six fixed page
  vectors. Their bounded post-startup delivery is active: the page
  vectors and 42-byte activator staged at `$1BAA` and installed at `$F68A` are
  checksum covered. The installed context/gate images and lifecycle handler now
  implement the `$CF30` carry contract; persistent `/bin/ush` repeatedly
  yields, resumes, and accepts commands in VICE from both D71 and D64.
- [x] Implement production cooperative `YIELD` for persistent `/bin/ush`.
- [x] Implement non-returning `EXIT`, preserving zombie status for `WAITPID`.
- [x] Implement immediate and `NOHANG` `WAITPID`, including atomic zombie
  reap and Linux-compatible `ECHILD` behavior.
- [x] Implement blocking `WAITPID` with private per-task request ownership;
  qualify child `EXIT(37)` waking and resuming its parent on D71 and D64.
- [x] Add the bounded `$F919` SPAWN loader seam: validate a flag-zero UDEX and
  copy its image/BSS into bank-1 APP1 without entering it; qualify byte-exact
  loading and a pre-seeded nonzero BSS on D71 and D64 before task-table
  mutation is introduced.
- [x] Implement atomic `SPAWN` task creation for the initial task-2/APP1
  allocation, including relocated `$D3/$D4` context pages, normal-return
  conversion to `EXIT(status)`, blocking parent `WAITPID`, and slot reuse.
  A compiled cc65 child completes two spawn/exit/reap cycles from both D71
  and D64.
- [x] Implement bounded `SLEEP` over a wrap-safe 16-bit monotonic clock,
  normalized to 60 logical ticks/s on PAL and NTSC. D71/D64 probes qualify
  invalid bounds and exact blocking wake/resume ownership.
- [x] Implement child-only `CANCEL`, including atomic rejection, blocked-wait
  cleanup, status 130 zombies, and subsequent `WAITPID` reap on D71 and D64.
- [x] Host-test and cc65-compile the proposed stdin-readiness validation and
  timeout policy without linking or advertising the ABI extension.
- [x] Implement resident ABI 0.4 `POLL` and migrate idle shell input waiting.
  The compiled-C probe and graphics/utility smoke pass on D71/D64 in VICE;
  independent 1986 machine-input typing/history, dragging and foreground Ctrl+C
  pass on both formats; physical-C128, manual host input and performance gates remain
  in [EVENT-WAITS.md](EVENT-WAITS.md) and issue #4.
- [x] Save and restore the selected compiler runtime and CPU context behind
  the production scheduler gate. Physical-hardware qualification of the
  integrated path remains part of the milestone acceptance gate.
- [x] Extend cooperative scheduling to the initial task-2/APP1 child alongside
  the persistent shell task.
- [ ] Generalize task allocation beyond the initial two-task configuration,
  then add timer-driven preemption.
- [ ] Qualify responsive graphics under input pressure (issue #6): xwave initial
  drawing now advances in four-vertex polls; synchronous compositor replay and
  exposed-window redraw still need work before performance acceptance.
  Issue #10 integrates scratch-only raster storage with preserved placement;
  emulator primitive and drag-release timings improve, but cached repaint still
  takes seconds. Focused xwave replay now uses four-vertex poll chunks after
  damage/chrome composition; the obscured-window path and damage/chrome/clock
  redraw remain synchronous. Full compositor and physical qualification remain.
  A packed move-cache format and standalone bank-crossing prototype now pass
  pixel/guard checks in 1986 and VICE with IRQs masked. The C paste still takes
  seconds and needs 1,273 bytes against a 49-byte resident reserve. The measured
  ASM byte blitter now passes both emulators plus all 64 alignment pairs;
  default paste is 4.56–6.87× faster but wrapper/ASM/state still needs 1,023
  bytes, and its complete-operation lease does not yield. The runtime placement
  audit finds no drop-in home: scheduler overlays own the entire primary-map
  gap. Next is measuring in-place ASM raster replacements without changing
  stacks/shadow/APIs, then bounded lease integration; active-IRQ, ownership,
  compositor and physical gates remain. Production still replays pixels on moves.
  C-clipping/ASM-span fill and the public ASM pixel entry now pass independent
  pixel/dirty/stack gates and are installed in the display service. Their 173
  net bytes remain named padding; frozen placements and ABIs are unchanged.
  D71/D64 native drag/input/background-clock and VICE app/bitmap gates pass.
  Measured release delays improve, but full deferred repaint still takes
  seconds; physical validation and responsive-compositor acceptance remain.
  Shared-pixel C line stepping, span rectangles and ASM clear are also now
  installed: another 294 saved bytes stay padded; both-format emulator gates
  and clean-build determinism pass. Primitive lines improve 6–8%, rectangle
  matrix 4.14×, clear about 10×; sampled cancellation is not improved.
  Cache reserves total 516, still at least 507 short before bindings/bounded
  state. Next: explicit service-placement/shared-raster budget investigation.
  Physical/visual qualification remains pending; pixel-cache moves are not
  enabled. See [GRAPHICS-SHARED.md](GRAPHICS-SHARED.md).
  A private bank-1 row-overlay proof now passes both emulators with active
  IRQs and an actual SEI-removal negative control: 213 bytes in bank 1,
  194 resident binding bytes, leaving 322 before integration costs. Delivery,
  ownership/completion, bounded compositor state and live-service/HW gates
  remain; no pixel-cache move is enabled. See
  [WINDOW-CACHE-OVERLAY.md](WINDOW-CACHE-OVERLAY.md).
  Experimental core-prefix delivery now passes both-format VICE/native boot
  and lifetime gates without changing normal disks or resident bytes. Pure C
  generation/row policy is host-tested; its 2,567-byte bank-1 core/policy/helper
  link is measured but unexecuted. The live shell stack cannot be borrowed;
  private C runtime/stack and explicit completed-image ABI gates come next.
  See [WINDOW-CACHE-DELIVERY.md](WINDOW-CACHE-DELIVERY.md). Cached moves remain
  disabled; there is no new user-visible cache build to test yet.
  A subsequent private C dispatcher/stack proof passes both emulators: real
  policy and row transfers, all runtime/I/D/stack/guard checks, and three
  single-byte fault controls (IRQ map, ZP restore, shell-stack alias) are
  qualified. Module code is 2,685 + 28 state; bindings277 leave239 resident
  reserve bytes before integration. Completion/marshalling/continuation fit,
  production delivery, live input/task/Z80, NMI and HW gates remain. See
  [WINDOW-CACHE-C-RUNTIME.md](WINDOW-CACHE-C-RUNTIME.md).
  Latest checkpoint: the combined bounded C command and repeated pixel reuse
  pass both emulators, including live fault controls. UAPP 0.3 explicit image
  completion IS installed, preserving all 53 vectors/ZP; both-format boot,
  input/drag/cancellation/recertification and bitmap gates pass. The seam
  spends 158 resident bytes. Subsequent installed NMI deferral spends 77,
  leaving 281 padding; exact-stub C-lease stress and both-format normal
  input/Z80/clock/drag/cancellation gates pass in both emulators. Physical
  RESTORE confirmation remains. The uninstalled 241-byte binding would leave
  40 before manager/delivery integration; bootfs is exactly 11,708 bytes.
  Complete integration fit, C-module delivery and live cached moves remain
  unfinished. Production moves still
  redraw. See [WINDOW-CACHE-COMMAND.md](WINDOW-CACHE-COMMAND.md).
  NMI evidence/manual gate: [WINDOW-CACHE-NMI.md](WINDOW-CACHE-NMI.md).
  Subsequent private C manager savings recover 221 with identical host drawing/
  state traces and both-format emulator gates. Current padding502, binding241
  leaves261; a real bank-0 continuation/link is still739 short BEFORE actual
  manager hooks/locks/delivery. The four-byte C continuation is host-tested,
  not installed. The subsequent direct in-bank controller fits at3,977 bytes
  with26 private state, guarded240-byte stack and2,224-byte image (default2,184).
  Both emulators pass single-row/stale-ticket/repeated-paste/pixel/dirty/ZP/
  stack/I/D/IRQ/NMI and four live fault controls. Next: complete module delivery
  and bounded resident hooks/locks within261 remaining bytes before live GUI
  gates. No cached move is enabled. See
  [WINDOW-MANAGER-BUDGET.md](WINDOW-MANAGER-BUDGET.md) and
  [WINDOW-CACHE-CONTROLLER.md](WINDOW-CACHE-CONTROLLER.md).
  Whole-controller delivery/lifetime now passes on separate D71/D64 test disks
  in both emulators, moving only the temporary scheduler source5000→6000.
  Complete code/identity bytes survive apps, utilities and graphics restart;
  native32-drag/clock/cancellation gates pass. Zero new resident delivery bytes,
  but runtime acceptance, persistent tickets, bounded compositor hooks/locks
  and actual live cache execution still need qualification. Normal disks
  unchanged; no cached move is enabled. See
  [WINDOW-CACHE-CONTROLLER-DELIVERY.md](WINDOW-CACHE-CONTROLLER-DELIVERY.md).
  Page-bounded pre-C acceptance and persistent original-ticket reconstruction
  now pass standalone machine tests in both emulators, including bad payload/
  header rejection and four live runtime faults. The safe measured closure is
  553 resident bytes versus502 available:51 short BEFORE compositor hooks.
  Recover implementation bytes, then qualify the full manager hook/lock link;
  normal disks remain unchanged and pixel-cached moves are still disabled. See
  [WINDOW-CACHE-ACCEPTANCE.md](WINDOW-CACHE-ACCEPTANCE.md).
  A subsequent standalone compact transport recovers182 resident bytes by
  loading the gateway from the validated bank-1 module. Charged closure371,
  aggregate headroom131 BEFORE compositor hooks; no complete-link fit claim.
  Module4,106 bytes includes196-byte gateway source and needs17 validation
  polls. Stack/image capacity unchanged; both emulators pass full pixels,
  repeated pastes, bad-image rejection and four live fault controls. Revised
  module delivery now passes both formats/emulators; isolated normal/panic
  transport-only links preserve every segment/helper with131 bytes remaining.
  No live cache invocation or compositor hook fit yet. Next: measure real
  manager hooks/locks, regenerate bridges, then qualify the integrated path.
  See [WINDOW-CACHE-COMPACT.md](WINDOW-CACHE-COMPACT.md) and
  [WINDOW-CACHE-COMPACT-DELIVERY.md](WINDOW-CACHE-COMPACT-DELIVERY.md).
  Latest: a separate bootable compositor candidate now invokes the bounded
  cache. Actual normal/panic links preserve every segment and runtime helper,
  with159 padding bytes left; regenerated bridges avoid the earlier stale-link
  hazard. Both-format native1986 tests cover repeated cached moves with full
  pixels and no new wave painter/Z80 calls, clock repair, resize fallback,
  Ctrl+C, typing and restart. VICE qualifies capture/bitmap/NMI/restart (not
  native dragging). The user reports the manual candidate looks good; platform
  and individual cases were not specified. Normal disks remain
  unchanged. Release plus cache presentation still takes roughly4–5s in the
  sampled PAL sequence, so responsive-compositor and physical gates remain
  open. See [WINDOW-CACHE-LIVE.md](WINDOW-CACHE-LIVE.md).
  A separate band-boundary commit follow-up keeps the four-row poll budget,
  reduces median page copies56→22.5 and settled-paste frames156.5→129.5; every
  pixel/input/guard gate passes. A clock-minute repair outlier still takes313
  frames, so worst-case responsiveness remains open. The timing change also
  exposed and fixed a `$D011` shutdown raster-target bug (one byte, unchanged
  placement), now tested at late raster295 with continued typing/restart.
  See [WINDOW-CACHE-REPAINT.md](WINDOW-CACHE-REPAINT.md). Normal cache promotion
  remains separate from this test disk; only the shutdown fix is normal-linked.
  A geometry-based occlusion follow-up now avoids pasting for hidden, exposed
  upper-strip and disjoint lower-window damage. Forced clock updates drop from
  278 to 119/126 PAL frames (hidden/upper strip), copying 0/2 pages instead of
  40/44 with identical canvases. Sampled worst drag-paste latency drops313→163;
  median full move time is essentially unchanged. Complex overlap remains a
  ~5s fallback, so general responsiveness and physical/default-promotion gates
  stay open. See [WINDOW-CACHE-OCCLUSION.md](WINDOW-CACHE-OCCLUSION.md).
  A separately qualified prefix/row-range command now repairs only intersecting
  rows and the necessary left prefix, preserving the full packed source stride.
  Partial-overlap clock repair improves254→195 PAL frames, 33→23 page copies,
  with complete canvas equality; hidden/strip timings stay unchanged. Provider
  and integrated disks pass host/1986/VICE gates, including cancellation/input
  regression tests and clean-build determinism. Normal disks remain unchanged;
  ~3.9s still leaves responsiveness and physical/default-promotion gates open.
  See [WINDOW-CACHE-PARTIAL.md](WINDOW-CACHE-PARTIAL.md).
  User testing then exposed xclock-over-xwave drag-start latency missed by
  wave-only drag tests. An isolated deferred-background candidate clears the
  old rectangle and moves only the outline, repairing exposed pixels on
  release. Native clock drag-start improves265→16 PAL frames; full pixel,
  input/cancel/restart, placement and clean-build gates pass in both formats.
  Release repair remains synchronous; manual/physical acceptance and normal
  promotion are still open. See [WINDOW-DRAG-START.md](WINDOW-DRAG-START.md).
  The user reports improved drag start. Per user direction, future wave
  projection and render caches belong to xwave, not the windowing system;
  that separate application experiment is not part of this milestone.
  The merged window-manager milestone keeps caching opt-in. Default-build
  integration and its input/hardware acceptance gates are the next manager step.
  See [WINDOW-MANAGER-MILESTONE.md](WINDOW-MANAGER-MILESTONE.md).
  The next increment now provides a source-built `WINDOW_CACHE=1` normal-build
  configuration, regenerated acceptance bindings and pre-packaging normal/panic
  layout guards. Both-format 1986/VICE qualification and clean 1→0→1 switching
  pass. The user reports it looks OK on real hardware and confirms RESTORE
  during window dragging with working input afterward. The requested manual
  hardware gate is passed, and the user approved default promotion. `make boot`
  now enables the cache; `WINDOW_CACHE=0` retains the prior compositor. Slow
  synchronous release/background repair remains open. See
  [WINDOW-CACHE-INTEGRATION.md](WINDOW-CACHE-INTEGRATION.md).
  Next manager increment is issue #14, `graphics-bounded-repaint`: measure
  continuous compositor call durations and input-service gaps, then host-test
  damage continuation/cancellation and bound manager-owned composition. The
  synchronous painter contract must be addressed explicitly; merely moving a
  whole callback to another poll is not bounded. No xwave-specific projection
  work is included. See [WINDOW-REPAINT-CONTINUATION.md](WINDOW-REPAINT-CONTINUATION.md).
  The private continuation reference now passes host receipt/invalidation and
  full mock-canvas tests, including interrupted repair and destroy/reuse. Actual
  cc65 measurement is 4,643 CODE plus 22 caller-state bytes, too large to add
  directly. Next is a compact replacement adapter with a measured placement
  plan; normal disks and public painter ABI remain unchanged.
  Preparation now proves a private state-compaction candidate can recover
  117 CODE + 12 HIGHBSS bytes in both normal/panic links, with matching host
  canvases and lifecycle traces. This is not installed or a latency improvement;
  the bounded adapter/state layout and renderer contract remain open.
  The private 18-byte lane now matches reference traces/canvases; one-row chrome,
  <=4-row clearing and <=1-page commit are host-tested with receipt validation
  and clip cleanup. CLIENT/RESTORE stay delegated, not implemented. State can
  replace the old damage box within 88 bytes, but the C code remains at least
  3,171 bytes short before integration costs. Next is the modular service's
  placement/transport proof, then renderer and real poll gates. No disk change.
- [ ] Add message queues and capability-based device handles.
- [x] Define service-module descriptor ABI 0.1, version negotiation, and the
  startup lifecycle.
- [x] Invoke resident service poll vectors cooperatively and report failures
  through the service-registry panic path; scheduler cadence, stop, and dynamic
  loading remain future work.
- [ ] Move console, graphics, storage, and filesystem policy into C service
  modules with no private microkernel dependencies.
- [ ] Add host tests for scheduler and queue policy.

**Exit gate:** at least four C tasks survive repeated preemption while performing
banked-memory and display operations.

## Phase 4 — Secondary execution engine

- [x] Prove the MMU CPU-switch sequence in a minimal assembly spike.
- [x] Implement production mailbox validation, sequence numbers, error results,
  and a boot-time `NOP` transaction through the bounded Z80 worker.
- [ ] Implement copy, checksum, and one decompression operation after defining
  bank-aware buffer leases and measured admission thresholds.
- [x] Measure handoff cost and define initial per-operation size thresholds.
- [ ] Add repeated handoff and malformed-request tests.
- [ ] Confirm behavior on real hardware.

**Exit gate:** 100,000 mixed worker transactions complete without deadlock or
mailbox corruption, with published benchmark results.

## Phase 5 — Dual-display and input system

- [x] Define the initial owned VDC surface API with pixel, span, rectangle,
  software-text, dirty tracking, and bounded assembly flush operations.
- [x] Compose the cold-boot surface in system RAM, upload it as one hidden
  16,000-byte transfer, and reveal the completed bitmap atomically.
- [ ] Complete the capability-tiered VDC compositor described in
  `docs/VDC-FRAMEBUFFER.md`.
- [x] Bring up and qualify the baseline 640x200 one-bit VDC framebuffer on 16
  and 64 KiB VDC configurations in VICE and `1986`.
- [x] Convert the compact 64x64 pipe artwork at build time and place it at the
  upper left, with system information below, as the framebuffer-backed splash.
- [ ] Degrade cleanly to the text console when framebuffer initialization fails.
- [x] Add a software-defined bitmap font, then render the `HCAP` PAL/NTSC, VDC,
  and expansion-memory results as the second framebuffer client.
- [x] Adapt `assets/bootscreen.png` into a logo rail and full-height bordered
  boot console drawn through the public graphics primitives.
- [x] Retain the bordered root console as a 64x21 text-cell model independent
  of its VDC rendering.
- [x] Enter and verify VDC-only 2 MHz operation after VIC-based hardware
  discovery and before display composition.
- [x] Return the production boot policy to 1 MHz after adopting the native VDC
  text console, preserving VIC-IIe display availability; retain 2 MHz as an
  explicit VDC-only lease.
- [x] Add terminal output, cursor movement, wrapping, and scrolling to the root
  console model.
- [x] Track root-console row damage and re-render only changed rows through the
  owned framebuffer surface.
- [x] Track bounded row and cell damage so interactive terminal edits avoid a
  full-surface dirty-map scan and full-row redraw.
- [x] Use the lower logo rail for a change-driven list of running graphical
  applications.
- [x] Add bounded window descriptors, z-order, clipping, damage, and
  back-to-front recomposition for overlapping text and bitmap windows.
- [x] Add Window Manager 0.1 with a bounded registry, managed bitmap chrome,
  client clipping, pointer routing, and content-hidden assembly-blitted outline
  dragging.
- [x] Advance the VIC-IIe Window Manager to 0.2 with bounded damage-region
  recomposition, compact z-order, click-to-focus/raise, and overlap-safe
  managed client painting.
- [x] Advance the VIC-IIe Window Manager to 0.3 with a visible lower-right
  resize grip and content-hidden outline resizing before release-time repaint.
- [x] Separate VIC-IIe display and window-manager lifecycles, then replace the
  temporary embedded application pollers with a loader-managed app dispatcher.
- [x] Route normalized keyboard events to a fixed-focus root-terminal editor.
- [ ] Generalize keyboard input routing to arbitrary focused windows; pointer
  routing to managed VIC-IIe windows is complete.
- [ ] Implement queued VDC text and bitmap transfers.
- [ ] Implement VIC text/bitmap surfaces, sprites, and raster service.
- [x] Add `xinit` with an initial bank-1 VIC-IIe hires surface and centered
  black X pointer while the VDC console remains active.
- [x] Reserve control port 1 for a proportional 1351 mouse, reserve control
  port 2 for a digital joystick, and merge both into a raster-paced pointer.
- [x] Build the first fixed-window `xclock` graphical application, following the bounded
  analog-clock design proven in GEOBENCH.
- [x] Build `xwave` as a two-axis isometric radial sinc mesh using bounded Z80
  row computation, 8502 VIC-IIe rendering, and VDC-console `Ctrl+C`
  cancellation.
- [x] Make xclock and xwave graphics respond to managed-window resizing.
- [x] Cache the completed xwave surface so move, reveal, and restacking paints
  use the 8502; reserve new Z80 sampling leases for launch and resize only.
- [x] Add shell foreground jobs and a whitespace-delimited trailing `&` for
  background `xclock` and `xwave` execution.
- [ ] Build `xmandel` from the GEOBENCH `XAOS.APP` fixed-point design as a
  tiled Z80-compute/8502-present stress test with zoom and recenter controls.
- [ ] Support VDC-only, VIC-only, mirrored, and extended desktop modes.
- [x] Add a polled full-matrix C128 keyboard source with normalized queued
  press/release events.
- [x] Debounce matrix rows across consecutive scans and derive modifiers from
  stable state before exposing keyboard input to the terminal.
- [x] Add a bounded root-terminal line editor with insertion, Backspace,
  horizontal cursor movement, retained submission, and VDC repaint.
- [x] Make the root terminal a direct VDC text-mode client with a hardware
  cursor and custom upper-half glyphs for the logo and window edges.
- [x] Preserve mixed-case terminal text with per-cell VDC primary/alternate
  character-set attributes.
- [x] Add a bounded native shell parser and command registry with initial
  console, version, hardware, service, and CPU-role commands.
- [x] Give shell commands Unix-like `argc`/`argv`, exit status, and standard
  stream descriptors without coupling commands to VDC hardware.
- [x] Add bounded volatile shell history with Up/Down command recall and draft
  restoration.
- [ ] Benchmark equivalent VIC-IIe and VDC graphics primitives, including CPU
  draw cost, transfer cost, display-cycle contention, and perceived latency.
- [ ] Implement a VIC-IIe graphics service as the preferred interactive-pixel
  candidate while retaining VDC bitmap modes for high-resolution/second-screen
  use.
- [x] Add fixed-port joystick and proportional 1351 mouse pointer sources.
- [ ] Add paddle and light-pen event sources.
- [ ] Demonstrate a two-monitor collaborative application.

**Exit gate:** both displays update independently under task and storage load
without missing input events.

## Phase 6 — Storage and executable environment

- [x] Freeze the resident-core boundary and extraction order in ADR 0007.
- [x] Define and host-validate the fixed-address UDEX 0.1 container.
- [x] Move `cowsay` to the user source tree as the first loader acceptance
  program; do not register it as a resident builtin.
- [x] Define and link the fixed syscall veneer and 8502 entry/exit convention.
- [x] Add the first loader-managed task slot and validated read-only `/bin`
  bootfs.
- [x] Add init as the registry-visible owner of the root session; its direct
  delegation to the bootstrap shell remains transitional.
- [x] Package a minimal persistent `/bin/ush`, initially boot-preload it in bank 1, and
  poll it from init through the public task/stream boundary.
- [x] Move terminal-line ownership plus native `cd`, `echo`, `help`, `pwd`, and
  `uname` handling into `/bin/ush`, with bounded compatibility exec/wait for
  commands not yet extracted.
- [x] Replace the fixed `ush` preload with init-driven, named runtime
  persistent-task allocation.
- [x] Load, run, and reclaim `cowsay` without adding it to the resident image.
- [x] Add the read-only bootfs `open`, `getdents`, `stat`, and `close`
  operations through the public syscall boundary.
- [x] Add `/bin/ls` over that directory ABI, supporting `ls`, `ls /`,
  `ls /bin`, and `ls -l /bin` without direct knowledge of devices or
  filesystem formats.
- [x] Add persistent root-session working-directory state and implement
  Bash-like `cd` and `pwd` natively in `/bin/ush`; make standalone `ls` inherit
  that state for `.`.
- [ ] Replace the bootstrap directory token with per-process `chdir`/`getcwd`
  operations as part of the general VFS process contract.
- [x] Package `xclock` as a standalone, loader-managed UDEX graphical program.
- [x] Package `xwave` as a standalone, loader-managed dual-engine UDEX
  graphical program, retaining its computed surface between repaints.
- [ ] Implement IEC device discovery and baseline serial operations.
- [ ] Add 1571 burst support only after baseline correctness.
- [ ] Define the filesystem format and mount contract.
- [ ] Complete general storage-backed file, directory, and stream syscalls.
- [ ] Add disk-error recovery and media-change handling.
- [ ] Load and terminate relocatable C applications after the fixed-address
  format is qualified.
- [ ] Extract terminal, window, display, input, time, and engine policy into
  loadable servers and remove their static pointer-table entries.
- [x] Package the native shell as `/bin/ush` and have init load it for the root
  terminal session at boot.
- [ ] Replace bootfs fallback with storage-backed `/bin` resolution after VFS
  and IEC services are available.

**Exit gate:** applications can be installed, launched, exchange files, and exit
without rebooting or corrupting media.

## Phase 7 — System services and release

- [ ] SID audio service and timer-safe sound queues.
- [ ] REU and GeoRAM acceleration/paging backends.
- [ ] Shell, system monitor, file manager, editor, and SDK examples.
- [ ] Programmer and driver documentation.
- [ ] Automated image builds and release provenance.
- [ ] Compatibility matrix across C128, C128D, and C128DCR configurations.

**Exit gate:** UDEKS 1.0 boots and performs its documented core workflows on the
supported stock hardware matrix, with reproducible GPL source releases.
