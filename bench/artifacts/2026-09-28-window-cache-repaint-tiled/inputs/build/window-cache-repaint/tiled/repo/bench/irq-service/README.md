# Interrupt-service benchmark

This suite extends the initial interrupt qualification with three instrumented
handler paths on each CPU:

1. `minimal`: preserve the ISR ABI, acknowledge CIA1 Timer A, and return;
2. `kernel_tick`: also increment a 32-bit monotonic tick and signal an event;
3. `jump_table_dispatch`: call a validated no-op target through an indirect
   kernel jump-table entry.

Each variant runs 16 times with a 4,000-system-tick continuous Timer-A period.
Both implementations explicitly establish their interrupt mode (including
`IM 1` on Z80). Running Timer A is sampled high/low/high and retried if the
high byte changes, preventing a torn 16-bit timestamp at a low-byte rollover.
For every interrupt the suite records:

- underflow to the first timestamp after the admitted register prologue;
- the timestamp just before count bookkeeping, wait-loop patching, and the
  epilogue;
- underflow to the first timestamp after RTI and a patched fixed wait jump.

The decoder derives the instrumented handler interval, paired entry-to-resume
service cost, and pre-exit-to-resume tail. The paired service interval cancels
the variable emulator entry delay. Common instrumentation overhead remains in
the absolute figures; differences between variants isolate the incremental
kernel work more reliably.

The fixed wait loop makes return placement deterministic. Patching that loop is
test instrumentation and is performed after the pre-exit timestamp. It remains
included in the resume and tail figures.

```sh
make bench-irq-service
python3 tools/irq_service_decode.py run.vsf
```

The 8502 PRG starts with `SYS 10240`; the Z80 launcher starts with `SYS 10192`.
The result block is 320 bytes at `$F180` and uses the `IRQS` magic.

VICE 3.10 and `1986` have validated the corrected r2 harness. Physical-C128
runs are still required to qualify the absolute timing and production budgets.
