# Pointer input service 0.1

UDEKS assigns the two C128 control ports permanently for its native graphical
environment:

| Physical port | Device | Hardware path |
|---|---|---|
| Control port 1 | Commodore 1351 proportional mouse | SID `$D419/$D41A` plus CIA1 port B buttons |
| Control port 2 | Digital joystick | CIA1 port A low five bits |

CIA1 port A bits 7–6 are held at `%01` (`$40`) between keyboard scans, which
selects the port-1 POT pair and leaves port 2 available for digital input.

The resident input-class service combines both sources into one bounded
320x200 pointer coordinate. Applications consume the normalized pointer state;
they do not read CIA or SID registers and do not need separate mouse and
joystick code. Simultaneous movement is combined, the joystick contributes a
five-pixel step per video frame after one-sample digital debounce, and
coordinates are clipped so the compact sprite remains visible.

The 1351 driver implements the manual's modulo-64 delta algorithm. It removes
the POT noise bit, ignores one-count jitter, divides useful deltas by two, and
reverses the Y axis. Control-port sampling temporarily makes both CIA1 ports
inputs while reading port-1 buttons, then restores the service-owned port
configuration. The keyboard scanner independently saves and restores the same
registers.

Pointer sampling is paced once per video frame by a two-phase VIC-IIe raster
interrupt. At raster 200 the driver selects the port-1 POT pair and closes the
keyboard gate. At raster 226 it reads the converted POT values, decodes the
modulo position immediately, and reopens keyboard polling. This exceeds the
1351 manual's 1.6 ms SID conversion-settling requirement without busy-waiting.
More importantly, synchronous repaint and Z80 service work can delay a client
of the pointer state but cannot delay or reorder the modulo samples themselves.
Fast motion therefore cannot alias into a reversal or become stuck behind a
stale cooperative sample. The first two stable samples calibrate the driver and
cannot move the pointer, preventing startup drift on an empty port.

The IRQ vector first enters an 11-byte trampoline in common RAM at
`$FFC5-$FFCF`. It saves the interrupted MMU profile and selects kernel bank 0
with I/O visible before entering the resident assembly driver. A second common
stub at `$F909-$F90D` restores the exact profile and returns. Consequently the
sampler remains safe while a graphics gateway has bank-1 bitmap RAM mapped at
`$D000-$DFFF`; the interrupted gateway resumes with its original mapping.

Because the C128 keyboard and control ports share CIA1 pins, keyboard scans are
suppressed during the POT conversion window and while a joystick direction,
joystick fire, or mouse button is active. Each short matrix scan also masks IRQs
to close the race between the C-level gate check and the hardware scan. For the
joystick activity check, the opposite half of the keyboard matrix is probed at
both high and low. Only a low bit persistent in both phases is treated as a
grounded control-port switch; keyboard-induced lows vary with the drive phase.
Releasing all control-port switches re-enables keyboard polling automatically.

The electrical model and settling rule follow the
[Commodore 1351 Mouse User's Manual](https://retroisle.com/commodore/c64128/OriginalDocs/1351mousev11.php)
and the CIA mapping in the
[Commodore 128 Programmer's Reference Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf).
The maintained [cc65 1351 driver](https://github.com/cc65/cc65/blob/master/libsrc/c64/mou/c64-1351.s)
is an independent cross-check for modulo motion and keyboard isolation.

## Diagnostic record

The 32-byte `PTRI` record begins at `$F1D0`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `PTRI` |
| 4–6 | 3 | Format (`1`), state, and failure code |
| 7 | 1 | Capabilities: mouse 1, joystick 2, 1351, raster-IRQ paced |
| 8–10 | 3 | Pointer X (little-endian) and Y |
| 11 | 1 | Buttons: mouse left/right and joystick fire |
| 12–15 | 4 | Raw joystick, mouse buttons, POTX, and POTY |
| 16–17 | 2 | Last signed X/Y motion |
| 18–25 | 8 | IRQ sample, movement, mouse-event, and joystick-event counters |
| 26–27 | 2 | POT conversion phase and active-source mask |
| 28–31 | 4 | Reserved |
