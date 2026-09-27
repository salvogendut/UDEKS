# Raster scratch audit — issue #6 follow-up

Branch: `graphics-raster-audit`, based on PR #7 merge `6aadcf3`.
Production rasterization, ABI, kernel layout and disks are unchanged.

The next responsiveness bottleneck is synchronous composition: window chrome,
cached surface replay and exposed-clock redraw. Before adding deferred-compositor
state, this spike measures whether changing cc65 temporary storage can reduce
raster overhead and recover resident space without another staging mechanism.

## Repeatable experiment

```sh
distrobox enter my-distrobox -- python3 tools/graphics_raster_audit.py
python3 -m unittest discover -s tests -p 'test_graphics_raster_audit.py'
```

The tool copies the actual display module into `build/graphics-raster-audit`,
changes only line/fill storage, compiles all three variants with the production
`cc65 -Oirs` flags, and reads segment sizes from assembled objects with od65.
Source hash and toolchain version accompany the report. It does not link an
experimental kernel or replace any production output.

| Variant | CODE | added BSS | net object saving |
| --- | ---: | ---: | ---: |
| Production baseline | 4,347 | 0 | 0 |
| Static temporary variables | 4,266 | 32 | 49 |
| Static temporaries and copied arguments | 4,342 | 50 | −45 |

These are **object bytes**, not guaranteed whole-link savings and not measured
runtime speed. Copying arguments is rejected on footprint grounds. The
scratch-only candidate merits a runtime benchmark but is not yet integrated.
The source and projection remain unchanged; the host tests execute each real
variant against an independent clipped pixel/line/fill reference over 500
deterministic cases per variant, including off-screen coordinates, empty clips,
nonpositive rectangles, both colors, and exact dirty-page flags.

## Qualification follow-up

The standalone timing suite now passes on both 1986 and VICE with complete
independent-reference pixel/dirty-map equality. Timer-count reductions are
11.709–12.481% for tested lines and 23.589–23.859% for tested fills. These are
interrupt-masked, display-off primitive workloads, not end-to-end GUI timings.
The two engines differ in raw CIA cascade counts; that is preserved, not hidden.
The caller/IRQ audit confirms current cooperative scratch ownership, not future
preemptive safety.

An isolated whole-kernel link confirms 49 bytes of net savings, but it moves the
shadow start to `$A1AF` and private providers. That image has not been packaged
or booted with old import bridges. See the detailed
[timing/link evidence](../bench/results/2026-09-27-graphics-raster-timing/README.md)
and [repeatable suite](../bench/graphics-raster/README.md).

## Remaining integration gates

1. Preserve the `$A1E0` shadow/staging contract explicitly. One candidate is a
   named 49-byte code reservation, subsequently consumed by measured compositor
   work. Regenerate private provider/import bindings; do not boot the isolated
   candidate with production bindings or reuse legacy row scratch.
2. Keep the audited no-yield/no-nested-drawing contract explicit. Future
   preemption needs display-service serialization; static scratch is not
   automatically reentrant.
3. Re-run normal/panic placement, clean builds and complete application/window
   input and bitmap gates on the integrated candidate. Then measure launch,
   close and repaint latency with interrupts and display active.
4. Only then decide whether the recovered space pays for an occlusion/deferred-compositor
   increment or whether a service-placement change is required. Preserve the
   legacy xwave row reservation: old UAPP 0.1 images may still use `$F340-$F358`.
5. Re-run input, foreground cancellation, dragging/resizing/stacking and bank
   bitmap equality gates. Keep issue #6 and physical-C128 gates open.

Compile-only evidence: `bench/results/2026-09-27-graphics-raster-audit/report.json`.
