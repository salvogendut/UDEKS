# UDEKS roadmap

This roadmap is organized around demonstrable capability gates. Dates are not
assigned until the bring-up measurements expose the true hardware costs.

## Phase 0 — Foundation

- [x] Select `GPL-3.0-or-later`.
- [x] Select cc65/ca65/ld65 for the 8502.
- [x] Select SDCC plus RASM for Z80 development.
- [x] Establish source layout, build entry points, and host checks.
- [x] Draft the mailbox ABI and architecture plan.
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

- [ ] Define the reset/loader contract and final bootstrap load address.
- [ ] Establish a known MMU state without relying on undocumented ROM state.
- [ ] Bring up a polled VDC text console.
- [ ] Add a panic screen and emulator-visible diagnostic codes.
- [ ] Detect PAL/NTSC, model, VDC RAM size, and optional memory expansions.
- [ ] Produce the first bootable D71 image.

**Exit gate:** a stock configuration boots to the same diagnostic console in
`1986`, VICE, and real hardware.

## Phase 2 — Memory and interrupts

- [ ] Adopt the permanent bank/common-RAM map through an architecture decision.
- [ ] Implement atomic MMU configuration primitives.
- [ ] Implement IRQ/NMI entry, CIA tick, and monotonic time.
- [ ] Define kernel, task, and interrupt stack bounds with canaries.
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
- [ ] Add host tests for scheduler and queue policy.

**Exit gate:** at least four C tasks survive repeated preemption while performing
banked-memory and display operations.

## Phase 4 — Secondary execution engine

- [x] Prove the MMU CPU-switch sequence in a minimal assembly spike.
- [ ] Implement mailbox validation, sequence numbers, and error results.
- [ ] Implement `NOP`, copy, checksum, and one decompression operation.
- [x] Measure handoff cost and define initial per-operation size thresholds.
- [ ] Add repeated handoff and malformed-request tests.
- [ ] Confirm behavior on real hardware.

**Exit gate:** 100,000 mixed worker transactions complete without deadlock or
mailbox corruption, with published benchmark results.

## Phase 5 — Dual-display and input system

- [ ] Define display surface and mode APIs.
- [ ] Implement queued VDC text and bitmap transfers.
- [ ] Implement VIC text/bitmap surfaces, sprites, and raster service.
- [ ] Support VDC-only, VIC-only, mirrored, and extended desktop modes.
- [ ] Add keyboard, joystick, mouse/paddle, and light-pen event sources.
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
