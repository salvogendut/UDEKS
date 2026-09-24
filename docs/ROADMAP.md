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

- [ ] Freeze the initial syscall jump-table ABI.
- [ ] Implement task creation, exit, yield, sleep, and event wait.
- [ ] Save and restore the selected compiler runtime and CPU context.
- [ ] Add cooperative scheduling, then timer-driven preemption.
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
- [x] Separate VIC-IIe display, window-manager, and temporary application-poll
  lifecycles into independently registered modules.
- [x] Route normalized keyboard events to a fixed-focus root-terminal editor.
- [ ] Generalize keyboard input routing to arbitrary focused windows; pointer
  routing to managed VIC-IIe windows is complete.
- [ ] Implement queued VDC text and bitmap transfers.
- [ ] Implement VIC text/bitmap surfaces, sprites, and raster service.
- [x] Add `xinit` with an initial bank-1 VIC-IIe hires surface and centered
  black X pointer while the VDC console remains active.
- [x] Reserve control port 1 for a proportional 1351 mouse, reserve control
  port 2 for a digital joystick, and merge both into a frame-paced pointer.
- [x] Build the first fixed-window `xclock` graphical application, following the bounded
  analog-clock design proven in GEOBENCH.
- [x] Build `xwave` as a wireframe function plotter using bounded Z80 sample
  computation, 8502 VIC-IIe rendering, and VDC-console `Ctrl+C` cancellation.
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

- [ ] Implement IEC device discovery and baseline serial operations.
- [ ] Add 1571 burst support only after baseline correctness.
- [ ] Define filesystem and executable/module formats.
- [ ] Implement file, directory, and stream syscalls.
- [ ] Add disk-error recovery and media-change handling.
- [ ] Load and terminate relocatable C applications.

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
