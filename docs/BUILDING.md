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
make 8502       # build build/8502/udeks-8502.bin
make z80        # build build/z80/udeks-z80.bin through SDCC
make z80-asm    # build the independent RASM smoke image
make bench      # build comparable 8502 and Z80 benchmark payloads
make bench-irq  # build both CIA interrupt-entry probes
make bench-irq-service  # build the three-path interrupt-service suite
make bench-context  # build the task-context save/restore suite
make bench-kernel  # build syscall, event-queue, MMU, CIA, and VDC cases
make bench-handoff  # build bidirectional ownership and mailbox cases
make bench-offload  # build copy/checksum/transform crossover sweep
make            # build all three target images
```

The 8502 artifact is a 97-byte raw bring-up image linked at `$2000`. The SDCC
artifact is a fixed 8 KiB raw window covering `$2000`–`$3FFF`; only its leading
bytes currently contain code. Neither is bootable yet.

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
`x128sc` and `c1541` are planned as an independent behavior oracle and disk
image tool. Real-hardware verification gates MMU, timing, video, IEC, and
CPU-handoff milestones.
