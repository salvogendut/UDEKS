# UDEKS artwork

`udekspipe.png` is the high-resolution pipe-and-name mark. The root
`UDEKS.png` adds the expanded project name and is the README logo. The
two-colour pipe XPM files are prepared source variants for constrained targets:

- `udekspipe-64.xpm` is the active upper-left VDC boot mark;
- `udekspipe-160.xpm` is the larger layout variant.

`bootscreen.png` is the authoritative high-resolution composition reference:
a logo rail at the left and a bordered boot console at the right. The VDC
implementation adapts its hierarchy and spacing to the native 640x200 one-bit
surface while reporting only subsystems the current kernel actually provides.

The earlier `udeksdroid` PNG and XPM variants remain as project-history source
artwork but are no longer linked into the boot image.

Target-specific packed bitmaps are generated during the build and must not
replace these source assets. The C128 kernel does not decode PNG or XPM files
at runtime. Run `make framebuffer-assets` to generate the row-major, MSB-first
VDC bitmap under `build/assets/`.
