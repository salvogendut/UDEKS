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

## Required next gates

1. Audit all callers and IRQ paths before permitting non-reentrant storage.
   Confirm that neither yielding nor nested rendering can occur while scratch
   is live; document how future preemption will serialize the display service.
2. Measure line/fill CPU cycles or machine frames on 1986 and VICE. Use identical
   initial bitmaps, geometry, clipping and dirty-page output. Do not infer speed
   from code size or count a host-time run as C128 timing.
3. Link an experimental image, measure complete CODE/BSS/runtime-helper changes,
   and account for the `$A1E0` boundary and boot-delivery bindings before any
   production substitution. The 49 bytes are not currently free resident RAM.
4. Only then decide whether this pays for an occlusion/deferred-compositor
   increment or whether a service-placement change is required. Preserve the
   legacy xwave row reservation: old UAPP 0.1 images may still use `$F340-$F358`.
5. Re-run input, foreground cancellation, dragging/resizing/stacking and bank
   bitmap equality gates. Keep issue #6 and physical-C128 gates open.

Compile-only evidence: `bench/results/2026-09-27-graphics-raster-audit/report.json`.
