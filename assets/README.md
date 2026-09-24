# UDEKS artwork

`udeksdroid.png` is the high-resolution project logo. The two-colour XPM files
are prepared source variants for constrained targets:

- `udeksdroid-160.xpm` is the planned 160x160 VDC boot splash;
- `udeksdroid-64.xpm` is the compact icon variant.

Target-specific packed bitmaps are generated during the build and must not
replace these source assets. The C128 kernel does not decode PNG or XPM files
at runtime.
