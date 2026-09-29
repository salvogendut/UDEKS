# Installed display-service span and pixel mechanisms

Status: integrated on `graphics-window-cache-spike`, emulator-qualified on
2026-09-28; physical-C128 validation pending. Issue #6 remains open.

The first compact replacements are now in the **display service**, not in
kernel policy. `vic_graphics.c` retains fill geometry, clipping and row lookup;
`vic_span.s` merges a clipped row's edge masks, and `vic_pixel.s` supplies the
existing public cc65 pixel entry. Both assembly sources are byte-identical to
the independently qualified standalone candidates. Line rendering, rectangle
composition, dirty-page commits and the public UAPP API remain unchanged.

The pixel entry accepts color in A and consumes exactly four software-stack
bytes (y, x), including rejected coordinates. Signed clipping, black set versus
all-other-colors clear, interleaved rows and logical dirty-page indices match
the C reference. The standalone suite checks full bitmap/dirty-map equality,
clip boundaries, extreme signed coordinates, all bit/row offsets, stack balance,
guards and a logical-page crossing at the unaligned `$A1E0` shadow base.

The stack probe deliberately reads each SP into a variable **before** comparing
them: cc65 can push the comparison's left operand before evaluating the right.
The old inline comparison falsely failed even on the unmodified C reference.

## Budget and ownership

The complete display implementation now uses 3,796 C CODE + 102 span CODE +
190 pixel CODE = **4,088 CODE**, versus 4,258, and 29 BSS versus 32. Net saving
is **173 bytes**, confirmed by an isolated full link with identical library
helper membership. Named resident padding holds those 173 bytes; existing
49-byte raster and eight-byte outline reserves remain intact. The frozen
`VICSHADOW $A1E0-$C11F`, low/high state, module/stack reservations, common
gateway sizes `[254, 46, 68, 358]` and UAPP zero-page addresses are unchanged.
Private boot-service/scheduler bridges are regenerated for the new link.

Drawing remains cooperative, serialized and binary-mode. Neither mechanism
yields, invokes services, changes MMU mapping or adds BSS. Caller-clobbered
cc65 scratch is not used by the current pointer IRQ/tick path. This is not
permission to add drawing in IRQs or enable preemption without serialization.

The move-cache prototype needs 1,023 bytes. Named raster reserves now total
222, leaving **at least 801 additional bytes**, before bindings and bounded
continuation state. No cache is installed and no guard, stack, shell command
or scheduler padding has been appropriated. Unchanged-size moves still replay
cached wave heights through the 8502; the Z80 does not recompute them.

## Qualification and limits

Standalone span: 16 positive emulator records plus two rejected missing-dirty
flag controls; bulk fill primitive speedup 3.55–3.57×. Standalone pixel: 16
positive records; speedups include driver overhead and are not GUI timings.
Exact PRGs, maps, sources and provenance are preserved in the respective
`bench/{artifacts,results}/2026-09-28-graphics-{span,pixel}` directories.

Integrated D71 and D64 both pass 32 native 1986 drags with a background clock,
partial/complete plots, lifecycle guards, exactly 21 Z80 row leases, Ctrl+C
and subsequent console input. The normal input smoke also passes typing,
backspace, history, 1351 dragging and early foreground cancellation. VICE
cold-boot/app/utility/input-wait checks pass on both disk formats; its shadow
clear/installed-tail checks pass and all 8,000 drawn shadow bytes equal the
bank-1 VIC bitmap. VICE was not subjected to native mouse drag stress.

The current harness against the preserved pre-replacement D71 reports:

| Native PAL-frame measurement | Reference | Integrated |
| --- | ---: | ---: |
| Maximum partial-plot drag release | 279 | 171 |
| Maximum complete-plot drag release | 266 | 167 |
| Completed-wave cancellation | 174 | 140 |
| Remaining replay after last release | 674 | 970 |

These are deterministic harness samples, not worst-case guarantees. Faster
release changes how much deferred paint has completed between scripted moves;
the last measurement does **not** establish improved full-image completion.
Repaint still takes seconds, so the responsive-compositor acceptance box stays
unchecked. Judge both release responsiveness and visible completion on hardware.

A clean parallel `make -j8 boot all placement-check` reproduces identical disks.
`make graphics-cache-placement` measures the new owned padding and primitives.
Exact integrated disks/maps, source snapshots, logs and bitmap captures are in
`bench/{artifacts,results}/2026-09-28-graphics-primitives-integration`, protected
by SHA-256 manifests and host tests. No ROMs or full emulator snapshots are saved.

## Test this image

Use `build/boot/udeks.d64` for Pi1541, or `.d71` in 1986/VICE. Cold boot, then:

```sh
xinit
xclock &
xwave
```

Drag the wave while it is drawing and after completion, overlap the clock,
resize, then press Ctrl+C at the VDC console. Check pointer accuracy, outline
movement, complete repaint, surviving clock, normal typing/history, and
`xinit -q`. Physical resize/overlap behavior remains a manual gate.

## Reproduce without changing historical evidence

In `my-distrobox`, build and run the documented native input/stress probes;
on the host run `task_yield_probe.py` for both disks and
`shadow_boot_probe.py --vic-compare` with separate output paths. See the saved
logs and `tools/graphics_primitives_qualify.py` for the exact required paths.
Capture host `flatpak info net.sf.VICE > build/raster-primitives-VICE-flatpak.txt`
before running the qualifier in the container. Its `--preserve` refuses to
replace an existing snapshot. All VICE helpers close only their owned sessions.

The older raster/span/pixel builders now use the immutable pre-ASM C reference.
Their **isolated** budget links omit the two installed replacement objects and
173-byte padding, then require the preserved reference map. This keeps the C
oracle real, retains executable benchmark PRGs for future hardware tests, and
does not alter any production output. Experimental unpadded kernels must not
be packaged or booted.

The follow-on [shared-raster mechanisms](GRAPHICS-SHARED.md) are now integrated
and separately qualified; the measurements here remain the preceding checkpoint.
They save another 294 net bytes, retaining all savings as padding. An explicit
service-placement/budget investigation is next: the cache still does not fit.

That is the historical shared-raster checkpoint. The subsequent
[completion seam](WINDOW-CACHE-COMMAND.md) spends 158 bytes from that padding,
leaving 358 total resident reserve. Its combined C cache command is qualified
standalone but not integrated; complete manager/NMI/delivery fit remains open.
