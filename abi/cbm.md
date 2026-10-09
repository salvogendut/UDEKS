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
on-target viewer enforces the same validation before publishing any pixels.

## Display model

`xview /picture.cbm` validates the header, opens a fixed-size movable/closable
VIC-II window, and streams into a pending retained bitmap. The empty frame
may appear during loading; no picture pixels appear until exact payload/EOF
validation and a successful file CLOSE. `xview /picture.cbm &` returns the
console prompt; foreground Ctrl+C cancels loading or closes the displayed app.
There is no zoom, resizing, browsing dialog or full-screen mode in this slice.

The packed viewer accepts dimensions up to **240x175**, subject to the shared
display pool: `8 + ceil(width/8) * height` bytes per image. **128x80 uses 1,288
bytes; 160x100 uses 2,008.** Dense pictures no longer hit the old 160-tile limit.
Sparse images cost the same as dense images of the same dimensions; there is
no compression. Oversized/over-budget files fail explicitly, never crop,
truncate or downsample.
Every accepted CBM pixel is displayed 1:1, black on the standard yellow paper.
Conversion/resizing/dithering happens on the host, not inside the viewer.

The generic UDEX 0.2 executable uses private arguments and native mounted-file
I/O; there is no resident app ID, special launch path or kernel change. The
3,217-byte executable has 2,455 image + 64 BSS bytes: **2,519 runtime bytes**.
It fits ordinary slots 3 and 5, without borrowing slot 4. The build enforces
both fits. Two `xview` instances can show different pictures with private
arguments, decoder state and window ownership. Window titles show the first
eight basename characters. Close the desired window, or use foreground Ctrl+C;
`xview -q` stops one matching instance, not a filename-selected instance.

Slot compatibility and drawing memory are separate limits. Retained surfaces
share the existing **2,304-byte display pool**. ALEX uses 701 bytes and
CLOCKWORK uses 704, so they fit together (1,405), also leaving room for a clock.
The smaller ALEX2 demo leaves room for both clock and wave. There is no new
four-large-app guarantee or memory compaction of running programs. BEGIN
fails with a clear display-memory error if peers leave insufficient room.

Loading yields between bounded reads. The single filesystem stream is owned
only during loading and is closed on errors as well as success; task retirement
handles cancellation. A **19-byte application buffer** replaces the full tile
array. Header/payload data is copied out of the shared request before yielding.
Move/uncover repaints use the service's retained packed pixels, without opening
or reading the file again. Closing while loading cancels quietly and releases
the stream; errors abort the transaction and task exit retires the frame while
preserving the diagnostic/exit status. Requires **UTRQ 0.20**, not older disks.

## Build and demo

From the feature worktree `build/packed-bitmap`, branch `graphics-packed-bitmaps`:

```sh
distrobox-enter my-distrobox -- make -j8 boot xview graphics-apps-check
python3 tools/build_xview_demo.py --output build/xview/demo
```

Use a new output directory on repeat runs; the packaging tool refuses overwrite.
D71 uses both sides; D64 is supported by the tool but the normal compact image
has insufficient free space for this additional app and photo. No existing
applications are removed. The demo disks leave the kernel and existing files
unchanged. Packed demo candidates are
**`build/packed-bitmap/build/xview/demo/udeks-packed.d71`** and **`.d81`**
relative to the root checkout. Both are generated from the matching UTRQ 0.20
boot candidates; root published downloads remain unchanged until acceptance.
The packager includes the three original pictures plus new 128x80 ALEX128 and
160x100 CLOCK160 conversions. Graphics initializes on demand.

Test the larger pictures separately (close the first before opening the second):

```text
xview /alex128.cbm &
xview -q
xview /clock160.cbm &
xview -q
```

CLOCK160 leaves only 296 display bytes, insufficient for a clock. This is a
display-pool limit, not a lost app slot. Try it alone; errors must leave other
windows intact and release the loading stream. Use `cat /hello` after cancelling
an in-progress foreground load with Ctrl+C or its close box.

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
background one alive. ALEX2 is a small three-app example; the original ALEX
and CLOCKWORK conversions also now fit beside clock + wave. The new larger
ALEX128/CLOCK160 pictures plus both apps exceed the shared display pool.

Provenance: the container and converter began on `additional-apps` at `6b61f5c`.
This branch corrects row padding/dimension validation, transparent backgrounds,
the payload-size documentation and the old fixed-slot viewer proposal.
Host tests and the current VICE qualification are recorded in
[the ordinary-slot/multiple-instance evidence](../bench/results/2026-10-09-cbm-viewer-r2/README.md).
The earlier joined-slot prototype is preserved in
[the original evidence](../bench/results/2026-10-09-cbm-viewer/README.md).
