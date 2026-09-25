# UDEKS time service 0.1

The resident time service is machine-policy class `4`, instance `1`. It reads
CIA1's 6526 time-of-day clock as a coherent latched value, publishes binary
24-hour fields to applications, and mirrors the value into the C128 BASIC
`TI` counter at `$A0-$A2`. The counter uses the BASIC/KERNAL convention of 60
jiffies per second and rolls with the 24-hour TOD value. CIA TOD has only
tenth-second resolution, so the mirror advances in six-jiffy units.

The capability service selects the PAL 50 Hz or NTSC 60 Hz TOD divider.
Writing the existing tenths value starts a TOD clock left stopped by reset
without inventing a wall-clock value. The stable `clock_set` syscall updates
CIA TOD and `TI` together; `/bin/date` accepts either BASIC `TI$` form
`HHMMSS` or the friendlier `HH:MM:SS` form. `xclock` reads this same service,
so it follows a `date` change on its next poll.

Applications use `udeks_time_now()` and never access CIA registers directly.
The C128 has no battery-backed clock, so the published value is the machine's
TOD value rather than persistent civil time.

The 24-byte `TIME` record begins at `$F200`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0–3 | 4 | ASCII magic `TIME` |
| 4–7 | 4 | Format, state, error, and CIA1-TOD source |
| 8–11 | 4 | Binary hour, minute, second, and tenth |
| 12–15 | 4 | Reserved |
| 16–19 | 4 | Poll and changed-second counters |
| 20–23 | 4 | Reserved |
