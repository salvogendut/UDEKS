# Building UDEKS

To build/install a graphical program **without rebuilding the OS**, start with
the [independent app example](GRAPHICAL-APPS-SDK.md). The recipe below builds
the system itself; the example has its own `make graphical-example` target.

## Reference environment

The validated development environment is the Fedora 44 `my-distrobox`
container. As of 2026-09-23 it contains:

| Tool | Validated version/source |
|---|---|
| cc65/ca65/ld65 | Fedora package `cc65-2.19-15.fc44` (`cc65` reports V2.18) |
| SDCC | 4.6.2, revision 16671, from `../sdcc/bin` |
| RASM | 3.2.1 Atlas, build 2026-05-05 |
| GNU Make | 4.4.1 |
| Python | Python 3 supplied by Fedora |

These versions validate the scaffold; they are not yet the pinned release
toolchain. Phase 0 will replace environmental assumptions with checksummed tool
sources or packages.

To install the currently validated 8502 tools in the container:

```sh
distrobox enter my-distrobox
sudo dnf install cc65
```

SDCC and RASM are currently provided through paths shared with the host. A clean
environment bootstrap will be added before the Phase 0 exit gate.

## Targets

```sh
make doctor     # report every required program and fail if one is absent
make check      # host-side unit and utility checks; no target compiler needed
make 8502       # build build/8502/udeks-8502.bin and .prg
make z80        # build build/z80/udeks-z80.bin through SDCC
make z80-asm    # build the independent RASM smoke image
make boot       # build build/boot/udeks.d64 and .d71 for native C128 boot
make publish-boot  # explicitly refresh checked-in build/udeks.d64/.d71 + SHA256SUMS
make panic-probe  # build a non-release D71 that injects descriptor failure
make placement-check  # verify the real linker-map placement budget (reference container)
make task-poll-policy  # cc65 compile-only event-wait reference policy; not linked
make filesystem-policy  # compile the root/suffix resolver also used by the live service
make framebuffer-assets  # pack the 64x64 XPM as a 512-byte VDC bitmap
make user-sources  # compile staged user programs separately from the kernel
make user-programs  # link and package standalone UDEX programs
make bench      # build comparable 8502 and Z80 benchmark payloads
make bench-irq  # build both CIA interrupt-entry probes
make bench-irq-service  # build the three-path interrupt-service suite
make bench-context  # build the task-context save/restore suite
make bench-kernel  # build syscall, event-queue, MMU, CIA, and VDC cases
make bench-handoff  # build bidirectional ownership and mailbox cases
make bench-offload  # build copy/checksum/transform crossover sweep
make            # build all three target images
```

`make user-sources` compiles `user/bin/cowsay.c`, `user/bin/date.c`, the
minimal persistent `user/bin/ush.c`, and the bank-1 task stream runtime under
`build/user/`. The
runtime provides nonblocking `read`, bounded `write`, Unix descriptor numbers,
and Linux errno values through the common task-request gate. `make
user-programs` independently links the transient `cowsay`, `date`, and `ls`
programs for the first loader-owned slot, `ush` at bank-1 `$9000`, and the
managed graphical `xclock` and `xwave` images at bank-0 `$0200` and `$1200`,
wrapping each as UDEX. None resolves private moving kernel symbols; graphical
apps use a fixed managed-app entry table. The same target creates
`build/user/bootfs.img` for the remaining transitional commands and recovery
shell. `make boot` installs the graphical UDEX files as ordinary DOS `XCLOCK.BIN`
and `XWAVE.BIN`, not bootfs entries. The
standalone `date` reads or sets the shared TI-compatible clock, so `xclock`
observes the same time. After stage
1 delivers the services, init asks the common-RAM loader to validate and
install disk `USH.BIN` through system `/bin/ush`, with bootfs recovery. Commands absent from the shell's native table
use the same resolver through its transient entry point. That path swaps the
first task slot, supplies a private C stack and cc65 zero page, runs the
program, and restores the slot on exit. Runtime qualification in both
emulators and on hardware remains required before this milestone is closed.

### Publishing disk images

The repository's downloadable snapshots are `build/udeks.d64` and
`build/udeks.d71`, with provenance in [build/README.md](../build/README.md).
They are deliberately separate from fresh outputs under `build/boot/` so
an experiment or fault-injection build does not silently replace a published
image. Only the two snapshots, their README and SHA256SUMS are tracked;
all other build contents and nested worktrees remain ignored.

After building and qualifying the normal images in my-distrobox:

```sh
make publish-boot
cd build
sha256sum -c SHA256SUMS
```

Update image provenance and link the qualification evidence, then commit the
two disks and checksum file together. `publish-boot` copies the normal build
and generates checksums; it is not itself a hardware/emulator qualification.
Do not publish a `WINDOW_CACHE=0` or other experimental configuration as the
accepted baseline without its own validation. `make clean` removes named
compiler-output directories only; it preserves these published files and
unrelated worktrees/test-run directories. Use an isolated source copy when
you need a completely fresh build without touching ongoing work.

### Root namespace candidate (#26)

The root namespace is merged in main as PR #28. Build from current main, not
an older worktree. Device 8 backs `/`; `/mnt` starts free. `/etc/rc` is `RC.ETC` on disk.
Policy uses bank-1 `$B000-$CFFF`; bootfs is bounded to `$A000-$AFFF`. See
[filesystem contract](../abi/filesystem.md) for limits and the current test image.
Run these VICE checks from the host after the container build:

```sh
python3 tools/root_namespace_probe.py --output build/root-namespace/vice-1541
python3 tools/root_namespace_probe.py --disk build/boot/udeks.d71 --drive 1571 --output build/root-namespace/vice-1571
python3 tools/root_namespace_probe.py --recovery --output build/root-namespace/recovery
python3 tools/startup_probe.py --variant valid --output build/root-namespace/startup-valid
```

Also run startup variants `invalid` and `missing`. For native 1986 input and
window dragging, run `tools/1986_storage_smoke_build.py --root-namespace
--emulator /path/to/1986 --roms /path/to/1986/roms --output build/root-namespace/1986`
inside my-distrobox (SDL3). Probes use disposable disk copies and close their
own sessions. Do not run `make clean` above repository worktrees; use an
isolated source copy for a fresh parallel-build check.

### Development PRG

The 8502 artifacts are a raw resident image and a development PRG that loads
from `$0200` (boot-only capability service in application slot 1, probe page
at `$0B00`, scheduler at `$1200`, boot-only console composer at `$1600`, crt0
at `$1C00`, and the resident kernel at `$2000`) and is entered at `$1C00` with
`SYS 7168`; `--raw-load` in
`tools/vice_capture.py` loads it through the
monitor because the payload starts below the BASIC launcher. Its linker region
ends before the `$D000` I/O aperture. The SDCC
artifact is a fixed 8 KiB raw window covering `$2000`–`$3FFF`; only its leading
bytes currently contain code. `make boot` packages both into a deterministic
D71 and a side-one D64 compatibility image implementing the stage-0/stage-1 path in
[ADR 0003](decisions/0003-memory-bootstrap.md). The direct-load PRG remains
useful for focused bring-up tests. Use `build/boot/udeks.d64` with Pi1541 and
other drives that do not boot D71 images; its boot payload is identical to the
one in `build/boot/udeks.d71`.

`make panic-probe` builds `build/boot/udeks-panic-probe.d71`. Its console
descriptor deliberately has invalid magic so the complete registry-to-panic
path can be tested. See the [panic-path contract](PANIC.md); never use this
fixture as a normal system disk.

The production boot image starts hardware capability discovery before the VDC
console. Its [capability contract](HARDWARE-CAPABILITIES.md) records PAL/NTSC,
VDC revision and RAM tier, and expansion presence for later service policy.
`make framebuffer-assets` deterministically converts the two-colour project
artwork into row-major, MSB-first scanlines under `build/assets/`; the target
kernel will consume those bytes without carrying an image decoder.

The current transitional production image starts eleven statically linked
modules in order: hardware capability discovery, CIA time, the bounded Z80
worker, the VDC text console,
the raster-paced pointer source, the passive VIC-IIe graphics service, the
window manager, the polled keyboard source, the fixed-focus root-terminal
editor, the managed-app dispatcher, and init. Init polls the persistent
`/bin/ush` task plus the resident compatibility shell; `xclock` and `xwave`
themselves are no longer resident modules. Static placement is a bootstrap detail: each entry has a separate
descriptor and lifecycle, and the display module does not drive window or
application policy. The image stays at
1 MHz, leaving the VIC-IIe active for the future graphics/second-display
service. The previously qualified VDC-only 2 MHz transition and VDC
framebuffer remain optional modules.

The worker boot self-test completes a real `8502 -> Z80 -> 8502` `NOP`
transaction through the ABI 0.3 mailbox. `z80ctl status` reports the common-RAM
diagnostics and `z80ctl test` requests another bounded lease. The Z80 runs at
stock timing; no optional doubled/8 MHz emulator mode is used. See the
[worker contract](../abi/z80-worker.md).

`xinit` activates the [VIC-IIe graphics service](../abi/vic-graphics.md): a
yellow 320x200 bank-1 bitmap with a centered black X pointer; `xinit -q`
terminates that display session. Neither transition replaces or suspends the
VDC console. The compact X pointer accepts a proportional 1351 mouse on control
port 1 and a digital joystick on control port 2. During a repaint or Z80 lease,
its 63 sprite bytes are temporarily replaced by the pipe asset as a busy
indication; nested Z80 work cannot clear a repaint-owned indication. A
non-blocking three-frame release delay makes brief work visible without
stalling the executive. Mouse positions are consumed by a two-phase raster IRQ,
so compositor and Z80 latency cannot reverse or lose modulo-64 motion. `xclock`
starts the first
managed analog-clock window. `xwave` opens another managed window and uses
bounded Z80 sinc-surface leases while the 8502 projects and plots a connected
two-axis isometric mesh on the VIC-IIe. A command
without `&` owns the foreground and accepts `Ctrl+C`; `xclock &` or `xwave &`
returns the prompt immediately. Moving or resizing hides window contents and
transfers only an outline until release. See the
[`window-manager contract`](../abi/window.md) and
[`xclock` design and status](XCLOCK.md) and the
[`xwave` dual-engine plotter](XWAVE.md), followed by the GEOBENCH-XAOS-inspired
[`xmandel` viewer](XMANDEL.md).

Window Manager 0.3 supports four overlapping, movable, resizable bitmap windows. Clicking an
exposed area raises and focuses that window; moving or closing one recomposes
only the bounding damage region from back to front. The current modules remain
statically linked into one bootstrap kernel payload even though each has an
independent descriptor and lifecycle. Disk-loadable modules require the later
allocator, filesystem, and executable loader milestones.

The two initial graphical applications are emitted as ordinary disk UDEX files
and loaded on first invocation (after `mount 8 /mnt`) into fixed, retained low-memory slots at
`$0200-$0BFF` and `$1200-$1BFF`. This removes their code and state from the
resident `$2000` kernel range while keeping lifecycle polling bounded. These
fixed slots are transitional rather than general process address spaces. New
programs live in `user/` and target the
[UDEX executable format](../abi/executable.md).
Their kernel-facing calls use the fixed
[8502 syscall and entry ABI](../abi/syscalls.md).

The text console displays the compact UDEKS pipe and Japanese wordmark in a
left rail and a bordered 64x21 root terminal to the right. A bordered
`RUNNING` panel in the lower rail tracks active `xinit`, `xclock`, and `xwave`
lifecycle states without redrawing when the set is unchanged. Build tooling
packs the artwork and six line-drawing shapes into 63 deduplicated upper-half
VDC glyphs, leaving the stock lower character set intact. Ordinary output
writes character cells, dirty edits transfer only changed spans, and the
insertion point uses the hardware cursor. Screen clearing uses VDC block fill.
The console contains identity, version, truthful hardware/service states, a
welcome line, and the interactive prompt described in
`docs/WINDOW-SYSTEM.md`.

The retained model now implements the provisional
[terminal API](../abi/terminal.md): sequential output, control characters,
wrapping, scrolling, cursor damage, and direct text-cell refresh. It
is paired with the complete 11-column polled
[C128 keyboard service](../abi/keyboard.md), including normalized press/release
events and a bounded FIFO. The provisional
[root-terminal editor](../abi/line-editor.md) supports bounded insertion,
Backspace, horizontal cursor motion, submission, and prompt renewal. The native
shell provides bounded command dispatch and Unix-like streams. Up/Down browse
six volatile history entries and preserve the current draft; completion is
not implemented yet.

The optional framebuffer owns a 16,000-byte system-RAM backing surface. Client changes
are clipped, accumulated as byte spans per scanline, copied through the bounded
assembly VDC transport, and retired only after the complete span is accepted.
The cold-boot image is composed in RAM and uploaded as one hidden full-surface
transaction before bitmap mode is revealed; only the splash sample is read
back on the production path. The initial
single-client lease exposes pixel, horizontal-line, filled-rectangle, glyph,
string, and flush operations from `include/udeks/framebuffer.h`.

The resident 8502 image links the small subset of cc65's `none` runtime needed
by its C services. Startup initializes cc65's downward-growing software stack
at `$EFF0`; the 6502 hardware stack remains on physical bank-0 page one. The
Z80 worker uses the reserved common-RAM stack `$F2B0-$F2FF` (SP `$F300`) so
its suspended frames survive persistent bank-1 task polls and MMU profile
changes between bounded leases. The
first display service is the [VDC console](VDC-CONSOLE.md), with bounded assembly port
access and C display policy. It is discovered and started through the
[service-module ABI](../abi/services.md); the kernel calls the generic registry,
not a console-specific symbol.

`tools/ihx_to_bin.py` performs strict Intel HEX checksum validation and rejects
addresses outside the declared output window. This avoids silently creating an
unexpectedly large or truncated Z80 payload.

The benchmark target creates `build/bench/8502/bench-8502.bin` and
`build/bench/z80/bench-z80.bin`. See the [benchmark harness](../bench/README.md)
for its provisional memory contract and result decoder.

The interrupt target creates PRG-wrapped 8502 native-vector and Z80 IM1 probes
under `build/bench/irq/`. See the [interrupt probe notes](../bench/irq/README.md)
for entry addresses, the result contract, and the snapshot decoder.

The service-cost target creates corresponding artifacts under
`build/bench/irq-service/`. Its [measurement contract](../bench/irq-service/README.md)
defines the minimal, kernel-tick, and jump-table-dispatch paths.

The context target creates its artifacts under `build/bench/context/`. Its
[context contract](../bench/context/README.md) records exactly which CPU and
compiler-runtime state is transferred by each variant.

The kernel-primitives target builds under `build/bench/kernel/`. See its
[suite contract](../bench/kernel/README.md) for the shared-C and assembly case
boundaries.

The handoff target builds a single dual-CPU PRG under `build/bench/handoff/`.
Its [suite contract](../bench/handoff/README.md) defines both ownership
directions, the mailbox validation path, and the `HNDF` result block.

The offload target builds a single dual-CPU PRG under `build/bench/offload/`.
Its [suite contract](../bench/offload/README.md) defines the local/delegated
timing boundaries, buffer validation, and `XOFS` result block.

Published benchmark inputs are copied to a dated directory under
[`bench/artifacts`](../bench/artifacts/). These checked-in PRGs are immutable
comparison inputs for VICE and real hardware; a changed harness gets a new
dated bundle rather than replacing an old binary.

## Tool boundaries

The 8502 side uses one relocatable object ecosystem: cc65 emits ca65 input,
ca65 creates objects, and ld65 places them according to
`cfg/8502-bootstrap.cfg`.

The Z80 side has two intentionally separate paths:

- SDCC C and assembly linked into the same image use SDCC's `sdasz80` object
  format and linker.
- RASM builds standalone images. A RASM image and an SDCC image meet only at a
  documented binary/jump-table boundary.

Do not attempt to feed SDCC `.rel` files to RASM.

## Emulator plan

Task Request ABI 0.4 input waits have a dedicated compiled-C qualification
task. Build the disks in the reference container, then run the host VICE probe:

```sh
distrobox enter my-distrobox -- make -j8 boot build/boot/udeks-task-poll-probe.d71
python3 tools/task_poll_probe.py
python3 tools/task_poll_probe.py --disk build/boot/udeks-task-poll-probe.d64
python3 tools/task_yield_probe.py
python3 tools/task_yield_probe.py --disk build/boot/udeks.d64
```

`make task-poll-probe` wraps building/running both formats when the toolchain
and Flatpak are available in the same environment. `task_cancel_probe.py
--input-wait` reuses the cancellation probe with a blocked INPUT subscription.
The compiled probe preserves local stack arrays across finite/infinite and
stopped waits. Additional monitor-seeded subscriptions qualify wake scanning,
not extra task allocation. Line injection selects bank 0 and preserves the
paused CPU's live MMU profile, including during VIC/Z80 activity.

The local `../1986` C128DCR emulator is the primary integration target. VICE
3.10 is installed as Flatpak `net.sf.VICE`; it supplies `x128` and `c1541` as
the independent behavior oracle and disk-image tool. `tools/vice_capture.py`
loads preserved PRGs, selects native 1/2 MHz mode when requested, waits for the
result-state byte, and saves a raw decoder-ready block. It uses a temporary
BASIC wrapper for pure machine-code PRGs without changing their payload bytes
or addresses. See the [r2 VICE results](../bench/results/vice-3.10-2026-09-24-r2/README.md)
for a complete command. `tools/shadow_boot_probe.py --vic-compare` boots the
native D71 with tail sentinels patched into the payload, proves the `crt0`
VIC-shadow clear, and compares the drawn bank-0 shadow with the bank-1 bitmap;
`make shadow-probe` wraps it and the result is preserved in
`bench/results/2026-09-26-shadow-clear`. Real-hardware verification still gates
MMU, timing, video, IEC, and CPU-handoff milestones.

For native disk tests, `tools/vice_capture.py --native-disk` attaches the D71
at power-on instead of injecting a BASIC launcher. `1986` saves complete VSF
snapshots. `tools/snapshot_extract.py` extracts a
compact decoder-ready address range from those snapshots, for example:

```sh
python3 tools/snapshot_extract.py run.vsf result.bin \
  --address 0xf180 --size 320
```

Pass `--screenshot output.bmp` to `tools/vice_capture.py` to capture the active
VICE canvas after the requested result record reaches its completed state. A
small `--screenshot-delay` lets a newly activated display complete a raster
refresh before capture. Native interactive tests can wait for an exact
common-RAM readiness signature with `--keybuf-ready-block ADDRESS=HEXBYTES`,
then inject an entire line-editor record atomically with
`--ready-block ADDRESS=HEXBYTES`.

For disk-loaded 2 MHz runs, issue BASIC `FAST` immediately before `RUN` or
`SYS`; in the qualified launch path, the emulator's `--fast` startup option
alone did not leave the benchmark in 2 MHz mode. IRQ qualification also stops
the otherwise unused CIA1 Timer B and reads CIA1 ICR before entering the
preserved PRG. The exact commands and rationale are in the
[`1986` r2 report](../bench/results/1986-7556c23-2026-09-24-r2/README.md).
