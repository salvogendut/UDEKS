# VDC framebuffer and compositor

The VDC can provide a genuine 640×200 one-bit bitmap front buffer. UDEKS will
use it as the basis of a C graphics/compositor service so applications can mix
text and graphics on one surface. Text in this mode is rendered from fonts by
software; the VDC does not overlay its character mode on bitmap mode.

## Memory tiers

A 640×200 bitmap occupies 16,000 bytes at an 80-byte stride. An optional
80×25 cell-attribute plane requires another 2,000 bytes.

- **16 KiB VDC:** one monochrome front buffer nearly fills VDC RAM. The
  canonical backing surface lives in banked system RAM, and dirty rows or
  rectangles are uploaded through bounded VDC transfers. Hardware text mode
  remains available as the low-memory console fallback.
- **64 KiB VDC:** the service may add the attribute plane, VDC-resident staging
  areas, cached fonts, and front/back buffers while retaining a system-RAM
  backing surface for recovery and composition.

The capability service selects the tier from measured VDC RAM; no graphics
code infers it from a model name.

## Module boundary

The compositor will be predominantly C and will own surfaces, clipping, dirty
tracking, software font rendering, and text/graphics composition. Assembly will
remain limited to bounded VDC register access and measured block-transfer fast
paths. Applications will target a surface API, never `$D600/$D601` or a fixed
VDC address.

The present C text console predates this compositor and is the first C display service.
The framebuffer/compositor is planned as the first substantial graphics C
module; once it is usable, the console becomes one of its clients rather than
owning VDC layout directly.

## First implementation slice

The baseline mode transition, hardware clear, linked splash upload, complete
readback, and black-on-yellow activation are implemented and qualified on both
VDC RAM tiers. The software font and hardware panel are also qualified; general
surface drawing, dirty tracking, and the public client API remain the next layer.

The initial display service deliberately targets the conservative mode that
works with either VDC memory tier: 640x200, one bit per pixel, 80 bytes per
scanline. Its first public operations will be small and stable:

1. acquire and release the display;
2. enter and leave the baseline bitmap mode;
3. clear, plot, draw an 8-bit span, and fill a clipped rectangle;
4. draw one software glyph and a string;
5. mark dirty scanline spans and flush them to VDC RAM.

The API will use opaque surface and display handles. Mode tables, VDC addresses,
and register numbers remain private to the service. More ambitious modes such
as 640x225, interlace, per-cell colour, and page flipping are later capability-
gated extensions rather than assumptions made by the baseline API.

The first end-to-end client is the boot splash. A host-side build tool converts
`assets/udekspipe-64.xpm` into packed VDC scanlines while preserving the PNG
and both XPM sizes as source artwork. The service places the compact 64x64 pipe
mark at the upper right of the baseline surface and verifies it in VDC RAM. No
PNG decoder belongs in the kernel. The 160x160 variant remains available for
future layouts with more room. The present transitional service runs after the
text console and takes final display ownership; the software-font milestone
removes that split ownership by making console output a framebuffer client.

The second client installs an original software-defined 5x7 font in 8x8 cells
and renders a hardware inventory beside the splash. It reads the published
`HCAP` record; it must not touch probe registers itself. The first screen
reports PAL/NTSC, VDC family and memory, and REU/GeoRAM presence. This makes glyph rendering,
text-over-bitmap composition, clipping, dirty-span flushing, and cross-service
data consumption part of the same visible qualification.

## VDC operating rules

Experience from existing C128 software suggests several rules that should be
treated as correctness requirements rather than optional optimisations:

- Snapshot the complete VDC mode state before taking ownership and restore it
  on release or service failure. Each mode transition starts from a documented
  baseline so stale register state cannot leak between modes.
- Program mode registers through ordered mode descriptors. Some VDC results
  depend on write order, not only on the final register values.
- Every ready wait is bounded. A failed VDC operation is reported to the
  microkernel and must not hang the machine.
- Use register 30 block fill/copy behind a checked assembly primitive for
  clears, moves, repeated glyph rows, and VDC-resident copies.
- Update only changed scanline spans or glyph runs. Text and animation should
  not require uploading the complete 16,000-byte bitmap each frame.
- Schedule disruptive register changes at a safe display boundary where
  practical. Timing-sensitive or unusual modes require separate PAL/NTSC,
  emulator, monitor, and real-hardware qualification.
- Keep a recoverable system-RAM representation. The VDC front buffer is a
  device resource, not the compositor's sole copy of client state.

## Reference survey and provenance

These projects provide valuable behavioural evidence and design examples:

- [vdcmaniac](https://github.com/xahmol/vdcmaniac) documents register ordering,
  mode-state leakage, hardware block operations, advanced modes, and extensive
  real-hardware validation.
- [Wedge80](https://github.com/graham-it/Wedge80) demonstrates a stable graphics
  entry surface, bitmap text and drawing primitives, automatic 16/64 KiB
  handling, and a broad mode matrix.
- [C128_splash_on_VDC](https://github.com/DarwinNE/C128_splash_on_VDC) is a
  compact C example of a 640x200 monochrome bitmap on a 16 KiB VDC, including
  register preservation and hardware-assisted clearing.
- [MatrixVDC](https://github.com/LukaszDziwosz/MatrixVDC) shows the value of
  sparse, incremental VDC updates for animation rather than redrawing an
  entire display.
- [The8BitTheory's VDC repositories](https://github.com/The8BitTheory) include
  reusable ideas such as bounded memory/register operations, display-boundary
  synchronisation, block fill/copy, soft-sprite-oriented transfers, and a
  practical 640x225 64 KiB application.

UDEKS uses these as references for hardware behaviour and API lessons only.
The display service will be independently implemented under
`GPL-3.0-or-later`; copied or adapted code, should it ever be justified, must
first have a compatible licence and receive file-level attribution.

## Bring-up diagnostic record

The first implementation publishes a 32-byte `VFBR` record at `$F0E0`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `VFBR` |
| 4 | 1 | Format (`3`; formats 1 and 2 preserve earlier milestones) |
| 5 | 1 | Starting (`1`), ready (`2`), or error (`$80 | code`) |
| 6 | 1 | Failure code |
| 7 | 1 | Bitmap stride (`80` bytes) |
| 8 | 1 | Height (`200` scanlines) |
| 9 | 1 | One-bit pixel format (`1`) |
| 10 | 1 | Detected VDC RAM in KiB |
| 11 | 1 | Saved register 25 |
| 12 | 1 | Active bitmap register 25 |
| 13–14 | 2 | Saved display address |
| 15–18 | 4 | Splash width in bytes, height, x-byte, and y |
| 19–20 | 2 | Splash VDC address (`$0406`, little-endian) |
| 21–22 | 2 | Verified byte-sum (`$5873`, little-endian) |
| 23 | 1 | Display and verified-font flags (`$7F`) |
| 24 | 1 | VDC colour register (`$0D`, black on yellow) |
| 25–26 | 2 | Font width (`5`) and height (`7`) |
| 27 | 1 | Rendered hardware-information lines (`9`) |
| 28–29 | 2 | Verified font-panel byte-sum |
| 30 | 1 | Consumed `HCAP` field mask (`$1F`) |
| 31 | 1 | Reserved; zero |

The service reads every uploaded splash byte back before making bitmap mode
visible. Every software-font scanline is also read back immediately after it is
written. `tools/framebuffer_decode.py` strictly validates all three record
versions so preserved qualification evidence remains readable.
