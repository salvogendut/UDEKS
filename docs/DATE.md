# `date` and the shared C128 clock

`/bin/date` is a standalone 8502 UDEX program. With no arguments it prints the
shared 24-hour time as `HH:MM:SS`. It accepts the C128 BASIC `TI$` spelling or
a colon-separated form:

```text
date 143025
date 14:30:25
date -s 14:30:25
```

Setting the time uses the public `$CF40` syscall rather than touching CIA1
from the program. The time service updates CIA1 TOD, its common `TIME` record,
and BASIC's 24-bit `TI` jiffy counter at `$A0-$A2`. `xclock` reads the same
service and therefore reflects the new value on its next service poll.

The C128 has no battery-backed real-time clock, so this is time since boot or
the last explicit setting, not persistent calendar time. No date or timezone
is represented yet.
