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

The C text console predates this compositor and remains the recovery display
service. The framebuffer is now the first substantial graphics C module; the
next console milestone will route ordinary console output through its public
surface API rather than retaining a separate VDC layout owner.

## First implementation slice

The baseline mode transition, linked splash upload, sampled readback, and
black-on-yellow activation are implemented and qualified on both VDC RAM
tiers. A 16,000-byte system-RAM backing surface, clipped drawing primitives,
software text, dirty-span tracking, bounded assembly flushing, and a
single-client ownership lease now form the first public graphics API.

The initial display service deliberately targets the conservative mode that
works with either VDC memory tier: 640x200, one bit per pixel, 80 bytes per
scanline. Its first public operations are deliberately small:

1. acquire and release the display;
2. plot a pixel, draw a clipped horizontal span, and fill a clipped rectangle;
3. draw one software glyph or a string at pixel coordinates;
4. track dirty byte spans per scanline and flush only those spans;
5. retire a span only after its bounded assembly transfer completes.

Cold boot deliberately uses a different repaint policy. UDEKS blanks the VDC
before touching its RAM, builds the complete root-window image in system RAM,
and sends all 16,000 bytes through one auto-incrementing assembly transfer.
The display is enabled only after upload and splash verification, so no
top-to-bottom border or text construction is exposed. Interactive clients
continue to use incremental dirty spans rather than uploading a full screen.

The initial API uses a single global ownership lease; task-associated opaque
handles follow once scheduler identities exist. Mode tables, VDC addresses,
and register numbers remain private to the service. More ambitious modes such
as 640x225, interlace, per-cell colour, and page flipping are later capability-
gated extensions rather than assumptions made by the baseline API.

The first end-to-end client is the boot splash. A host-side build tool converts
`assets/udekspipe-64.xpm` and `assets/udekusu-64.xpm` into packed VDC
scanlines while preserving their PNG sources and the larger pipe XPM as source
artwork. The service places the compact 64x64 pipe mark at the upper left and
the 64x21 Japanese UDEKS wordmark directly below it. Per-span readback is not
used by the production renderer; the splash region is sampled back as the boot
transfer's integrity check. No PNG decoder belongs in the kernel. The
160x160 pipe variant remains available for future layouts with more room. The
present transitional service runs after the
text console and takes final display ownership; the software-font milestone
removes that split ownership by making console output a framebuffer client.

The second client installs an original software-defined 5x7 font in 8x8 cells.
Following `assets/bootscreen.png`, the pipe occupies a left rail and a 528x184
bordered boot console occupies the right. Its 64x21 text grid and cursor are now
retained independently of VDC pixels as the first root-window state. Seventeen
populated lines provide the UDEKS identity and version, `HCAP` hardware results,
accurate executive/worker state, explicit deferred storage/filesystem services,
and a static future-shell prompt. A separate boot-content producer populates
the model and the VDC backend renders it. The display client must not touch
probe registers itself. This makes state retention, glyph rendering,
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
| 4 | 1 | Format (`8`; formats 1–7 preserve earlier milestones) |
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
| 19–20 | 2 | Splash VDC address (`$03C2`, little-endian) |
| 21–22 | 2 | Verified byte-sum (`$5873`, little-endian) |
| 23 | 1 | Display flags (`$3F`: RAM cleared, uploaded, splash verified, active, state saved, font drawn) |
| 24 | 1 | VDC colour register (`$0D`, black on yellow) |
| 25–26 | 2 | Font width (`5`) and height (`7`) |
| 27 | 1 | Rendered boot-console lines (`17`) |
| 28–29 | 2 | Retained boot-console character checksum |
| 30 | 1 | Consumed `HCAP` field mask (`$1F`) |
| 31 | 1 | Graphics API flags (`$3F`: backing, primitives, text, dirty flush, ownership, retained root text) |

The service reads every uploaded splash byte back before making bitmap mode
visible. The rest of the production transfer relies on the bounded ready poll
for every byte and does not pay for a second 16,000-byte read pass.
`tools/framebuffer_decode.py` strictly validates all eight record versions so
preserved qualification evidence remains readable.
