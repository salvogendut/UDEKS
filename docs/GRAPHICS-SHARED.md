# Shared raster mechanisms in the display service

Status: installed and emulator-qualified, 2026-09-28, following the span/pixel
checkpoint `0406805`. Physical validation is pending; issue #6 remains open.

Line stepping remains **C Bresenham**, with the same signed geometry and
cooperative scratch ownership. It now calls the qualified public ASM pixel
entry instead of duplicating clipping, address calculation, masking and dirty
marking. Rectangles retain inclusive edges but draw them through four clipped
fill spans. A 52-byte ASM clear writes exactly 31×256 + 64 = 8,000 bytes,
ignores the clip like the old clear, and marks all 32 logical dirty pages.
Black sets bits; any other color clears them. All mechanisms remain in the
display service, not scheduler or kernel policy.

No drawing path yields, polls services, invokes callbacks or changes MMU.
The software-stack ABI and serialization requirements remain unchanged.
Existing clip/coordinate arithmetic assumptions are retained, not expanded
into a new overflow-safe geometry API. The C correctness oracle remains a
preserved pre-replacement source, never the new implementation itself.

## Measurements

| Whole display C-object change | Net bytes saved |
| --- | ---: |
| Shared-pixel line | 217 (214 CODE + 3 BSS) |
| Span rectangle | 20 CODE |
| ASM clear | 57 CODE (109 removed, 52 added) |
| Combined full-link saving | **294** |

The full link confirms the object result with unchanged library-helper
membership. C display CODE is now 3,453 and BSS 26; span/pixel/clear add
102/190/52 CODE, for **3,797 total display CODE**. The previous stage used
4,088 CODE and 29 BSS. All 294 net bytes remain named resident padding, on
top of the existing 173, 49 and separately retained eight-byte outline reserve.
`VICSHADOW $A1E0-$C11F`, common gateways `[254,46,68,358]`, UAPP zero page,
module/stack reservations and installed scheduler placement are unchanged.
Private boot-service/scheduler bridges regenerate normally.

Twelve standalone PRGs produce 24 passing 1986/VICE records: short and clipped
long lines, directed octants/axes/degenerate points, rectangle alignment and
clip cases, narrow/invalid/offscreen rectangles, and black/non-black clears.
Each checks all bitmap/dirty bytes, stack balance, guards and completion.
A host harness exercises the real candidate C geometry against an independent
pixel oracle over 1,000 randomized clip/geometry/color trials.

VICE primitive timings (CIA counts at stock 1 MHz, IRQs masked/display off):

| Case | Reference | Candidate | Speedup |
| --- | ---: | ---: | ---: |
| Short lines | 1,636,252 | 1,520,908 | 1.08× |
| Clipped long lines | 6,313,504 | 5,934,758 | 1.06× |
| Line matrix | 32,482,167 | 30,168,737 | 1.08× |
| Rectangle matrix | 4,797,988 | 1,158,171 | 4.14× |
| Black clear | 890,415 | 89,344 | 9.97× |
| Non-black clear | 889,853 | 88,786 | 10.02× |

These are primitive timings including diagnostic-call overhead, not GUI or
hardware speed claims. The production image is qualified separately.

## Integrated gates and limits

D71 and D64 pass 32 native 1986 wave drags with a background clock, lifecycle
guards, partial/complete drawing, exactly 21 Z80 row leases and console
cancellation. Normal input/backspace/history, pointer dragging, early Ctrl+C
and background-app/console recovery pass. VICE cold-boot, scheduler/app,
utility and input-wait smokes pass for both formats. Its shadow-clear and
installed-tail gates pass; all 8,000 bank-0 shadow bytes match the bank-1 bitmap.
VICE native mouse drag stress was not performed. No sibling emulator files
were edited and no ROMs/full snapshots are preserved.

The current harness reruns the preceding span/pixel disk for comparison:

| Native PAL-frame sample | Previous | New |
| --- | ---: | ---: |
| Maximum partial-plot release | 171 | 107 |
| Maximum complete-plot release | 167 | 103 |
| Completed-wave cancellation | **140** | **161** |
| Remaining replay after last release | 970 | 655 |

Release improves, but sampled cancellation **does not**. These are specific
scripted runs, not worst-case guarantees. Painting still takes seconds; faster
release also changes how much paint remains between scripted moves. Full
responsive-compositor acceptance stays open.

A clean parallel `make -j8 boot all placement-check` reproduces identical
disks. Exact programs, sources, maps, logs, bitmap captures and provenance are
preserved under `bench/{artifacts,results}/2026-09-28-graphics-shared` and
`...-graphics-shared-integration`, with SHA-256 manifests and host tests.
`tools/graphics_primitives_qualify.py --shared --preserve` refuses overwrite.

## Test and next decision

Test `build/boot/udeks.d64` on Pi1541 or either format in 1986/VICE. Run
`xinit`, `xclock &`, then `xwave`; drag during and after plotting, overlap and
resize, check the outline-only drag, Ctrl+C, console/history, and `xinit -q`.
Physical and visual resize/overlap qualification remain manual gates.

The raster reserves now total **516 bytes** against the 1,023-byte cache
prototype: **at least 507 bytes remain missing**, before bindings and bounded
continuation state. The cache is not installed, so moves still replay cached
heights; they do not recompute the wave on the Z80.

Next is an explicit service-placement/shared-raster budget decision, with
measured alternatives and lifetime/IRQ gates. Do not claim a fit, shrink
stacks, overwrite scheduler padding or remove commands to manufacture one.
Further optimization may help, but is not promised to cover that deficit.

Reproduce standalone probes with `tools/graphics_shared_bench.py build`, then
`run --engine 1986` inside `my-distrobox`, `run --engine vice` on the host,
and `decode`. Experimental links omit only this stage's provider/padding and
require the preserved span/pixel checkpoint map. All split linker outputs are
isolated; unpadded experimental kernels must never be packaged or booted.
