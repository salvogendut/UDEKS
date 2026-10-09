# UDEKS documentation

Start with the current roadmap and public contracts. Implementation notes and
preserved benchmark records describe specific checkpoints; their old paths,
addresses or status claims do not override the current source and ABI.

## Start here

- [Roadmap](ROADMAP.md) — accepted features, limits and next priorities
- [Scheduled console applications](NATIVE-CONSOLE-APPS.md) — completed #52 / PR #53: foreground input, background jobs, native files and scheduled cat
- [Writable root and file commands](ROADMAP.md#current-baseline) — merged baseline (#47 / PR #48)
- [Create-only disk writes](STORAGE-0.3.md) — merged baseline (#44 / PR #45)
- [Generic graphical-app plan](GENERIC-GRAPHICS-APPS.md) — merged baseline (#35)
- [Independent apps SDK](GRAPHICAL-APPS-SDK.md) — console C commands and foreground/background graphical apps
- [D81 / 1581 image](D81.md) — third build format, filesystem support and tests
- [Architecture plan](PLAN.md) — the intended system and microkernel boundary
- [Building and publishing](BUILDING.md) — toolchain, targets and disk snapshots
- [Downloadable boot images](../build/README.md) — provenance, checksums and boot instructions
- [Boot and root-namespace workflow](BOOT-STARTUP.md#root-namespace-candidate-26)
- [Dedication](../DEDICATION.md) · [Contributing](../CONTRIBUTING.md)

## Current interfaces

These describe byte layouts and bounded public contracts, not full POSIX
compatibility. Some documents retain historical implementation sections.

- [Mailbox ABI](../abi/mailbox.md)
- [Task lifecycle ABI](../abi/tasks.md)
- [UDEX executable format](../abi/executable.md)
- [Read-only boot filesystem format](../abi/bootfs.md)
- [Filesystem and Unix-like command direction](../abi/filesystem.md)
- [8502 syscall and program-entry ABI](../abi/syscalls.md)
- [Bank-1 8502 cooperative-task gate](../abi/task-bank.md)
- [Bank-task request and stream ABI](../abi/task-request.md)
- [Bounded Z80 worker service](../abi/z80-worker.md)
- [VIC-IIe graphics service](../abi/vic-graphics.md)
- [VIC-IIe window manager](../abi/window.md)
- [Pointer input service](../abi/pointer-input.md)
- [CIA time service](../abi/time.md)
- [Service-module ABI](../abi/services.md)
- [Framebuffer client API](../abi/framebuffer.md)
- [Retained terminal API](../abi/terminal.md)
- [C128 keyboard API](../abi/keyboard.md)
- [Root-terminal line editor API](../abi/line-editor.md)
- [Native shell contract](../abi/shell.md)
- [Standard stream interface](../include/udeks/stream.h)

## Architecture decisions

- [Toolchain decision](decisions/0001-toolchain.md)
- [Executive CPU decision](decisions/0002-executive-cpu.md)
- [Proposed native memory and bootstrap contract](decisions/0003-memory-bootstrap.md)
- [Microkernel and service-module decision](decisions/0004-microkernel-modules.md)
- [Root-console and overlapping-window decision](decisions/0005-root-window-and-compositor.md)
- [Text-console and 1 MHz boot decision](decisions/0006-text-console-default.md)
- [Resident core and loadable service decision](decisions/0007-resident-core-and-loadable-services.md)
- [Context-switch placement decision](decisions/0008-context-switch-placement.md)
- [Boot-only capability relocation decision](decisions/0009-boot-only-capability-relocation.md)
- [Boot-console relocation decision](decisions/0010-boot-console-relocation.md)
- [Boot-delivery shadow-execution decision](decisions/0011-boot-delivery-shadow-execution.md)
- [Scheduler secondary-payload delivery](decisions/0012-scheduler-secondary-payload.md)

## Services, applications and implementation notes

The current filesystem routes are `/`, `/bin`, `/etc`, and optional `/mnt`.
In older notes, commands loaded from `/mnt` and binaries lacked suffixes.
Use the [filesystem contract](../abi/filesystem.md) for the current behavior.

- [Disk shell and startup](BOOT-STARTUP.md)
- [Disk-loaded graphical apps](DISK-GRAPHICS.md)
- [`xsprdef` session sprite editor](XSPRDEF.md)
- [Command extraction](COMMAND-EXTRACTION.md)
- [Retained-window cache integration](WINDOW-CACHE-INTEGRATION.md)
- [Window-manager milestone](WINDOW-MANAGER-MILESTONE.md)
- [Event waits](EVENT-WAITS.md)
- [Boot staging map](BOOT-STAGING-MAP.md)

<details>
<summary>More subsystem and application notes</summary>

- [Scheduler placement spike](SCHEDULER-PLACEMENT.md)
- [VDC console service](VDC-CONSOLE.md)
- [Assembly panic path](PANIC.md)
- [Hardware capability discovery](HARDWARE-CAPABILITIES.md)
- [8502 clock policy](CLOCK.md)
- [Proposed VDC framebuffer/compositor](VDC-FRAMEBUFFER.md)
- [Window system and native console plan](WINDOW-SYSTEM.md)
- [Black-on-yellow visual identity](VISUAL-IDENTITY.md)
- [`date` and the shared C128 clock](DATE.md)
- [`xclock` analog clock application](XCLOCK.md)
- [`xwave` dual-engine graphics demo](XWAVE.md)
- [`cowsay` first user-program port](COWSAY.md)
- [`/bin/ush` user-shell migration](USH.md)
- [Planned `xmandel` dual-engine Mandelbrot viewer](XMANDEL.md)
- [Read-only storage bring-up](STORAGE-0.1.md)
- [Disk-execution bring-up](STORAGE-0.2.md)
- [Graphics primitive services](GRAPHICS-PRIMITIVES.md)
- [Bounded repaint replay](BOUNDED-REPLAY.md)
- [Graphics cache placement](GRAPHICS-CACHE-PLACEMENT.md)
- [Cache qualification](WINDOW-CACHE-ACCEPTANCE.md)
- [Engineering handover](../HANDOVER.md) — detailed checkpoint history, not the priority list

</details>

## Qualification and history

- [Current root-namespace evidence](../bench/results/2026-09-30-root-namespace/README.md)
  and [exact accepted artifacts](../bench/artifacts/2026-09-30-root-namespace/README.md)
- [Command-release evidence](../bench/results/2026-09-30-command-release/README.md)
- [Benchmark plan](BENCHMARKS.md)
- [All preserved results](../bench/results/) · [All preserved artifacts](../bench/artifacts/)

<details>
<summary>Early CPU, boot, display and framebuffer experiments</summary>

These records establish provenance and explain earlier decisions. In particular,
bitmap-console experiments are not the current character-mode VDC console.
No historical evidence has been deleted or renamed.

- [Initial emulator benchmark results](../bench/results/2026-09-24-1986-initial.md)
- [Initial emulator interrupt results](../bench/results/2026-09-24-1986-irq-latency.md)
- [Initial emulator interrupt-service results](../bench/results/2026-09-24-1986-irq-service.md)
- [Initial emulator context-switch results](../bench/results/2026-09-24-1986-context.md)
- [Initial emulator kernel-primitives results](../bench/results/2026-09-24-1986-kernel.md)
- [Initial emulator bidirectional-handoff results](../bench/results/2026-09-24-1986-handoff.md)
- [Initial emulator offload-crossover results](../bench/results/2026-09-24-1986-offload.md)
- [`1986` r2 benchmark results](../bench/results/1986-7556c23-2026-09-24-r2/README.md)
- [VICE 3.10 r2 benchmark results](../bench/results/vice-3.10-2026-09-24-r2/README.md)
- [Native memory-map direct-load smoke test](../bench/results/2026-09-24-memory-map-smoke/README.md)
- [Native D71 boot results](../bench/results/2026-09-24-native-boot/README.md)
- [VDC console qualification](../bench/results/2026-09-24-vdc-console/README.md)
- [Service-registry qualification](../bench/results/2026-09-24-service-registry/README.md)
- [Assembly panic-path qualification](../bench/results/2026-09-24-panic/README.md)
- [Hardware-capability qualification](../bench/results/2026-09-24-capabilities/README.md)
- [VDC framebuffer and boot-splash qualification](../bench/results/2026-09-24-vdc-framebuffer/README.md)
- [VDC software-font and hardware-panel qualification](../bench/results/2026-09-24-vdc-font/README.md)
- [Compact pipe-logo bootsplash qualification](../bench/results/2026-09-24-vdc-pipe-logo/README.md)
- [Backed framebuffer API and console-viewport qualification](../bench/results/2026-09-24-framebuffer-api/README.md)
- [Reference-style UDEKS bootscreen qualification](../bench/results/2026-09-24-reference-bootscreen/README.md)
- [Retained root-console qualification](../bench/results/2026-09-24-root-console/README.md)
- [VDC-only 2 MHz qualification and timing](../bench/results/2026-09-24-clock-2mhz/README.md)
- [Corrected preserved benchmark PRGs for VICE and hardware](../bench/artifacts/2026-09-24-r2/README.md)

</details>
