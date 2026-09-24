# UDEKS architecture and implementation plan

## Purpose

UDEKS is a small native C128 operating system that exposes the machine's two
processors, two display engines, banked RAM, and expansion hardware through one
coherent executive. It is not a CP/M replacement running solely on the Z80, a
C64-mode environment, or an attempt to imitate modern symmetric multiprocessing.

## Design principles

1. **Hardware truth before metaphor.** The 8502 and Z80 alternate ownership of
   one bus. “Dual-engine” means explicit scheduling and handoff, not concurrent
   CPU execution.
2. **Stock-machine baseline.** Core functionality must run with 128 KiB system
   RAM and 16 KiB VDC RAM. Expansions improve capability without becoming
   hidden requirements.
3. **C for policy, assembly for mechanism.** State machines, resource policy,
   filesystems, and user-facing services belong in C. Reset, interrupt entry,
   context switching, MMU transitions, and cycle-critical transfers belong in
   assembly.
4. **Bounded work.** Every cross-CPU transaction and interrupt-disabled region
   has a documented upper bound.
5. **Explicit representation.** Cross-CPU, on-disk, and driver ABIs use byte
   layouts and fixed-width values rather than compiler-native structures.
6. **Testable layers.** Pure algorithms build and test on the host. Hardware
   behavior is tested first in `1986`, cross-checked in VICE, and confirmed on
   real C128 hardware.

## Supported hardware

The baseline target is a PAL or NTSC Commodore 128 with 128 KiB RAM, a 16 KiB
8563 VDC, VIC-IIe, SID, both CIAs, MMU, and an IEC device. C128D, C128DCR,
64 KiB VDC RAM, REU, GeoRAM, mouse devices, network adapters, and other storage
are runtime-detected extensions.

Machine-model differences must remain behind capability flags. Code may not
assume a DCR, 64 KiB VDC, REU, or 1571 unless the corresponding capability is
present.

## Execution architecture

### Executive CPU

The executive processor owns normal execution. Its responsibilities are:

- interrupt dispatch and timekeeping;
- task scheduling and C runtime context management;
- MMU configuration and bank ownership;
- device arbitration and driver dispatch;
- VDC/VIC display composition;
- storage, filesystem, and application services;
- creation and validation of jobs for the secondary CPU.

The 8502 and Z80 are both candidates for this role. The selection remains open
until the suite in [BENCHMARKS.md](BENCHMARKS.md) has measured compiled C,
handwritten assembly, interrupts, context switching, I/O, memory, and CPU
handoff in representative C128 display modes. ADR 0002 records the decision
process and will record its outcome.

The scheduler and context format will be designed only after that decision. An
8502 context must account for the hardware stack, cc65 software-stack pointer,
compiler-owned zero-page state, and page-zero/page-one mappings. A Z80 context
must account for the registers and interrupt state actually admitted by the
kernel ABI. Neither cost is assumed; both are benchmark inputs.

### Secondary execution engine

The non-executive CPU is a trusted synchronous execution engine, not an
autonomous background CPU. A transaction is:

1. prepare a mailbox request and any input buffers;
2. publish the request state last;
3. save the executive context and switch CPU ownership;
4. validate and execute one bounded operation;
5. publish completion and return ownership;
6. validate the result and resume executive scheduling.

Initial worker candidates are memory transforms, checksums, decompression, and
measured block operations. IEC, serial, and mathematical work move to the
secondary CPU only when a benchmark demonstrates a system-level benefit after
handoff costs.

### Displays

The VDC and VIC-IIe have separate driver instances and independent surfaces.
The VDC is the default system console and desktop. The VIC-IIe is not merely a
fallback: it can host a secondary console, preview, status surface, collaborative
view, or sprite-oriented application.

The display server must support VDC-only, VIC-only, mirrored, extended, and
application-owned secondary modes. Full-time 2 MHz 8502 operation and an active
VIC display are competing requirements; mode policy must expose that tradeoff.

## Memory plan

The current `$2000` link addresses and `$F000` mailbox are provisional bring-up
choices. The final map will define:

- permanently visible kernel code and data;
- common RAM and the mailbox;
- task-local stack allocations and, for 8502 code, zero-page allocations;
- bank-0 and bank-1 ownership windows;
- secondary-CPU code, stack, and job buffers;
- VIC-visible RAM;
- load versus run addresses for banked modules;
- optional REU/GeoRAM paging and swap policy.

No permanent address is accepted until it survives 8502, Z80, VIC, VDC,
interrupt, ROM-overlay, and model-compatibility tests.

## Kernel interfaces

The first stable interfaces will be:

- a versioned syscall jump table rather than direct kernel symbol linkage;
- a versioned cross-CPU mailbox;
- device classes with capability queries;
- byte-oriented filesystem and executable headers;
- display surfaces independent of a particular video chip;
- event queues for keyboard, pointer, timers, storage, and inter-task messages.

Applications initially share the kernel address space but receive distinct
stacks and banked workspaces. An 8502 executive may additionally use distinct
page-zero/page-one mappings. Protection is cooperative because the C128 has no
memory protection unit.

## Boot strategy

Bring-up begins as a RAM-loaded binary so reset, display, MMU, and handoff code
can be tested independently. A native bootable disk image follows after the
memory map is stable. The boot path must establish a completely documented MMU
configuration and must not leave UDEKS dependent on BASIC or KERNAL services.

ROM routines may be used only in an explicitly temporary bootstrap layer.

## Build and verification

- GNU Make coordinates both target toolchains.
- cc65/ca65/ld65 produce the 8502 image with a project-owned linker map.
- SDCC and its assembler/linker produce C-linked Z80 payloads.
- RASM produces standalone Z80 payloads and diagnostics.
- Tool versions and checksums will be pinned after the first hardware-valid
  boot spike.
- `1986` is the primary integration emulator; VICE is the independent oracle.
- Real-hardware smoke tests gate milestones that depend on MMU, timing, video,
  IEC, or expansion behavior.

## Principal risks

| Risk | Response |
|---|---|
| CPU handoff deadlocks the machine | Tiny audited worker entry; one operation per lease; emulator trace tests |
| Compiler runtime prevents safe task switching | Inspect generated code; own crt0; explicitly save all compiler-owned runtime state |
| Common RAM conflicts with ROM, vectors, or buffers | Prove the complete map before ABI 1.0 |
| The selected executive performs poorly in real workloads | Select it only after the comparative benchmark gate; retain portable policy code |
| Secondary-CPU offload costs more than it saves | Benchmark end-to-end and keep work on the executive below measured thresholds |
| VDC readiness stalls latency-sensitive paths | Bounded polling and queued display operations |
| Emulator behavior hides hardware differences | Cross-check VICE and require real-machine milestone tests |
| Toolchain optimizer regression | Pin versions and retain binary/layout regression tests |

## Definition of architectural success

The architecture is validated when a stock machine can boot without resident
ROM dependencies, schedule multiple C tasks on the selected executive, submit
and complete bounded jobs on the secondary CPU repeatedly, operate both
displays, load applications from disk, and recover cleanly from rejected jobs
and device errors.
