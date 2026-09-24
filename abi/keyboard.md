# UDEKS C128 keyboard API 0.1

The first input service is a resident, polled 8502 driver for the complete C128
keyboard. It scans the eight C64-compatible matrix columns through CIA1
`$DC00/$DC01` and the three C128-only columns through VIC-IIe `$D02F` and
`$DC01`. CAPS LOCK is sampled from active-low bit 6 of the 8502 port at `$0001`;
the locking 40/80 switch is sampled from MMU `$D505` bit 7.

Each scan saves and restores CIA1 port A, both CIA data-direction registers,
and `$D02F`. The unused column selector is held at `$FF` while the other matrix
is scanned. UDEKS therefore does not depend on the inherited KERNAL port setup
and does not leave keyboard or joystick-shared CIA pins reconfigured.
The scanner discards the first port-B sample after each column change before
using the second sample. The C service then requires the same complete matrix
row in two consecutive polls before publishing any transitions from that row.
Events and modifiers are derived from this debounced matrix, preventing switch
bounce or a settling glitch from becoming spurious terminal characters.

## Events

`include/udeks/keyboard.h` exposes a 16-entry FIFO of four-byte events:

```c
struct udeks_key_event {
    unsigned char type;
    unsigned char scan_code;
    unsigned char character;
    unsigned char modifiers;
};
```

Event type is press (`1`) or release (`2`). Scan codes are physical matrix
positions from 0 through 87, calculated as `column * 8 + sense_bit`; they do
not change with keyboard layout or modifiers. `character` is normalized ASCII
where the key has a text meaning, otherwise zero. Modifier bits report SHIFT,
CONTROL, Commodore, ALT, and the CAPS switch as observed in the same scan.

The US-layout provisional map provides lowercase letters without SHIFT,
uppercase letters with SHIFT or CAPS, their XOR combination for SHIFT+CAPS,
ASCII control letters with CONTROL, common shifted punctuation, Return/Enter,
backspace, tab, escape, and keypad digits. Shift+0 has no character on the C128
matrix and is therefore not normalized to a second `0`. Layout selection and
international maps belong above the raw scan service and remain future work.

`udeks_keyboard_event_get()` removes the oldest event and returns
`UDEKS_KEYBOARD_EMPTY` when the queue is empty. If the queue is full, new
transitions are dropped and the diagnostic drop counter advances. Typematic
repeat and debounce policy belong to the input/terminal policy layer rather
than the raw hardware event source.

## Diagnostic record

The service publishes a 48-byte `KEYB` record at `$F120`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `KEYB` |
| 4 | 1 | Format (`2`; format 1 is preserved pre-debounce evidence) |
| 5 | 1 | Starting (`1`), ready (`2`), or error |
| 6 | 1 | Failure code |
| 7 | 1 | Matrix columns (`11`) |
| 8 | 1 | Queue capacity (`16`) |
| 9–10 | 2 | Queue depth and dropped-event count |
| 11–14 | 4 | Last event type, scan code, character, and modifiers |
| 15–16 | 2 | CAPS and 40/80 switch states |
| 17 | 1 | Capabilities (`$1F`: base/extended matrix, port preservation, FIFO, debounce) |
| 18–23 | 6 | Poll, press, and release counters, little-endian |
| 24–34 | 11 | Current pressed-bit matrix snapshot |
| 35–37 | 3 | Last press scan code, character, and modifiers |
| 38–47 | 10 | Reserved |

The service is registered as input class `5`. Its descriptor supplies both
start and poll vectors; the bring-up kernel repeatedly invokes all registered
poll vectors after startup. Scheduler-driven cadence and interrupt-backed
queues will replace this cooperative loop later without changing key events.

The matrix and register model follows the
[Commodore 128 Programmer's Reference Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf).
The independent [C128 keyboard-scan table](https://www.hydrophilic.net/CBM/C128/Keyboard_Scan.html)
is used as a cross-check for physical positions and the requirement to deselect
the unused matrix.

The local `1986` emulator exposes the complete 11-line matrix, including
VIC-IIe `$D02F` selection, the active-low CAPS/ASCII-DIN switch, and host
mappings for the C128-only keys. VICE and real C128 hardware remain independent
qualification targets for electrical timing and physical-keyboard behavior.
