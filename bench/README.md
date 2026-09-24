# Initial CPU benchmark harness

This directory contains the first executable comparison between the C128's
8502 and Z80. Both images compile `common/runner.c` and `common/workloads.c`
from the same source. CPU-specific assembly supplies startup and access to CIA1
Timer B.

Build both images with:

```sh
make bench
```

The provisional harness selects RAM bank 0 with the I/O window visible,
disables interrupts, and assumes these addresses are available:

| Range | Purpose |
|---|---|
| `$2000` onward | CPU-specific benchmark image |
| `$E000-$E0FF` | deterministic source data |
| `$E100-$E1FF` | destination data |
| `$EFF0` downward | Z80 stack |
| `$F100-$F17F` | fixed result block |
| below `$D000` | cc65 software stack |

These are bootstrap addresses, not the permanent UDEKS memory map. The launcher
must establish the mapping before entering either image. Byte 6 of the result
block is reserved for a launcher-supplied configuration identifier and is
preserved by the suite.

The initial configuration identifiers are 1 for an 8502 1 MHz run, 2 for an
8502 2 MHz run, and 3 for a stock-timing Z80 run. Zero means that the launcher
did not identify the configuration.

Both targets also produce a PRG wrapper. The 8502 wrapper can be loaded at its
embedded address and entered with `SYS 8192`. The Z80 wrapper includes a
32-byte 8502 launcher at `$1FE0`; enter it with `SYS 8160`. It writes
`JP $2000` at `$FFED-$FFEF` and enters the C128 ROM-installed handoff at
`$FFD0`. The Z80 then resumes after its reset-time ownership transfer and jumps
to the payload. This is a bootstrap technique, not the final UDEKS handoff ABI.

## Current cases

The format contains an empty-call calibration, fill, copy, repeated checksum,
branch-heavy control flow, and 16-bit arithmetic. Workload outputs are checksums
validated independently by `tools/bench_decode.py`.

The suite uses CIA1 Timer B as a free-running 16-bit down counter clocked from
the system clock. It disables interrupts but does not configure the MMU, VIC,
or CPU speed. Those conditions belong to the launcher so the identical payload
can be exercised in multiple modes.

The timer wraps after 65,536 ticks. Each adapter clears and checks CIA1's Timer
B underflow flag; it writes `$FFFF` as an overflow sentinel, which the decoder
rejects. Current loop sizes leave additional headroom for slower display modes.

## Reading results

Given a 64 KiB memory dump or a snapshot produced by the `1986` emulator:

```sh
python3 tools/bench_decode.py memory.bin
python3 tools/bench_decode.py --json run.vsf
```

For a file containing only the 128-byte block, the same command automatically
uses offset zero. The decoder rejects incomplete runs, malformed records, and
wrong workload checksums.

This slice measures compiler-generated throughput only. CPU ownership transfer,
interrupt latency, task-context save/restore, display pressure, PAL/NTSC runs,
and real-hardware capture remain required by `docs/BENCHMARKS.md` before ADR
0002 can be accepted.

The first validated emulator-only samples are under `results/`. They are
deliberately labeled preliminary and must not be cited as the ADR 0002 outcome.

The separate [`irq/`](irq/) harness qualifies native 8502 and Z80 IM1 delivery
and records entry-through-prologue latency samples.

The [`irq-service/`](irq-service/) suite follows that qualification with
minimal, kernel-tick, and jump-table-dispatch service paths through RTI.

The [`context/`](context/) suite measures CPU-only, compiler-complete, and
full-architecture task-context save/restore primitives.

The [`kernel/`](kernel/) suite compares C dispatch and event queues alongside
assembly MMU, CIA, and VDC register transactions.

The [`handoff/`](handoff/) suite runs both processors in one image and measures
bare ownership round trips and full ABI mailbox transactions in both directions.

The [`offload/`](offload/) suite compares local assembly operations with
complete cross-CPU copy, checksum, and transform requests from 16 bytes through
2 KiB, deriving the first profitable size in each direction.

Exact PRGs used for published result sets are retained under [`artifacts/`](artifacts/).
Each dated bundle contains hashes, entry commands, result ranges, and decoder
mapping for later VICE and physical-hardware runs. Generated files in `build/`
remain disposable; preserved benchmark inputs do not.
