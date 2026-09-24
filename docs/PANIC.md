# Panic path

The resident 8502 core owns a last-resort panic path implemented entirely in
assembly. It masks interrupts, publishes diagnostics in common RAM, makes one
bounded best-effort VDC write, and halts. It does not call C or use the cc65
software stack.

`udeks_panic()` receives one byte in `.A` using the cc65 fastcall convention.
Codes `$20`–`$2F` identify service-startup failures; the low nibble is the
registry failure code. The first qualified case is `$22`, an invalid service
descriptor magic.

The path writes `UDEKS PANIC xx` at VDC screen address `$0000`, where `xx` is
the hexadecimal panic code. Every VDC readiness wait is bounded by one 16-bit
counter wrap. Even if the VDC is absent or wedged, the common-RAM record is
published and the machine reaches the halt loop.

## Diagnostic record

The 16-byte record at `$F0B0` has this layout:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `PANI` |
| 4 | 1 | Record format (`1`) |
| 5 | 1 | Published state (`2`), written last |
| 6 | 1 | Panic code |
| 7 | 1 | CPU (`0` = 8502) |
| 8 | 1 | 8502 processor status after interrupt masking |
| 9 | 1 | MMU configuration register |
| 10 | 1 | MMU mode register |
| 11 | 1 | VDC flags: bit 0 attempted, bit 1 completed |
| 12 | 4 | Reserved; zero |

The mode register's unused high bit differs between the current emulators, so
the decoder validates only the documented 8502/native-mode bits.

`make panic-probe` builds a native D71 whose console descriptor deliberately
has bad magic. This qualification fixture exercises the real registry failure,
kernel escalation, assembly panic record, VDC message, and final halt path.
It is not a release image.
