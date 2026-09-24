# Interrupt qualification probes

These probes are the prerequisite for interrupt-latency benchmarking. They
prove that each CPU can receive, identify, acknowledge, return from, and
repeatedly re-enable a CIA1 Timer-A interrupt using the memory configuration
planned for measurement.

The 8502 probe installs the native IRQ vector at `$FFFE`. The Z80 probe uses
IM1 and installs a jump at `$0038`. Its launcher selects 16 KiB of common RAM
at both the bottom and top of the address space before selecting normal Z80 RAM
through MMU CR bit 6. This keeps the IM1 entry, payload, stack, and result block
visible without the reset BIOS overlay.

Both timers use a continuous 1,000-system-cycle period and require 32 consecutive
interrupts. The result block begins at `$F180` and uses the `IRQP` magic. A run
is valid only when it reaches `COMPLETE`, reports the target count, reports no
unexpected interrupt sources, and observes CIA1 ICR `$81` on the first and last
interrupt.

Each handler also records 32 raw latency samples. A sample is the number of
one-megahertz system ticks between Timer A reloading at underflow and the first
timestamp after the handler has preserved its admitted register set. This is
therefore an executive-relevant entry-plus-prologue measurement, not the bare
CPU interrupt-accept cycle count. The running CIA counter is sampled with a
stable high/low/high sequence so a low-byte rollover cannot tear the value.

```sh
make bench-irq
python3 tools/irq_probe_decode.py run.vsf
```

The 8502 PRG loads at `$2800` and starts with `SYS 10240`. The Z80 PRG contains
an 8502 launcher at `$27D0` and starts with `SYS 10192`.

The decoder reports the raw sample distribution and its minimum, median, and
maximum. VICE 3.10 has qualified the corrected r2 images; real hardware remains
required before the figures can finalize ADR 0002.
