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
  checksum covered. The installed context/gate images and 1,213-byte handler now
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
- [ ] Implement resident event wait and migrate shell input waiting;
  placement/test gates are in [EVENT-WAITS.md](EVENT-WAITS.md) and issue #4.
- [x] Save and restore the selected compiler runtime and CPU context behind
  the production scheduler gate. Physical-hardware qualification of the
  integrated path remains part of the milestone acceptance gate.
- [x] Extend cooperative scheduling to the initial task-2/APP1 child alongside
  the persistent shell task.
- [ ] Generalize task allocation beyond the initial two-task configuration,
  then add timer-driven preemption.
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
