# Compiled-C context-switch integration spike

This standalone Tasking 0.1 gate runs two real cc65 tasks through the relocated
page-zero/page-one strategy accepted by ADR 0008. Each task yields 32 times
from inside a live C frame while retaining a private volatile local array, a
16-bit accumulator, a hardware stack, and a cc65 software-stack pointer.

Build it in the reference container:

```sh
make bench-context-switch-c
```

The PRG loads at `$2800` and enters at `$2806` (`SYS 10246`). The 32-byte
`UCCS` result record is at `$F1A0`; state `2`, 64 switches, steps `32/32`, sums
`$1444/$4741`, and restored software-stack pointers `$70F0/$71F0` constitute a
pass. This is an integration spike, not yet the production `$FF16` path.
