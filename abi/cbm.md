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
| 11 | width × height / 8 | Bitmap payload |

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
python3 tools/png_to_cbm.py logo.png --width 160 --height 100 \
    --threshold 160 --invert pic.CBM
```

The source is aspect-fitted onto a white canvas of the requested size and then
thresholded to black and white (`--threshold`, default 128; `--invert` swaps
the colors). Output is a raw `.CBM` file; copy it to the picture disk
(`copy pic.CBM 9:pic.CBM` from BASIC, or via the host's CBM disk tooling) and
view it with `xview pic.CBM`.

The reference decoder used by the tests is `parse()` in the same tool; the
on-target viewer must enforce the same validation before opening a window.

## Display model

`xview <file>.CBM` opens a VIC-II window sized to the picture (clamped to the
screen), reads the payload from disk and plots the ink pixels into the window's
content area. The viewer is an additional fixed-slot application under issue
[#32](https://github.com/salvogendut/UDEKS/issues/32): four concurrent
graphical apps remain the ceiling, and the picture must be repaintable without
keeping the whole 8 KiB payload resident.