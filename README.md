# UDEKS

<p align="center">
  <img src="UDEKS.png" alt="UDEKS logo: a smoking pipe above the project name and Unified Dual-Engine Executive Kernel System expansion" width="560">
</p>

UDEKS—the **Unified Dual-Engine Executive Kernel System**—is a native operating
system for the Commodore 128. It is designed around the machine the C128 could
have been: a system that deliberately coordinates its 8502 and Z80 and treats
the VIC-IIe and VDC as independent, simultaneously useful display engines.

The name also echoes the Latin word *iudex*, “judge.” UDEKS is dedicated to
Lo Giudice, the teacher who introduced its creator to programming as a child
and embodied authority, knowledge, insight, firm direction, and paternal
sweetness. This project is developed in his memory. Read the full
[dedication](DEDICATION.md).

UDEKS is licensed under the GNU General Public License, version 3 or later.
See [LICENSE](LICENSE).

> [!IMPORTANT]
> UDEKS is in its architecture and bring-up phase. The current binaries are
> freestanding scaffolding and a qualified native boot path, not yet a usable
> operating system.

## Hardware model

- The 8502 and Z80 share the system bus and do **not** execute concurrently;
  ownership passes explicitly between them.
- The 8502 runs the resident executive; the Z80 is a bounded secondary
  execution engine for workloads that demonstrate an end-to-end benefit.
- The resident kernel is a small assembly-oriented microkernel. I/O,
  filesystems, graphics, consoles, and other policy live in modular services
  written predominantly in C.
- The VDC is the primary high-resolution/text display engine.
- The VIC-IIe is a first-class secondary display and timing/sprite engine.
- A stock 128 KiB C128 with 16 KiB VDC RAM is the baseline. A 64 KiB VDC, REU,
  GeoRAM, and model-specific capabilities are optional enhancements.
- PAL and NTSC machines are both targets.

## Toolchain

| Side | C | Assembly and linking |
|---|---|---|
| 8502 | cc65 | ca65 and ld65 |
| Z80 | SDCC | sdasz80/sdld for C-linked code; RASM for standalone assembly |
| Host | host C/Python where useful | GNU Make |

The reference development environment is the `my-distrobox` Distrobox
container, but the build has no intentional dependency on Distrobox.

```sh
distrobox enter my-distrobox
make doctor
make check
make
```

`make doctor` currently expects `cc65`, `ca65`, `ld65`, `sdcc`, `sdasz80`,
`rasm`, and Python 3 on `PATH`. See the [building guide](docs/BUILDING.md) for
the validated reference environment and individual targets.

## Repository layout

```text
abi/                 Cross-CPU contracts and protocol documentation
bench/               Comparable target-side CPU benchmark harness
cfg/                 Linker and memory-layout configurations
docs/                Architecture plan, roadmap, and decisions
include/udeks/        Public C headers shared across CPU builds
mk/                   Make configuration
src/8502/             8502 C and ca65 sources
src/boot/             Native C128 stage-0/stage-1 bootstrap
src/services/         Predominantly C system-service modules
src/z80/              Z80 C, SDAS, and RASM sources
tests/                Host-side tests and future emulator tests
tools/                Deterministic build utilities
```

`make boot` produces a native-autoboot D71 with the 8502 kernel and Z80 worker
at their proposed `$2000` locations. The memory map remains provisional until
the display-memory and physical-hardware gates in ADR 0003 pass.

## Documents

- [Architecture and implementation plan](docs/PLAN.md)
- [Development roadmap](docs/ROADMAP.md)
- [Executive CPU benchmark plan](docs/BENCHMARKS.md)
- [Initial emulator benchmark results](bench/results/2026-09-24-1986-initial.md)
- [Initial emulator interrupt results](bench/results/2026-09-24-1986-irq-latency.md)
- [Initial emulator interrupt-service results](bench/results/2026-09-24-1986-irq-service.md)
- [Initial emulator context-switch results](bench/results/2026-09-24-1986-context.md)
- [Initial emulator kernel-primitives results](bench/results/2026-09-24-1986-kernel.md)
- [Initial emulator bidirectional-handoff results](bench/results/2026-09-24-1986-handoff.md)
- [Initial emulator offload-crossover results](bench/results/2026-09-24-1986-offload.md)
- [`1986` r2 benchmark results](bench/results/1986-7556c23-2026-09-24-r2/README.md)
- [VICE 3.10 r2 benchmark results](bench/results/vice-3.10-2026-09-24-r2/README.md)
- [Native memory-map direct-load smoke test](bench/results/2026-09-24-memory-map-smoke/README.md)
- [Native D71 boot results](bench/results/2026-09-24-native-boot/README.md)
- [VDC console service](docs/VDC-CONSOLE.md)
- [Assembly panic path](docs/PANIC.md)
- [Hardware capability discovery](docs/HARDWARE-CAPABILITIES.md)
- [8502 clock policy](docs/CLOCK.md)
- [Proposed VDC framebuffer/compositor](docs/VDC-FRAMEBUFFER.md)
- [Window system and native console plan](docs/WINDOW-SYSTEM.md)
- [Black-on-yellow visual identity](docs/VISUAL-IDENTITY.md)
- [VDC console qualification](bench/results/2026-09-24-vdc-console/README.md)
- [Service-registry qualification](bench/results/2026-09-24-service-registry/README.md)
- [Assembly panic-path qualification](bench/results/2026-09-24-panic/README.md)
- [Hardware-capability qualification](bench/results/2026-09-24-capabilities/README.md)
- [VDC framebuffer and boot-splash qualification](bench/results/2026-09-24-vdc-framebuffer/README.md)
- [VDC software-font and hardware-panel qualification](bench/results/2026-09-24-vdc-font/README.md)
- [Compact pipe-logo bootsplash qualification](bench/results/2026-09-24-vdc-pipe-logo/README.md)
- [Backed framebuffer API and console-viewport qualification](bench/results/2026-09-24-framebuffer-api/README.md)
- [Reference-style UDEKS bootscreen qualification](bench/results/2026-09-24-reference-bootscreen/README.md)
- [Retained root-console qualification](bench/results/2026-09-24-root-console/README.md)
- [VDC-only 2 MHz qualification and timing](bench/results/2026-09-24-clock-2mhz/README.md)
- [Corrected preserved benchmark PRGs for VICE and hardware](bench/artifacts/2026-09-24-r2/README.md)
- [Building UDEKS](docs/BUILDING.md)
- [Toolchain decision](docs/decisions/0001-toolchain.md)
- [Executive CPU decision](docs/decisions/0002-executive-cpu.md)
- [Proposed native memory and bootstrap contract](docs/decisions/0003-memory-bootstrap.md)
- [Microkernel and service-module decision](docs/decisions/0004-microkernel-modules.md)
- [Root-console and overlapping-window decision](docs/decisions/0005-root-window-and-compositor.md)
- [Mailbox ABI](abi/mailbox.md)
- [Service-module ABI](abi/services.md)
- [Framebuffer client API](abi/framebuffer.md)
- [Retained terminal API](abi/terminal.md)
- [C128 keyboard API](abi/keyboard.md)
- [Dedication](DEDICATION.md)
- [Contributing](CONTRIBUTING.md)
