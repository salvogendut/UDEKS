# Installed REU bitmap backend — 2026-10-09

Production disk boot and unmodified XVIEW/XCLOCK/XWAVE programs, VICE x128
3.10 (Flatpak provenance in each report). This is **not** a standalone scratch
probe. The normal and panic link agree; no app allocation or public API moves.

Both runs use the same preserved D81 and CLOCK160 picture:

- **512 KiB REU:** exact CLOCK160 pixels, then clock + wave coexistence;
  interactive shell; CAT reads after freeing wave's joined allocation;
  exact uncover repaint without re-upload; independent CLOCK160 and ALEX128 objects;
  closing one preserves its peer; full retirement and slot/object reuse.
- **No REU:** exact original bitmap, 2,008-byte internal allocation; clock
  exits when its drawing does not fit (the known stock capacity limit);
  viewer remains intact; close, reuse and disk reads pass.
- Both: live hidden code equals the linked image before/after applications;
  byte-exact shadow/VIC comparison for each pictured stage; pointer IRQ
  counter advances; DMA buffer neighbors and immutable bootfs backup survive;
  borrowed common page is restored; kernel canary is intact; disks unchanged.
- REU backing file independently equals the 2,000- and 1,280-byte images in separate
  8 KiB extents, with every other expansion byte still `$A5`. This checks
  actual stored content and isolation, not merely successful DMA status.

VICE captures in `vice-*/*.bin` include their two-byte little-endian load
address prefix. `artifacts/bitmap-hidden-sealed.bin` and `vice-512/reu.img`
are raw. Reports bind source hashes, exact boot disk and emulator provenance;
`SHA256SUMS` covers preserved artifacts, captures and reports. The final code
contains no diagnostic row-copy instrumentation.

**1,734 host tests pass**, including source/artifact hashes and independent
decoding of the preserved pixels, expansion bytes, guards and cleanup records.
Container boot/graphics layout, placement and sim6502 bitmap gates passed.
A forced parallel rebuild (`make -B -j8`, no `make clean`) reproduced the
normal D64/D71/D81 and hidden-module hashes exactly. The compact D64 is built
normally; these picture demo files are deliberately packaged only on D71/D81.
D81 was cold-boot tested here; the matching D71 is supplied for testing, not
claimed as an additional live run. All probe-owned VICE sessions exited.

## Try it

Open `artifacts/udeks-packed.d81` in VICE with a **512 KiB REU**, drive 8 set
to **1581**. Cold boot, then:

```text
xview /clock160.cbm &
xclock &
xwave &
```

The three windows now coexist. Close wave before launching another native
console program: wave uses a joined allocation, and REU does not add task
slots. For independent large viewers, close clock/wave, launch another
`xview /clock160.cbm &`, then move windows to see both. Each `xview -q` stops
one instance. Root drive 8 mounts automatically; no manual mount is needed.

Reproduce from the worktree root (expand the paths below with this evidence
directory's prefix): `python3 tools/reu_graphics_probe.py --disk
artifacts/udeks-packed.d81 --picture artifacts/CLOCK160.CBM --second-picture
artifacts/ALEX128.CBM --reu 512`. Repeat with `--reu 0` for stock fallback.
The runner creates disposable media and a private REU file and closes VICE.

## Remaining gates

These are integration/coexistence checks, **not** full interaction, injected
NMI/RESTORE, pending-load cancellation, hardware-fault or physical-C128/REU
qualification. Package 3 remains the broader move/resize/input/cancellation
matrix and manual hardware acceptance. No 1986 or hardware result is inferred.
At the time of these automated runs, neither `main` nor the root published
boot downloads had been updated.

Subsequent acceptance: the user reported "It all works beautifully" and
authorized commit/push/PR/merge on 2026-10-09. The README includes the supplied
desktop screenshot. This accepts the demonstrated milestone; it does not
establish the unreported interaction or physical-REU gates listed above.
The preserved automated evidence remains unchanged.
