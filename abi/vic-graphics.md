# VIC-IIe graphics service 0.1

The optional VIC-IIe display service is class `3`, instance `1`. Service start
only publishes capability and memory-layout state; it does not disturb the
40-column display. The bash-like `xinit` command explicitly requests the first
graphics mode while the VDC root console remains active and interactive.

`xinit` establishes 320x200 high-resolution bitmap mode with the following
physical-bank-1 layout:

| Range | Purpose |
|---|---|
| `$4000-$40FF` | Immutable backup of the common transfer page |
| `$4100-$413E` | Saved normal-pointer sprite template |
| `$4140-$417E` | Busy-pipe sprite template |
| `$417F-$5BFF` | Reserved VIC window space |
| `$5C00-$5FFF` | Screen/color-selection bytes and sprite pointers |
| `$6000-$7F3F` | 8,000-byte high-resolution bitmap |
| `$7F40-$7FBF` | Reserved bitmap tail |
| `$7FC0-$7FFF` | Sprite 0, a black X pointer |

The MMU RAM-configuration register exposes physical bank 1 to the VIC-IIe and
CIA2 selects the `$4000-$7FFF` 16 KiB VIC bank. A common-RAM gateway clears
the bitmap to yellow, initializes every screen byte for black-on-yellow hires
pixels, installs the pointer sprite, then restores the 8502 kernel-I/O profile
before touching VIC/CIA registers. The VDC console is unaffected.

The C128 also lets the 8502 port at `$0001` expose character ROM to the
VIC-IIe at relative `$1000-$1FFF` in every VIC bank. Because the screen matrix
at relative `$1C00` occupies that window, `xinit` temporarily disables the
overlay by setting port bit 2. `xinit -q` restores the bit to its previous
state. Without this C128-specific step the bitmap itself is read correctly,
but character-ROM bytes are mistaken for color-selection bytes and the screen
appears as a grid of colored blocks.

Drawing clients use a bank-0 shadow bitmap through bounded pixel, line,
rectangle, fill, and commit calls. Drawing marks dirty 256-byte pages; commit
uses a common-RAM staging page to transfer only those pages into physical bank
1. The partial final bitmap page ends at `$7F3F` and cannot overwrite the
reserved sprite. This is the first C display surface used by `xclock`.

The module additionally exposes a dedicated XOR-outline operation for the
window service. C publishes compact precomputed geometry records in common
RAM. A relocated 8502 assembly blitter switches to physical bank 1 once per
motion, removes the previous outline and draws the new outline directly in
VIC bitmap RAM, then restores bank 0. These transient pixels deliberately do
not modify the retained shadow; the window service performs one ordinary
repaint after release. The relocated blitter remains cached for consecutive
drag updates; dirty-page commits invalidate it because they reuse the common
gateway workspace.

The display service does not drive compositor or application policy. The
window manager and loader-managed graphical applications have independent
lifecycle ownership.

The initial pointer is a compact, unexpanded, high-resolution foreground
sprite, approximately half the original X design, at the center of the visible
area. The [pointer-input service](pointer-input.md) moves it with a 1351 mouse
on control port 1 or a joystick on control port 2. The earlier `xinit`
milestone proved mode ownership, bank placement, independent dual-display
output, and input before the drawing primitives were added.

While ownership has been handed to the Z80 worker or the 8502 compositor is
repainting, the display service replaces the X data in sprite 0 with the 24x21
pipe from `assets/24x21-pipe-sprite.png`. Repaint owns the indication across
nested Z80 leases, preventing each lease from briefly restoring the X. Only
the 63 sprite bytes are exchanged; sprite position, color, and VIC
configuration remain unchanged. Release starts a non-blocking three-frame
grace period, keeping short jobs and repaints visible without delaying either
CPU. New work during that period reclaims the existing pipe without copying
the sprite again. Each pointer swap invalidates the shared common-gateway
cache so the next drag reloads the outline blitter before executing it.

`xinit -q` terminates the graphics session. It disables the pointer sprite,
blanks VIC-IIe bitmap output, returns VIC RAM visibility to physical bank 0,
and leaves the service passive and ready for a later `xinit`. The VDC console
continues throughout both transitions.

## Diagnostic record

The 24-byte `VICG` record begins at `$F1B0`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `VICG` |
| 4 | 1 | Record format (`1`) |
| 5 | 1 | Starting (`1`), ready (`2`), active (`3`), or error |
| 6 | 1 | Failure code |
| 7 | 1 | Mode (`1` = 320x200 hires) |
| 8–9 | 2 | Background and pointer colors (yellow `7`, black `0`) |
| 10–12 | 3 | Pointer X low/high and Y (`172`, `140`) |
| 13 | 1 | Physical VIC RAM bank (`1`) |
| 14–15 | 2 | Bitmap and screen high bytes (`$60`, `$5C`) |
| 16 | 1 | Sprite pointer (`$FF`) |
| 17–18 | 2 | Successful `xinit` operations |
| 19–20 | 2 | Successful `xinit -q` operations |
| 21–22 | 2 | Successful dirty-page commit calls |
| 23 | 1 | Pointer owner (`0` = X, `1` = Z80, `2` = repaint, `3` = release delay) |
