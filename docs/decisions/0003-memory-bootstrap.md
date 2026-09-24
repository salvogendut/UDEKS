# ADR 0003: Native memory map and bootstrap contract

- Status: proposed
- Date: 2026-09-24

## Context

ADR 0002 selects an 8502 resident executive and a bounded Z80 worker. The
current scaffolding links both payloads at `$2000`, assumes that some earlier
environment selected usable RAM, and places the mailbox at `$F000`. Kernel work
cannot safely proceed until those coincidences become an explicit physical-bank,
MMU, and loader contract.

The C128 MMU provides two 64 KiB RAM banks, four preconfigured memory maps,
independently relocated page zero and page one, and 1/4/8/16 KiB common areas at
the bottom, top, or both. Common RAM is physically in bank 0. MMU locations
`$FF00-$FF04` remain registers in every native-mode map, even when the `$D000`
I/O window is hidden.

Bottom common RAM would override relocated page-zero and page-one pointers, so
it conflicts with the planned task-context model. A top common area preserves
relocatable task pages while keeping handoff code, vectors, and IPC visible
across bank changes.

## Proposed decision

Use RAM bank 0 for the 8502 executive, RAM bank 1 for the Z80 worker and initial
task/data space, and bank-0 `$F000-$FFFF` as a 4 KiB top common area.

The four MMU preconfiguration registers have fixed roles:

| Profile | CR | RAM bank | `$D000-$DFFF` | Use |
|---|---:|---:|---|---|
| kernel I/O | `$3E` | 0 | I/O | Normal executive and drivers |
| kernel flat | `$3F` | 0 | RAM | Controlled access to RAM below I/O |
| worker I/O | `$7E` | 1 | I/O | Z80 worker when device access is admitted |
| worker flat | `$7F` | 1 | RAM | Z80 and bank-1 bulk-memory work |

`$D506` initially contains `$09`: 4 KiB common at the top, no bottom common,
and VIC RAM bank 0. The display service may set bit 6 later to point the VIC at
its reserved bank-1 window without changing the common-area bits.

The initial physical allocation is:

| Logical range | Bank 0 | Bank 1 / non-common view |
|---|---|---|
| `$0000-$01FF` | Initial executive zero page and stack | Relocatable task-page pool |
| `$0200-$0AFF` | Boot-preloaded application slot 1 | Task/worker low workspace |
| `$0B00-$0BFF` | Application slot 1 after stage 0 exits | Task/worker space |
| `$0C00-$11FF` | Reclaimed root-console state after stage 1 exits | Task/worker space |
| `$1200-$1BFF` | Boot-preloaded application slot 2 | Task/worker space |
| `$1C00-$1FFF` | Stage-1 loader | Task/worker space |
| `$2000-$3FFF` | 8502 kernel image | Resident Z80 dispatcher and code |
| `$4000-$7FFF` | 8502 kernel image | Reserved 16 KiB VIC-visible window |
| `$8000-$CFFF` | 8502 kernel image | Application, worker, and transfer data |
| `$D000-$DFFF` | I/O normally; bank-0 RAM in flat profile | I/O or bank-1 RAM by profile |
| `$E000-$E18F` | VIC-IIe module scanline-offset table | Worker data |
| `$E190-$E1AF` | VIC-IIe module dirty-page map | Worker data |
| `$E1B0-$E1B7` | VIC-IIe module clip state | Worker data |
| `$E1B8-$E2FF` | Statically linked module-private high BSS | Worker data |
| `$E300-$EFFF` | 8502 C software stack | Worker data and stack |
| `$F000-$FFFF` | 4 KiB common RAM | Bank-0 common RAM replaces bank 1 |

The bank-0 kernel linker range is `$2000-$CFFF`; it cannot grow into I/O or
common RAM. The first high-memory assignment gives `$E000-$E1B7` to the
VIC-IIe module's scanline table, dirty-page map, and clip state, and reserves
`$E1B8-$E2FF` for bounded module-private BSS, and `$E300-$EFF0` for the
downward-growing 8502 C software stack. The initial Z80
stack top is `$EFF0` in its non-common bank view.

Stage 1 transfers control from `$1C00-$1FFF` and never returns. Before doing
so it installs two 2560-byte application images from bank-0 staging ranges
`$D400-$DDFF` and `$E600-$EFFF` into `$0200-$0BFF` and `$1200-$1BFF`.
The kernel reclaims the adjacent `$0C00-$11FF` bootstrap/KERNAL workspace as a linker-
bounded `LOWBSS` segment. The retained root-console module owns its initial
allocation there and explicitly initializes every byte in
`udeks_root_console_reset()` before the renderer or terminal can observe it.

The common area is partitioned conservatively:

| Range | Contract |
|---|---|
| `$F000-$F03F` | Mailbox ABI 0.2 |
| `$F040-$F06F` | Native boot-chain diagnostics |
| `$F070-$F087` | VDC console diagnostics |
| `$F088-$F08F` | Reserved diagnostic alignment gap |
| `$F090-$F0A7` | Service-registry diagnostics |
| `$F0A8-$F0AF` | Reserved diagnostic alignment gap |
| `$F0B0-$F0BF` | Panic diagnostics |
| `$F0C0-$F0DF` | Hardware-capability diagnostics |
| `$F0E0-$F0FF` | VDC framebuffer diagnostics |
| `$F100-$F10F` | 8502 clock-policy diagnostics |
| `$F110-$F11F` | Reserved diagnostic alignment gap |
| `$F120-$F14F` | C128 keyboard diagnostics |
| `$F150-$F16F` | Root-terminal line-editor diagnostics |
| `$F170-$F18F` | Shell diagnostics and foreground-job state |
| `$F190-$F27F` | Worker, graphics, pointer, time, window, and application diagnostics |
| `$F280-$F2FF` | Reserved diagnostic space |
| `$F300-$F33F` | Bounded Z80/8502 wave-sample buffer |
| `$F340-$F7FF` | Future queues, job descriptors, and shared transfer metadata |
| `$F800-$FEFF` | 8502/Z80 gateway code and common kernel mechanisms |
| `$FF00-$FF04` | Permanent MMU register hole; never RAM or code |
| `$FF05-$FFCF` | Common gateway state/code, to be allocated explicitly |
| `$FFD0-$FFF9` | CPU handoff and interrupt/NMI trampolines |
| `$FFFA-$FFFF` | 8502 NMI, reset, and IRQ vectors |

No common-code linker segment may cross the `$FF00-$FF04` register hole.

## Bootstrap contract

The native disk path uses two small stages before the resident kernel:

1. The standard C128 ROM reset path transfers initial ownership from the Z80
   reset BIOS to the 8502 and reads an autoboot sector into `$0B00`.
2. Stage 0 uses the documented C128 `CBM` boot-sector format to load the UDEKS
   stage-1 image into bank 0 at `$1C00` and transfers control to it.
3. Stage 1 runs with interrupts disabled, verifies a native C128 with at least
   two 64 KiB RAM banks, loads/copies the 8502 image to bank-0 `$2000`, installs
   the Z80 image at bank-1 `$2000`, and installs common gateways and vectors.
4. Stage 1 selects the kernel-I/O profile, 4 KiB top common RAM, and physical
   bank-0 pages zero/one, then jumps to the 8502 entry at `$2000`.
5. The 8502 entry repeats the safe MMU/profile initialization idempotently,
   clears BSS, initializes the mailbox, and enters C. No BASIC or KERNAL service
   is part of the resident-kernel ABI after that point.
6. Service startup discovers video timing and remains at the inherited 1 MHz
   rate, allowing the VDC text console and VIC-IIe to stay active together.
   The qualified VDC-only 2 MHz transition is an optional later policy.

For development, `udeks-8502.prg` may be loaded directly at `$2000` and entered
with `SYS 8192`. This bypasses disk stages 0 and 1 but must satisfy the same
bank-0 placement contract.

## Validation required for acceptance

- [x] Linker and host tests enforce the bank-0 kernel limit and MMU constants.
- [x] A direct-load smoke image reaches C with the expected MMU readback and
  mailbox signature in both `1986` and VICE.
- [x] Bank switching through all four profiles leaves common signatures and the
  `$FF00-$FF04` hole behaving as specified.
- [x] Page-zero/page-one relocation works with top common enabled and is shown not
  to alias bank-0 pages accidentally.
- [x] A D71 autoboot image executes stage 0 at `$0B00`, stage 1 at `$1C00`, and the
  kernel at `$2000` without a BASIC command.
- [ ] VIC bank-1 selection and VDC-only 2 MHz operation do not corrupt either CPU
  image or common RAM.
- [ ] At least one physical C128 completes the bootstrap and map probe.

The preserved [direct-load smoke results](../../bench/results/2026-09-24-memory-map-smoke/README.md)
record the initial entry state. The subsequent
[profile and relocation results](../../bench/results/2026-09-24-memory-map-profiles/README.md)
record identical 23/23 passes in `1986` and VICE. The
[native D71 results](../../bench/results/2026-09-24-native-boot/README.md)
record the complete stage-0/stage-1/kernel path and verified Z80 installation.
The display-memory and physical-machine gates keep this ADR proposed.

## Consequences while proposed

- Kernel, worker, common-gateway, and bootstrap images require distinct linker
  regions even where they share a logical address.
- The `$F000` mailbox remains compatible with the qualified benchmark ABI.
- Relocatable task zero pages/stacks remain possible because bottom common RAM
  is disabled.
- Bank-1 capacity is deliberately traded for a fixed VIC window and resident
  Z80 image; later allocators may reclaim unused portions but cannot overlap an
  active display or worker lease.
- Addresses in this ADR are not ABI 1.0 until the validation list passes.

## Sources

- [Commodore 128 Programmer's Reference Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf), chapters 13 and 16.
- [`1986` Z80 initialization and handoff notes](https://github.com/salvogendut/1986/blob/7556c2357506dc576ab7ab0783f9971892db1450/docs/Z80-CPM.md)
- [ADR 0002](0002-executive-cpu.md)
