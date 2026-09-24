# UDEKS time service 0.1

The resident time service is machine-policy class `4`, instance `1`. It reads
CIA1's 6526 time-of-day clock as a coherent latched value and publishes binary
24-hour fields to applications. The capability service selects the PAL 50 Hz or
NTSC 60 Hz TOD divider. Writing the existing tenths value starts a TOD clock
left stopped by reset without inventing a wall-clock value.

Applications use `udeks_time_now()` and never access CIA registers directly.
The C128 has no battery-backed clock, so the published value is the machine's
TOD value rather than persistent civil time.

The 24-byte `TIME` record begins at `$F200`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0–3 | 4 | ASCII magic `TIME` |
| 4–7 | 4 | Format, state, error, and CIA1-TOD source |
| 8–11 | 4 | Binary hour, minute, second, and tenth |
| 12–15 | 4 | Raw latched 6526 TOD registers |
| 16–19 | 4 | Poll and changed-second counters |
| 20 | 1 | PAL (`1`) or NTSC (`2`) timing |
| 21–23 | 3 | Reserved |
