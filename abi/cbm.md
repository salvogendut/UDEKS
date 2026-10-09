# Commodore BitMap container (.CBM)

The `.CBM` container holds a black-and-white bitmap for the VIC-II hires
display. It is scanline-packed and deliberately independent of the 320x200
cell layout, so the same file serves any picture up to 320x200.

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 4 | Magic `CBM\0` |
| 4 | 1 | Version (`1`) |
| 5 | 2 | Width, little-endian, 1..320 |
| 7 | 2 | Height, little-endian, 1..200 |
| 9 | 2 | Stride = ceil(width / 8), little-endian |
| 11 | stride × height | Bitmap payload |

Rows are stored top to bottom; each row is `stride` bytes, most significant
bit first, so pixel `(x, y)` uses bit `7 - (x % 8)` of payload byte
`y * stride + x / 8`. `1` is ink, `0` is background. Unused low bits in the
final byte of a row must be zero.

The header must match the payload exactly: a `.CBM` file is `11 + stride *
height` bytes. Width/height/stride disagreement, a missing payload, extra
trailing bytes, a bad magic or an unsupported version are malformed files and
must be rejected before any pixel is shown.

## Creating pictures

`tools/png_to_cbm.py` converts a JPEG or PNG:

```sh
python3 tools/png_to_cbm.py photo.jpg pic.CBM            # 320x200
python3 tools/png_to_cbm.py logo.png --width 64 --height 64 \
    --threshold 160 --invert pic.CBM
python3 tools/png_to_cbm.py PICS/alex.png ALEX.CBM --width 88 --height 63 --dither
```

The source is aspect-fitted onto a white canvas of the requested size and then
thresholded to black and white (`--threshold`, default 128; `--invert` swaps
the colors). Transparent pixels are composited onto white. `--dither` uses
Floyd-Steinberg shading instead of a custom threshold; it is useful for photos.
Output is a raw `.CBM` file, **not a PRG with a load address**. Store it as a
closed SEQ file using host disk tools or `tools/add_cbm_viewer.py`; then view
it with `xview /pic.cbm`. The container supports 320x200; the initial viewer
has smaller bounds below. The converter does not silently enforce those bounds.

The reference decoder used by the tests is `parse()` in the same tool; the
on-target viewer must enforce the same validation before opening a window.

## Display model

`xview /picture.cbm` validates the complete file, closes it, then opens a
fixed-size movable/closable VIC-II window. `xview /picture.cbm &` returns the
console prompt; foreground Ctrl+C cancels loading or closes the displayed app.
There is no zoom, resizing, browsing dialog or full-screen mode in this slice.

The first viewer accepts dimensions up to **240x175**, with at most **160
nonblank 8x5 tiles**. Blank tiles are omitted losslessly. Thus 88x63, 80x80 or
128x50 fit regardless of pixel content; a larger sparse drawing may also fit.
A dense image can exceed the tile limit even when its dimensions fit.
Oversized/over-budget files fail explicitly, never crop, truncate or downsample.
Every accepted CBM pixel is displayed 1:1, black on the standard yellow paper.
Conversion/resizing/dithering happens on the host, not inside the viewer.

The generic UDEX 0.2 executable uses private arguments and native mounted-file
I/O; there is no resident app ID, special launch path or kernel change. The
3,184-byte executable has 2,442 image + 1,385 BSS bytes: **3,827 runtime bytes**.
It fits ordinary slots 3 and 5, without borrowing slot 4. The build enforces
both fits. Two `xview` instances can show different pictures with private
arguments, decoder state and window ownership. Window titles show the first
eight basename characters. Close the desired window, or use foreground Ctrl+C;
`xview -q` stops one matching instance, not a filename-selected instance.

Slot compatibility and drawing memory are separate limits. Retained commands
share the existing **2,304-byte display pool**. ALEX uses 1,144 bytes and
CLOCKWORK uses 1,152, so they fit together (2,296); adding a clock does not.
The smaller ALEX2 demo leaves room for both clock and wave. There is no new
four-large-app guarantee or memory compaction of running programs. PRESENT
fails with a clear display-memory error if peers leave insufficient room.

Loading yields between bounded reads. The single filesystem stream is owned
only during loading and is closed on errors as well as success; task retirement
handles cancellation. A one-row staging buffer, tile indices and at most 1,280 command bytes
replace a full 8 KiB framebuffer. Move/uncover repaints use the service's
retained command copy, without opening or reading the file again.

## Build and demo

From the repository checkout (the original qualification worktree was
`build/cbm-viewer`, branch `app-cbm-viewer`):

```sh
distrobox-enter my-distrobox -- make xview
python3 tools/add_cbm_viewer.py --disk build/udeks.d81 \
    --output build/xview/udeks-pictures-new.d81 PICS/ALEX.CBM PICS/CLOCKWORK.CBM PICS/ALEX2.CBM
```

Use a new output name on repeat runs; the packaging tool refuses overwrite.
D71 uses both sides; D64 is supported by the tool but the normal compact image
has insufficient free space for this additional app and photo. No existing
applications are removed. The demo disks leave the kernel and existing files
unchanged. The qualified candidates remain at
**`build/cbm-viewer/build/xview/udeks-pictures-r3.d71`** and **`.d81`** in the
original development workspace, not in a fresh clone. The commands above
recreate the D81 from tracked inputs; use `--disk build/udeks.d71` and a fresh
`.d71` output path for D71. Graphics initializes on demand.

Try two independent pictures:

```text
xview /alex.cbm &
xview /clockwork.cbm &
```

Both start at the same position; drag the first aside to see both. Close both
before the separate three-app test:

```text
xview /alex2.cbm &
xclock &
xwave &
```

Try dragging, covering/uncovering, closing either viewer independently, and
launching a second viewer in the foreground to verify Ctrl+C leaves the
background one alive. Use the smaller ALEX2 for the three-app combination:
the larger photos plus clock + wave exceed the shared display pool.

Provenance: the container and converter began on `additional-apps` at `6b61f5c`.
This branch corrects row padding/dimension validation, transparent backgrounds,
the payload-size documentation and the old fixed-slot viewer proposal.
Host tests and the current VICE qualification are recorded in
[the ordinary-slot/multiple-instance evidence](../bench/results/2026-10-09-cbm-viewer-r2/README.md).
The earlier joined-slot prototype is preserved in
[the original evidence](../bench/results/2026-10-09-cbm-viewer/README.md).
