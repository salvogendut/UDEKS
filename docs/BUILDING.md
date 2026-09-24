# Building UDEKS

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
make boot       # build build/boot/udeks.d71 for native C128 autoboot
make panic-probe  # build a non-release D71 that injects descriptor failure
make framebuffer-assets  # pack the 64x64 XPM as a 512-byte VDC bitmap
make bench      # build comparable 8502 and Z80 benchmark payloads
make bench-irq  # build both CIA interrupt-entry probes
make bench-irq-service  # build the three-path interrupt-service suite
make bench-context  # build the task-context save/restore suite
make bench-kernel  # build syscall, event-queue, MMU, CIA, and VDC cases
make bench-handoff  # build bidirectional ownership and mailbox cases
make bench-offload  # build copy/checksum/transform crossover sweep
make            # build all three target images
```

The 8502 artifacts are a raw resident image and a development PRG linked/loaded
at `$2000`. Its linker region ends before the `$D000` I/O aperture. The SDCC
artifact is a fixed 8 KiB raw window covering `$2000`–`$3FFF`; only its leading
bytes currently contain code. `make boot` packages both into a deterministic
D71 implementing the stage-0/stage-1 path in
[ADR 0003](decisions/0003-memory-bootstrap.md). The direct-load PRG remains
useful for focused bring-up tests.

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

The current production image starts three services in order: hardware
capability discovery, the qualified text-mode fallback, and the baseline VDC
framebuffer. The framebuffer takes final display ownership, enters 640x200
monochrome bitmap mode, and shows the compact UDEKS pipe at the upper left in
the default black-on-yellow theme. Following `assets/bootscreen.png`, it uses
the original UDEKS 5x7 software font to render a nearly full-height bordered
boot console to the logo's right. The console contains identity, version,
truthful hardware and service states, aligned status fields, a welcome line,
and a static future-shell prompt and cursor.

The framebuffer owns a 16,000-byte system-RAM backing surface. Client changes
are clipped, accumulated as byte spans per scanline, copied through the bounded
VDC transport, and read back before the dirty span is retired. The initial
single-client lease exposes pixel, horizontal-line, filled-rectangle, glyph,
string, and flush operations from `include/udeks/framebuffer.h`.

The resident 8502 image links the small subset of cc65's `none` runtime needed
by its C services. Startup initializes cc65's downward-growing software stack
at `$EFF0`; the 6502 hardware stack remains on physical bank-0 page one. The
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

The local `../1986` C128DCR emulator is the primary integration target. VICE
3.10 is installed as Flatpak `net.sf.VICE`; it supplies `x128` and `c1541` as
the independent behavior oracle and disk-image tool. `tools/vice_capture.py`
loads preserved PRGs, selects native 1/2 MHz mode when requested, waits for the
result-state byte, and saves a raw decoder-ready block. It uses a temporary
BASIC wrapper for pure machine-code PRGs without changing their payload bytes
or addresses. See the [r2 VICE results](../bench/results/vice-3.10-2026-09-24-r2/README.md)
for a complete command. Real-hardware verification still gates MMU, timing,
video, IEC, and CPU-handoff milestones.

For native disk tests, `tools/vice_capture.py --native-disk` attaches the D71
at power-on instead of injecting a BASIC launcher. `1986` saves complete VSF
snapshots. `tools/snapshot_extract.py` extracts a
compact decoder-ready address range from those snapshots, for example:

```sh
python3 tools/snapshot_extract.py run.vsf result.bin \
  --address 0xf180 --size 320
```

Pass `--screenshot output.bmp` to `tools/vice_capture.py` to capture the active
VICE canvas after the requested result record reaches its completed state.

For disk-loaded 2 MHz runs, issue BASIC `FAST` immediately before `RUN` or
`SYS`; in the qualified launch path, the emulator's `--fast` startup option
alone did not leave the benchmark in 2 MHz mode. IRQ qualification also stops
the otherwise unused CIA1 Timer B and reads CIA1 ICR before entering the
preserved PRG. The exact commands and rationale are in the
[`1986` r2 report](../bench/results/1986-7556c23-2026-09-24-r2/README.md).
