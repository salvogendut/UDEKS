# 8502 clock policy

UDEKS boots and remains at the C128's stock 1 MHz rate by default. Native VDC
text mode makes the root console responsive without sacrificing the VIC-IIe,
so both display engines can remain active. Hardware capability discovery may
therefore observe the VIC raster and later graphics services can use its
directly addressable video RAM.

The qualified 2 MHz transition is retained as an optional machine-policy
mechanism. A workload may request it only when policy permits the VIC display
to be blanked; it is not in the production boot service table.

The transition is an assembly mechanism with a service-class-4 descriptor. It
performs this ordered sequence when explicitly registered or invoked:

1. require a ready `HCAP` record;
2. clear display-enable bit 4 in `$D011` and verify readback;
3. clear test bit 1 and set fast-clock bit 0 in `$D030`;
4. verify that `$D030 & $03` is exactly `$01`;
5. publish the completed `CLK2` record.

The VIC-IIe remains responsible for DRAM refresh, but it is unavailable as a
display processor while fast mode is selected. The VDC remains independent and
active. I/O accesses are synchronized to the 1 MHz peripheral clock, so 2 MHz
primarily accelerates CPU-side composition and memory work rather than doubling
raw VDC-port throughput. A future fast-clock lease must provide a paired,
validated return to 1 MHz and arbitrate that clock change centrally.

## Diagnostic record

The 16-byte `CLK2` record at `$F100` is:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `CLK2` |
| 4 | 1 | Format (`1`) |
| 5 | 1 | Starting (`1`), ready (`2`), or error (`$80 | code`) |
| 6 | 1 | Failure code |
| 7 | 1 | `$D030` before transition |
| 8 | 1 | `$D030` verified after transition |
| 9 | 1 | `$D011` before VIC blanking |
| 10 | 1 | `$D011` verified after VIC blanking |
| 11 | 1 | Requested frequency in MHz (`2`) |
| 12 | 1 | Flags: capability ready, VIC blanked, fast-clock readback |
| 13 | 3 | Reserved; zero |

`tools/clock_decode.py` accepts a raw record, full RAM image, or VICE snapshot
and rejects a visible VIC, active VIC test bit, or missing 2 MHz readback.
The preserved [VICE/`1986` qualification](../bench/results/2026-09-24-clock-2mhz/README.md)
records identical register readback across both VDC memory tiers and the
measured cold-boot improvement.

The ordered transition follows the
[Commodore 128 Programmer's Reference Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf),
which specifies blanking the VIC display before setting `$D030` bit 0 and
requires bit 1 to remain clear in normal operation.
