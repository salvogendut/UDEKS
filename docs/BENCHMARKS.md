# Executive CPU benchmark plan

## Purpose

UDEKS will not choose its executive CPU from convention, headline clock rates,
or a single synthetic loop. This suite compares the 8502 and Z80 as complete
kernel hosts under the C128's real bus, display, interrupt, memory, and compiler
constraints. Its result gates the scheduler, permanent boot architecture, and
final memory map.

The question is not simply “which CPU is faster?” It is “which CPU is the
better executive while the other remains useful as a bounded secondary engine?”

## Measurement rules

- Use equivalent algorithms, inputs, memory placement, iteration counts, and
  result validation on both CPUs.
- Measure compiler-generated C and purpose-written assembly as separate result
  classes. C results represent normal kernel policy; assembly results represent
  mechanisms that UDEKS can reasonably hand tune.
- Time target execution with a C128 hardware timer. Host wall-clock time is not
  a benchmark result.
- Exclude loading, startup, reporting, and CPU handoff from ordinary workload
  intervals. Measure handoff explicitly in its own cases.
- Disable unrelated interrupts during throughput cases. Measure interrupt
  latency and jitter separately with the intended interrupt configuration.
- Warm up each case, repeat it enough to expose variance, and retain the raw
  samples as well as minimum, median, maximum, and iteration count.
- Check every output or final state so an optimizer, mapping error, or incomplete
  operation cannot appear as a fast result.
- Record compiler, assembler, linker, emulator, machine, video standard, VDC
  RAM, and expansion versions or configurations with every result set.

The initial C configurations are cc65 `-Oirs` and SDCC `--opt-code-size`, because
code size is a real kernel constraint. Additional speed-oriented configurations
may be compared, but they may not replace the common baseline and their binary
sizes must be reported.

## Operating modes

Every applicable workload runs under these conditions:

1. **VDC-only:** VIC display output disabled; 8502 at 2 MHz; stock Z80 timing.
2. **VIC active:** a stable VIC display active; normal supported CPU timing.
3. **Dual display:** VDC work with an active VIC display and representative
   interrupt pressure.
4. **PAL and NTSC:** repeat timing-sensitive cases for both standards.

The baseline machine has 128 KiB system RAM and 16 KiB VDC RAM. A 64 KiB VDC
is an additional configuration, not a substitute for the baseline. Expansion
RAM is excluded from the executive decision unless reported as a separate run.

## Workload groups

### C and control flow

- 8-bit and 16-bit arithmetic and comparisons;
- branch-heavy state-machine and event-dispatch loops;
- leaf and non-leaf calls with realistic argument passing;
- fixed-width parsing and checksum kernels.

### Memory

- fill, copy, compare, checksum, and search;
- small kernel-sized blocks and larger 1–8 KiB blocks;
- aligned and deliberately awkward source and destination locations;
- same-bank, cross-bank, and common-RAM access where both CPUs can perform the
  same operation safely.

### Kernel mechanisms

- syscall jump-table dispatch;
- event-queue push and pop;
- timer-queue update;
- minimum valid task context save and restore;
- MMU/bank selection used by the candidate executive;
- mailbox encode, validate, and decode.

Context results must report exactly which registers, compiler runtime state, and
interrupt state are preserved. An artificially incomplete context is invalid.

### Devices and displays

- CIA timer and register access;
- VDC ready polling and register/data transfers;
- representative VIC register updates;
- interrupt latency and jitter under VDC-only, VIC-active, and dual-display
  operation;
- IEC byte operations when the baseline driver exists.

### Cross-CPU operation

- 8502-to-Z80-to-8502 no-op round trip;
- Z80-to-8502-to-Z80 no-op round trip;
- mailbox validation and ownership-transfer overhead;
- end-to-end copy, checksum, and transform jobs at increasing buffer sizes.

These cases establish whether and when offload pays for its handoff cost. They
do not presume which direction is the normal one.

### Documentation and implementation evidence

The comparison also records non-timing engineering evidence:

- official C128 documentation for interrupt entry, MMU state, and each device
  as seen from the candidate CPU;
- maintained examples that exercise C128-specific I/O rather than only the
  generic processor instruction set;
- working historical implementations, including the C128 CP/M BIOS, and where
  they delegate hardware work to the other CPU;
- gaps that would require hardware experiments or reverse engineering before a
  reliable executive could be implemented.

This is a qualitative implementation-risk assessment, not a count of books or
web pages. Generic Z80 literature does not by itself document the C128 bus, and
generic 6502 literature does not by itself document the C128 MMU.

## Recorded costs

Each test records elapsed timer ticks and executable size. Kernel-oriented tests
also record mutable RAM, stack high-water mark where practical, and reserved
fast-memory or common-memory bytes. Interrupt tests record minimum, median, and
worst observed latency and jitter.

The executive decision prioritizes:

1. interrupt behavior and correct, bounded context switching;
2. compiled-C performance on representative kernel workloads;
3. code, stack, common-RAM, and compiler-runtime footprint;
4. device access and coexistence with the intended display modes;
5. CPU-handoff complexity and recovery behavior;
6. quality of C128-specific documentation and proven implementation evidence;
7. bulk computation throughput.

Bulk throughput is deliberately last: whichever CPU becomes secondary can
still perform suitable bulk jobs. No single workload determines the outcome.
Qualitative blockers—such as unreliable interrupt recovery or an impractical
memory reservation—must be reported alongside the numeric scores.

## Harness and result format

The first harness will use a temporary RAM-loaded image and a fixed common-RAM
control/results block. It will run one CPU's suite, transfer ownership, run the
other suite, and return results without including that transfer in ordinary
timed regions. Early runs may be extracted from emulator memory to avoid adding
console I/O to the measurement path.

Reproducible sources and host-side result validation belong under `bench/`.
Machine-readable results belong under `bench/results/` and should use CSV or
JSON plus a short Markdown interpretation. Result metadata must make it possible
to reproduce the exact binaries.

`1986` is the development instrument and VICE is the independent emulator
check. Their corrected agreement supports ADR 0002. Real-C128 runs remain
mandatory qualification for timing thresholds and hardware-dependent
milestones and can trigger an ADR review if they materially contradict the
emulator result.

## Decision deliverable

The completed comparison updates ADR 0002 with:

- the chosen executive and secondary engine;
- links to raw results and reproducible binaries;
- the weighted interpretation and any qualitative constraints;
- consequences for boot, interrupts, task context, memory layout, and displays;
- conditions that would justify revisiting the decision.

## Current status

The initial shared-C throughput slice is implemented and has produced
repeatable emulator results. Stock-timing Z80 code was faster than 2 MHz 8502
code in all five substantive cases, while the available C128-specific
interrupt and I/O literature favors the 8502 implementation path.

The first CIA1 Timer-A interrupt probe is also implemented. Both the 8502
native vector and Z80 IM1 paths completed 32 consecutive interrupts with the
expected source on every entry. The probe records entry-through-prologue
latency after preserving the proposed ISR register set. Its repeating latency
stair steps expose `1986` scheduling granularity, so these samples qualify the
harness but cannot be treated as physical-machine latency.

The follow-up service suite measures minimal, kernel-tick, and indirect
dispatch handlers through resumption of interrupted code. Paired timestamps
make the internal costs stable despite the entry artifact. In `1986`, the 2 MHz
8502 completed the paired post-prologue-to-resume paths in 123, 134, and 137
system ticks; the stock Z80 required 425, 475, and 466. This is meaningful
emulator evidence in favor of the 8502 interrupt path, but the asymmetric ISR
register contracts and missing hardware confirmation limited the weight of
this initial r1 result.

The task-context suite is implemented as well. After empty-loop subtraction,
the 2 MHz 8502 needs 206 ticks to preserve its CPU state plus all 26 bytes of
cc65 zero-page runtime state. The stock Z80 needs 116 ticks for SDCC-complete
state and 180 when alternate registers are also admitted. This favors the Z80
for context transfer and footprint, while the 8502 retains a large CPU-only
advantage. The result makes the task ABI—not merely the CPU—part of the final
executive decision.

The kernel-primitives slice adds a second split result. The stock Z80 is 1.36×
to 1.52× faster on shared-C direct and table syscall dispatch. The 2 MHz 8502
is 1.34× faster on the shared-C event queue and 3.32× to 4.80× faster on the
assembly MMU, CIA, and VDC transaction loops. Device ownership is therefore a
material executive criterion rather than a documentation preference alone.

The bidirectional handoff suite now exercises the real `$D505` arbitration path
and ABI 0.1 mailbox with either processor as requester. At 2 MHz 8502 speed, a
bare two-transfer round trip costs 88.531 ticks for an 8502 requester and
45.969 ticks for a Z80 requester. Complete validated NOP transactions cost
373.125 and 323.062 ticks respectively. These fixed costs establish the floor
that an offloaded job must recover and provide the baseline for the following
copy, checksum, and transform size sweep.

That size sweep is now implemented for handwritten copy, 16-bit checksum, and
XOR/rotate transform kernels over 16 bytes through 2 KiB. With the 8502 at
2 MHz, delegating any of these operations from the 8502 to the stock Z80 never
wins in the tested range. In the reverse direction, Z80-to-8502 delegation
first wins at 256 bytes for copy and 32 bytes for checksum and transform. At
1 MHz, the directions are more mixed: Z80 copy first helps an 8502 requester at
128 bytes, while 8502 checksum and transform first help a Z80 requester at 256
and 128 bytes. Those historical r1 PRGs remain under
`bench/artifacts/2026-09-24/`; corrected r2 images are used for current VICE
and future real-hardware comparisons.

VICE 3.10 has now run the full corrected r2 matrix. The first pass exposed a
missing explicit Z80 `IM 1` and torn low/high reads of running CIA timers; both
were corrected without overwriting the original artifacts. All 19 r2 VICE
configurations pass strict decoding. VICE preserves the broad split—Z80 for
compiled C and compiler context, 8502 for interrupts, queues, and direct device
traffic—and strengthens the current preference for an 8502 executive. At
2 MHz, none of the three tested assembly kernels benefits from 8502-to-Z80
offload through 2 KiB. Reverse offload first wins only at 1 KiB for checksum
and transform, and not for copy in that range.

`1986` commit `7556c23` has now run the same 19 corrected r2 configurations.
All canonical blocks pass strict decoding after explicitly stopping the unused
CIA1 Timer B before the IRQ cases, and the focused IRQ-service and offload
repeats are byte-identical. `1986` and VICE agree on the executive-level split:
Z80 for the compiled-C and larger compiler-context paths; 8502 for interrupts,
CPU-core context, event traffic, and direct MMU/CIA/VDC access.
Both also find no profitable 2 MHz 8502-to-Z80 offload for the three tested
assembly kernels through 2 KiB.

The emulators disagree on some reverse Z80-to-8502 crossover sizes, most
strongly at 2 MHz. Those thresholds must therefore be calibrated on physical
hardware rather than embedded as constants. The detailed
[`1986` r2 results](../bench/results/1986-7556c23-2026-09-24-r2/README.md),
[VICE r2 results](../bench/results/vice-3.10-2026-09-24-r2/README.md), and
[corrected PRGs](../bench/artifacts/2026-09-24-r2/README.md) are preserved.
Real-hardware and display-pressure gates remain open.
