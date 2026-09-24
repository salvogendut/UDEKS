# `1986` benchmark results — r2

These results use the exact PRGs in
`bench/artifacts/2026-09-24-r2/` and `1986` commit
`7556c2357506dc576ab7ab0783f9971892db1450`. The emulator ran with PAL
timing, the 80-column display selected, 64 KiB VDC RAM, and
`bench/handoff/1986-stock.conf`. That configuration explicitly sets
`double_z80_frequency = 0` and `tinker = 0`, selecting the stock effective
2 MHz Z80 timing rather than the optional doubled-frequency mode.

All 19 canonical result blocks pass their strict decoder. The interrupt-service
and offload cases were repeated three times per configuration; every repeat is
byte-identical. Canonical blocks are in `raw/`, repeats are in `repeats/`, and
each directory has a SHA-256 manifest.

## Main result

The corrected `1986` run agrees with VICE 3.10 on the executive-level split:

- stock Z80 wins the substantive shared-C workloads, compiler context, full
  context, and compiled switch/table dispatch;
- the 2 MHz 8502 wins CPU-core context, event-queue traffic, MMU/CIA/VDC
  transactions, IRQ entry, and every measured IRQ-service path;
- CPU handoff is expensive enough to require batching;
- a 2 MHz 8502 executive gains nothing by delegating the three handwritten
  offload kernels to the Z80 through 2 KiB.

Selected results, in one-megahertz CIA ticks, show the agreement directly:

| Measurement | `1986` 8502 | `1986` Z80 | VICE 8502 | VICE Z80 |
|---|---:|---:|---:|---:|
| IRQ entry median | 48 | 106.5 | 20 | 77.5 |
| Minimal IRQ service median | 144 | 500 | 149 | 527.5 |
| Kernel-tick IRQ service median | 154 | 549 | 162 | 556.5 |
| Compiler context operation | 206 | 116 | 214.516 | 97.688 |
| Full context operation | 206 | 180 | 214.516 | 149.328 |
| Switch dispatch, 128 iterations | 18,490 | 13,636 | 19,255 | 12,619 |
| Event queue, 32 round trips | 16,760 | 22,270 | 17,451 | 20,966 |
| MMU, CIA, VDC (128 each) | 1,256 / 1,256 / 2,148 | 4,170 / 4,176 / 10,304 | 1,308 / 1,363 / 2,418 | 4,092 / 3,883 / 9,204 |

The shared-C 2 MHz 8502 versus stock-Z80 totals are:

| Case | 8502 | Z80 |
|---|---:|---:|
| fill | 18,759 | 12,612 |
| copy | 20,614 | 15,684 |
| checksum | 11,314 | 6,976 |
| control | 14,004 | 11,078 |
| 16-bit arithmetic | 14,131 | 4,292 |

These are compiler/toolchain results, not a claim that the Z80 intrinsically
executes every equivalent algorithm faster.

## Handoff and offload

At 2 MHz, `1986` measured complete mailbox NOP round trips of 373.141 ticks
with the 8502 as requester and 323.094 with the Z80 as requester. The bare
round trips were 88.547 and 46.000 ticks respectively. VICE measured the same
shape at 337.891/295.828 complete and 78.797/44.844 bare.

The corrected offload crossover comparison is:

| Executive → worker | Operation | `1986` first win | VICE first win |
|---|---|---:|---:|
| 8502 1 MHz → Z80 | copy | 128 bytes | 64 bytes |
| 8502 1 MHz → Z80 | checksum / transform | none through 2 KiB | none through 2 KiB |
| Z80 → 8502 1 MHz | copy | none through 2 KiB | none through 2 KiB |
| Z80 → 8502 1 MHz | checksum | 256 bytes | 512 bytes |
| Z80 → 8502 1 MHz | transform | 128 bytes | 256 bytes |
| 8502 2 MHz → Z80 | all three | none through 2 KiB | none through 2 KiB |
| Z80 → 8502 2 MHz | copy | 256 bytes | none through 2 KiB |
| Z80 → 8502 2 MHz | checksum / transform | 32 bytes | 1 KiB |

The emulators disagree materially about Z80-to-8502 ownership-transition cost,
so these crossover sizes are not suitable as production constants. They do
agree on the decision-relevant result: none of these kernels should be sent
from a 2 MHz 8502 executive to the stock Z80 at the tested sizes. Physical
hardware must establish final per-operation thresholds.

## Controlled IRQ precondition

The unchanged r2 IRQ PRGs were entered only after BASIC stopped CIA1 Timer B
and acknowledged its pending flags:

```basic
POKE 56335,0:A=PEEK(56333)
```

Without that precondition, `1986` leaves Timer B running after startup. The
long 1 MHz 8502 interrupt-service run then observes ICR `$83` at its final
Timer-A interrupt: the enabled Timer-A source plus a masked Timer-B underflow
flag. The measured Timer-A path is otherwise complete, but the strict decoder
correctly rejects the non-isolated boundary. The rejected 1 MHz block and an
uncontrolled 2 MHz comparison are preserved in `diagnostics/`; neither is
included in the canonical results.

This does not alter an archived r2 PRG. It makes the machine precondition
explicit and produces the same isolated-Timer-A boundary observed in VICE. A
future harness revision should stop unused timers internally.

## Reproduction

For example, the controlled 2 MHz IRQ-service run is:

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
C128_CONFIG_PATH=bench/handoff/1986-stock.conf \
../1986/1986 --rom ../1986/roms \
  --disk bench/artifacts/2026-09-24-r2/irq-service-8502.prg \
  --paste 'fast:poke56335,0:a=peek(56333):bload"*":sys10240' \
  --paste-at 100 --frames 600 --no-throttle \
  --save-snapshot /tmp/irq-service-8502-2mhz.vsf

python3 tools/irq_service_decode.py /tmp/irq-service-8502-2mhz.vsf
python3 tools/snapshot_extract.py \
  /tmp/irq-service-8502-2mhz.vsf /tmp/irq-service-8502-2mhz.bin \
  --address 0xf180 --size 320
```

The BASIC `FAST` command is intentional. In this disk-loading path, `1986
--fast` alone did not leave the benchmark in 2 MHz mode; the dual-CPU result
headers exposed that such a run was still at 1 MHz. Stock-Z80 cases do not
issue `FAST`.
