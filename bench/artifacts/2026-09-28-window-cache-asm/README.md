# Standalone assembly window-cache blitter

Issue #6, `graphics-window-cache-spike`, based on the C reference checkpoint
`4ceeaf6`. These twelve PRGs are raw monitor programs loaded/entered at
`$2000`, not BASIC launchers or UDEKS boot disks. Cases 0–10 use the unchanged
bank-transfer probe. `cache-matrix.prg` separately checks 64 alignment pairs,
a full-width row and the bottom-right pixel using the actual ASM row routines.
All pass in 1986 and VICE. IRQs are masked and display disabled at stock 1 MHz.

One additional **intentionally failing** PRG, `cache-padding-negative.prg`,
replaces the capture tail-mask instruction with three NOPs. Its mutation and
hashes are in `padding-mutation.json`. Valid pixels/dirty flags still match,
but the direct padding check returns failure 3 in both emulators and the
decoder rejects it. Do not mistake this negative control for a passing image.

The wrapper uses cc65 `-Oirs`; diagnostic drivers remain unoptimized. ca65
assembles `rows.s` and `transfer-lease.s`. Measured object material is:

| Component | CODE | BSS |
| --- | ---: | ---: |
| C validation/owner wrapper | 607 | 13 |
| ASM byte rows | 267 | 5 |
| Installer + common gateway image | 131 | 0 |

Total 1,023 bytes, before whole-link helper changes and manager/ABI bindings.
The copied 99-byte gateway runs at `$F68A-$F6EC`; its source is included above,
not free resident memory. The staging-page lease lasts a complete operation,
does not yield or call services, and restores the page before returning.
Active IRQ/service interaction remains unqualified.

Exact binaries, maps, generated assembly, source snapshots, build provenance
and PRG hashes are covered by `SHA256SUMS`. No ROMs are distributed. Matching
records/comparison and immutable C baseline are in the corresponding result
directories. See [the design note](../../../docs/WINDOW-MOVE-CACHE.md).

Reproduce from the repository root:

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_bench.py build --variant asm
distrobox enter my-distrobox -- python3 tools/window_cache_bench.py run --variant asm --engine 1986
python3 tools/window_cache_bench.py run --variant asm --engine vice
python3 tools/window_cache_bench.py decode --variant asm
python3 tools/window_cache_compare.py
```

Production D71/D64 disks are unchanged. This checkpoint does not enable
pixel-preserving moves in the resident system.
