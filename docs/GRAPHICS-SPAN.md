# Compact display-service fill mechanism

Status: standalone candidate qualified in 1986 and VICE, 2026-09-28; subsequently
installed with the pixel entry—see [GRAPHICS-PRIMITIVES.md](GRAPHICS-PRIMITIVES.md).
This note preserves the first in-place raster replacement experiment
from [GRAPHICS-CACHE-PLACEMENT.md](GRAPHICS-CACHE-PLACEMENT.md), issue #6.

## Implementation and budget

`bench/graphics-span/fill.c` retains the public fill signature and C geometry,
positive-size checks, clipping and row-table lookup. `span.s` handles the
already-clipped row: first/last-byte masks, set/clear, eight-address VIC byte
spacing and logical dirty-page flags. Single-byte rows intersect both masks;
every non-black color clears pixels, matching the existing C behavior.

Private row parameters belong to the serialized display service. The assembly
uses caller-clobbered cc65 `ptr1`/`tmp1`; it does not bank-switch, invoke a
callback, yield, poll services or add a kernel ABI. Count must be 1–40, with
nonempty masks and validated geometry supplied by C. Decimal mode is assumed
clear, as in the existing cc65 executive. No active-IRQ qualification is claimed.

Dirty indices come from the *logical* shadow offset, not the absolute pointer's
high byte. The shadow starts at `$A1E0`; physical address and logical page
boundaries differ. All dirty flags still refer to the existing 32-page map.

| Full display-service object material | CODE | BSS |
| --- | ---: | ---: |
| Current C reference | 4,258 | 32 |
| Candidate C wrapper/rest of service | 4,073 | 29 |
| Assembly span mechanism | 102 | 0 |
| Net saving | 83 | 3 |

The full experimental resident link confirms **86 net bytes saved**, with
identical cc65 library-helper membership and unchanged low/high BSS, zero-page,
syscall and task-gate segments. Its baseline segments match the preserved
pre-ASM production map. All split linker outputs are retargeted to the experiment's
directory, never the production providers. Experimental images are **not
bootable releases**: the unpadded candidate shadow moves to `$A18A`, so boot
staging/private bridges would be wrong if someone packaged it as-is.

No production memory reservation changed. An eventual integration must retain
the saved bytes as named padding until a separately qualified placement change.
This saving plus the existing 49-byte reserve would total 135 bytes; the
1,023-byte move-cache prototype would still require **888 additional bytes**,
before bindings/continuation state and other whole-link effects. The fill
experiment alone does not solve cache placement.

## Qualification

Eight exact PRGs (C reference and candidate × four cases) pass in both 1986
and VICE. Every record includes all 8,000 shadow bytes and 32 dirty flags,
compared with an independent pixel reference:

- 24 aligned 160×80 fills;
- 24 partly clipped fills under a non-fullscreen clip;
- 210 cumulative fills covering all 64 first/last bit-alignment pairs in
  each color, every VIC row phase, all nonempty single-byte mask intersections,
  both screen edges, full-width rows, non-black color 255, rejected dimensions
  and wholly offscreen rectangles;
- a fresh-map full-width row crossing logical pages 0→1, independent of later
  matrix writes. Guard bytes bound the shadow and clip/dirty state.

A negative-control PRG replaces only the initial `STA $E190,Y` with three
NOPs. Both emulators preserve every expected pixel but omit dirty flag 0;
the decoder rejects the record. Repairing that flag alone makes it pass.
This prevents a later fill from concealing a missing flag. The two faulty
runs are not positive qualifications.

A host harness executes the actual candidate C wrapper over 2,000 randomized
rectangles/clips/colors with a mocked span primitive. It verifies geometry,
parameter preparation, dirty/pixel equivalence and no row call on rejection;
it does not pretend to execute ASM. Integer ranges are bounded screen/window
geometry, not a claim about undefined signed-overflow inputs.

| VICE workload | C reference ticks | Candidate ticks | Speedup |
| --- | ---: | ---: | ---: |
| Aligned fills | 10,427,152 | 2,917,048 | 3.5746× |
| Clipped fills | 10,648,394 | 3,000,043 | 3.5494× |
| Small-fill matrix | 547,902 | 424,722 | 1.2900× |
| Isolated crossing row | 11,620 | 4,109 | 2.8279× |

IRQs are masked, display disabled and the 8502 runs at stock 1 MHz. Counts
include the identical unoptimized diagnostic caller but exclude setup, result
publication, screen commits and compositor work. These are not GUI latency or
hardware-performance promises. The C service uses production `-Oirs` flags;
the diagnostic driver is unoptimized, keeping its publication stores simple.

Exact sources, PRGs, maps, mutation, hashes, run-to-PRG manifests and emulator
provenance are preserved under
`bench/{artifacts,results}/2026-09-28-graphics-span/`. The historical C raster
and cache proofs remain unchanged. Rebuilt PRGs must match the qualification
manifests byte-for-byte before preservation is allowed.

## Reproduce

Build the normal prerequisites first, in `my-distrobox`, then:

```sh
distrobox enter my-distrobox -- python3 tools/graphics_span_bench.py build
distrobox enter my-distrobox -- python3 tools/graphics_span_bench.py run --engine 1986
python3 tools/graphics_span_bench.py run --engine vice
distrobox enter my-distrobox -- python3 tools/graphics_span_bench.py fault --engine 1986
python3 tools/graphics_span_bench.py fault --engine vice
python3 tools/graphics_span_bench.py decode
```

These are raw monitor-loaded `$2000` PRGs, not interactive UDEKS boot disks.
VICE sessions started by the runner are terminated by their capture helper;
no sibling emulator sources or GUI build are modified.

The standalone snapshot above remains immutable. The builders now explicitly
use its pre-ASM C source, reconstructing only isolated experimental links; they
never overwrite installed providers. The installed fill/pixel version preserves
173 bytes as padding and passes full-image emulator gates. Physical testing is
pending; compact line/shared raster work and the cache-placement deficit remain.
