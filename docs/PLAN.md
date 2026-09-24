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

## Microkernel structure

UDEKS uses a modular microkernel architecture. The resident kernel keeps only
the mechanisms that must remain authoritative and always available: interrupt
and trap entry, context switching, scheduling primitives, IPC, MMU and bank
arbitration, capability/handle validation, and CPU ownership transfer. These
machine-facing core paths are implemented primarily in 8502 assembly and
export narrow C-callable interfaces.

I/O stacks, filesystems, graphics, display composition, consoles, protocols,
and other system policy are service modules written predominantly in C. They
communicate through versioned messages and handles rather than reaching into
kernel internals. Early images may link essential services statically, but
static placement does not permit private calls across module boundaries; the
same interfaces must support loadable and replaceable modules later. The
[service-module ABI](../abi/services.md) defines the compiler-neutral descriptor
and initial startup lifecycle used by the static bring-up registry.

The C128 has no memory-protection unit, so “microkernel” describes responsibility,
dependency direction, and failure containment by validation—not hardware-enforced
address-space isolation. ADR 0004 records this boundary.

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

ADR 0002 selects the 8502 as the resident executive. Corrected benchmark suites
in `1986` and VICE agree that it is the stronger interrupt, event, MMU, CIA,
and display-I/O engine. The Z80's compiled-C advantages remain useful through
the secondary-engine interface rather than moving device ownership away from
the 8502.

The scheduler and task context are therefore 8502-native. A task context must
account for the hardware stack, cc65 software-stack pointer, compiler-owned
zero-page state, and page-zero/page-one mappings. Early scheduling may be
cooperative while the full 33-byte cc65 context path is optimized and qualified.

### Secondary execution engine

The Z80 is a trusted synchronous execution engine, not an autonomous background
CPU. A transaction is:

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

The VDC graphics service exposes a 640×200 one-bit framebuffer surface and
software text composition. On 16 KiB VDCs the front buffer is paired with a
banked system-RAM backing surface and dirty uploads; 64 KiB VDCs may add an
attribute plane and VDC-resident staging or back buffers. The detailed proposal
is in [VDC-FRAMEBUFFER.md](VDC-FRAMEBUFFER.md).

The first framebuffer integration is a centred boot splash generated at build
time from the source artwork in `assets/`. It doubles as a visual test of mode
entry, clipping, packed scanline upload, and clean ownership transfer to the
console; text-only boot remains the failure fallback.

After the splash, a software-defined font renders the capability service's
published hardware inventory. Display code consumes `HCAP` and never repeats
hardware probes, keeping discovery policy in one service while proving
text-over-graphics composition.

The display server must support VDC-only, VIC-only, mirrored, extended, and
application-owned secondary modes. Full-time 2 MHz 8502 operation and an active
VIC display are competing requirements; mode policy must expose that tradeoff.

## Memory plan

[ADR 0003](decisions/0003-memory-bootstrap.md) proposes bank 0 for the 8502
kernel, bank 1 for the Z80 worker and initial task/data space, and bank-0
`$F000-$FFFF` as 4 KiB of top common RAM. The ordinary kernel links at
`$2000-$CFFF`; `$D000-$DFFF` remains the I/O aperture, and `$E000-$EFFF` is
reserved until stack and allocator work assigns it. Bank 1 initially reserves
`$2000-$3FFF` for Z80 code and `$4000-$7FFF` as a VIC-visible window.

The final map must define and validate:

- permanently visible kernel code and data;
- common RAM and the mailbox;
- task-local stack allocations and, for 8502 code, zero-page allocations;
- bank-0 and bank-1 ownership windows;
- secondary-CPU code, stack, and job buffers;
- VIC-visible RAM;
- load versus run addresses for banked modules;
- optional REU/GeoRAM paging and swap policy.

The MMU uses four preconfigured maps for bank-0/bank-1 execution with I/O shown
or hidden. Only top common RAM is enabled, because bottom common RAM would
override relocated zero-page and stack-page pointers. `$FF00-$FF04` are MMU
registers in every native map and must remain a hole in common code.

ADR 0003 remains proposed until the map survives 8502, Z80, VIC, VDC,
interrupt, ROM-overlay, emulator, and physical-machine tests.

## Kernel interfaces

The first stable interfaces will be:

- a versioned syscall jump table rather than direct kernel symbol linkage;
- a versioned cross-CPU mailbox;
- device classes with capability queries;
- byte-oriented filesystem and executable headers;
- display surfaces independent of a particular video chip;
- event queues for keyboard, pointer, timers, storage, and inter-task messages.
- a versioned service-module descriptor and lifecycle protocol.

Applications initially share the kernel address space but receive distinct
stacks, banked workspaces, and where practical distinct page-zero/page-one
mappings. Protection is cooperative because the C128 has no memory protection
unit.

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
| The selected executive performs poorly in later workloads | Retain portable policy code, preserved benchmarks, and explicit ADR revision criteria |
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
