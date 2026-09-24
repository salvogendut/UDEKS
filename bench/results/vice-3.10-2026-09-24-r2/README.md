# VICE 3.10 benchmark results — r2

These results use the exact PRGs in `bench/artifacts/2026-09-24-r2/` and VICE
3.10 from Flatpak `net.sf.VICE`. The runner used PAL/default C128 settings,
warp mode, disabled sound, seed 0, native 1 or 2 MHz 8502 mode, and VICE's stock
Z80 implementation. No Z80 accelerator or doubled-frequency modification was
enabled.

All 19 canonical result blocks pass their strict decoder. The offload cases
were repeated three times per speed and were byte-identical. The
interrupt-service cases were also repeated three times: both 8502 modes were
byte-identical; two Z80 repeats matched each other and differed slightly from
the first only in the minimal-path distribution (median service 527.5 versus
528 ticks). Canonical blocks are in `raw/`, additional repeats in `repeats/`,
and both directories include SHA-256 manifests.

## Main result

VICE independently reproduces the split seen in the initial `1986` work:

- stock Z80 wins all substantive shared-C workloads and the compiler-complete
  and full task-context operations;
- the 2 MHz 8502 wins CPU-core context, event-queue traffic, MMU/CIA/VDC
  transactions, and every interrupt path by a large margin;
- complete CPU handoff is expensive enough that jobs must be batched;
- with a 2 MHz 8502 executive, none of the three handwritten offload kernels
  benefits from delegation to the Z80 through 2 KiB.

Selected 2 MHz/stock-Z80 figures, in one-megahertz CIA ticks:

| Measurement | 8502 | Z80 | Interpretation |
|---|---:|---:|---|
| IRQ entry median | 20 | 77.5 | 8502 lower |
| Minimal IRQ service median | 149 | 527.5 | 8502 lower |
| Kernel-tick IRQ service median | 162 | 556.5 | 8502 lower |
| Compiler context operation | 214.516 | 97.688 | Z80 lower |
| Full context operation | 214.516 | 149.328 | Z80 lower |
| Switch dispatch, 128 iterations | 19,255 | 12,619 | Z80 lower |
| Event queue, 32 round trips | 17,451 | 20,966 | 8502 lower |
| MMU, CIA, VDC (128 each) | 1,308 / 1,363 / 2,418 | 4,092 / 3,883 / 9,204 | 8502 lower |

At 2 MHz, a complete mailbox NOP round trip costs 337.891 ticks with the 8502
as requester and 295.828 with the Z80 as requester. The corrected offload
crossovers are:

| Executive → worker | Copy | Checksum16 | XOR/rotate |
|---|---:|---:|---:|
| 8502 1 MHz → stock Z80 | 64 bytes | none through 2 KiB | none through 2 KiB |
| stock Z80 → 8502 1 MHz | none through 2 KiB | 512 bytes | 256 bytes |
| 8502 2 MHz → stock Z80 | none through 2 KiB | none through 2 KiB | none through 2 KiB |
| stock Z80 → 8502 2 MHz | none through 2 KiB | 1 KiB | 1 KiB |

The VICE direction is therefore clear but not by itself a final decision: it
strengthens the case for an 8502 executive with selective Z80 jobs. The same
r2 suite has since run under [`1986`](../1986-7556c23-2026-09-24-r2/README.md),
where the executive-level split agrees despite differing reverse-offload
thresholds. Physical-hardware and display-pressure qualification remain open;
the original `1986` r1 numbers are historical rather than directly comparable.

## Reproduction

For example, the corrected 2 MHz offload capture is:

```sh
python3 tools/vice_capture.py \
  bench/artifacts/2026-09-24-r2/offload-dual.prg \
  /tmp/offload-2mhz.bin \
  --autostart --fast --entry 0x27d0 \
  --result-address 0xf400 --result-size 416 --state-offset 5

python3 tools/offload_decode.py /tmp/offload-2mhz.bin
```

The Flatpak needs temporary loopback networking because VICE exposes its text
monitor on localhost; the runner requests this per invocation with
`flatpak run --share=network`. It does not persist a Flatpak permission change.
