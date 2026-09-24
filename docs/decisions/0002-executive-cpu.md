# ADR 0002: Executive CPU selection

- Status: proposed
- Date: 2026-09-23

## Context

The C128 contains an 8502 and a Z80, but only one owns the shared system bus at
a time. Either processor can in principle host the UDEKS executive while the
other executes bounded jobs. They differ in instruction timing, interrupt and
context state, compiler/runtime costs, memory-access idioms, I/O access, and
behavior under the C128's display modes.

Commodore's conventional use of the 8502, the Z80's reset-time ownership, raw
clock labels, and toolchain familiarity are insufficient reasons to make a
permanent architectural choice.

There is currently an evidence asymmetry. The official C128 Programmer's
Reference Guide teaches the 8502-facing interrupt, memory, graphics, sound, and
I/O model throughout its native-mode chapters. Its Z80 material is principally
the CP/M environment and BIOS interface, and it explicitly assumes prior Z80
knowledge. The preserved C128 CP/M BIOS source is valuable counter-evidence,
but also shows C128-specific I/O paths that coordinate with 8502 routines. This
likely lowers implementation risk for an 8502 executive; the decision process
must test and document that inference rather than treating it as benchmark
throughput.

## Candidates

1. **8502 executive, Z80 secondary engine.** This may favor compact interrupt
   mechanisms, direct memory-mapped I/O, page-zero use, and C128-native software
   conventions.
2. **Z80 executive, 8502 secondary engine.** This may favor Z80 register and
   instruction capabilities, SDCC-generated workloads, and direct continuation
   from the CPU that owns the machine at reset.

These are hypotheses to measure, not conclusions.

## Decision process

Use the reproducible suite specified in [the benchmark plan](../BENCHMARKS.md).
Compare compiled C and handwritten assembly under VDC-only, VIC-active, and
dual-display conditions, including kernel primitives, interrupt behavior,
context switching, device access, memory operations, and handoff in both
directions.

Development runs must agree sufficiently across `1986` and VICE to identify
emulator-specific behavior. Final acceptance requires real-C128 measurements.
The decision will emphasize executive workloads and system-level constraints,
not peak throughput in one loop.

Documentation quality and proven C128-specific implementations are scored as
engineering risk. They may break a close technical result or identify a
correctness blocker, but documentation volume alone cannot override measured
behavior.

## Preliminary evidence — 2026-09-24

The first shared-C suite has run in the `1986` emulator using CIA1 Timer B.
Three runs per configuration were identical and all workload checksums passed.
At stock Z80 timing, SDCC output completed every substantive case faster than
cc65 output running on the 8502 at 2 MHz:

| Workload | 8502 2 MHz | Z80 stock | 8502 / Z80 |
|---|---:|---:|---:|
| fill | 18,758 | 12,610 | 1.49× |
| copy | 20,613 | 15,682 | 1.31× |
| checksum | 11,313 | 6,974 | 1.62× |
| control flow | 14,003 | 11,076 | 1.26× |
| 16-bit arithmetic | 14,130 | 4,290 | 3.29× |

The Z80 baseline explicitly used the emulator's ratio of two T-states per
one-megahertz bus cycle (`double_z80_frequency = 0`, `tinker = 0`). An
intentional doubled-frequency control run halved every substantive tick count
exactly and was excluded from the table, confirming that the reported column
is the stock effective 2 MHz Z80 rather than the 8 MHz modification.

The linked suite occupied 1,940 bytes on the 8502, including startup and
selected cc65 runtime helpers. The Z80 link map reported 633 bytes of code;
its 8 KiB raw artifact is a padded transport window and is not its code size.

This is evidence that the Z80 remains a serious executive candidate, not a
decision in its favor. The suite does not yet measure interrupt latency, full
task-context switching, syscall dispatch, MMU transitions, device drivers,
display pressure, or complete handoff cost. It has not yet run in VICE or on
real hardware. See the [raw samples and provenance](../../bench/results/2026-09-24-1986-initial.md).

The accumulated emulator evidence is therefore deliberately split:

- **Z80 measured advantages:** compiled-C speed, linked size, and the admitted
  compiler/full task-context transfer.
- **8502 measured advantages:** interrupt service, MMU/CIA/VDC access, the
  event queue, and the tested assembly copy/checksum/transform mechanisms at
  2 MHz.
- **8502 implementation-risk advantage:** C128-specific interrupt, MMU, I/O,
  and example-code documentation.
- **Unresolved deciding evidence:** display coexistence, independent-emulator
  agreement, and real-hardware verification.

### Initial interrupt probe

A subsequent CIA1 Timer-A probe qualified both candidate interrupt routes in
`1986`. Each route received and acknowledged 32 consecutive interrupts; CIA1
ICR was `$81` at both boundaries and no unexpected source was observed. Three
runs per configuration were identical.

| Configuration | Minimum | Median | Maximum | Spread |
|---|---:|---:|---:|---:|
| 8502, 1 MHz | 25 | 53.5 | 82 | 57 |
| 8502, 2 MHz | 13 | 41.5 | 74 | 61 |
| Z80, stock timing | 57 | 87 | 117 | 60 |

Values are one-megahertz system ticks from the CIA underflow through interrupt
acceptance and an ABI-safe entry prologue to the first timer read. The 8502
path preserves hardware-stacked P/PC plus software-stacked A, X, and Y. The Z80
path uses IM1, with hardware-stacked PC and software-stacked AF, BC, DE, HL, IX,
and IY; its alternate registers and I/R are not admitted by this ISR ABI.

The figures are not yet evidence of physical latency. Every configuration
shows a deterministic stair-step distribution with roughly the same 60-tick
spread, indicating emulator interrupt-service granularity. They also compare
the proposed executive prologues rather than identical byte counts. They do,
however, prove that Z80 IM1 works through the intended common-RAM/MMU layout and
that neither candidate is blocked from CIA interrupt ownership. See the
[raw interrupt results](../../bench/results/2026-09-24-1986-irq-latency.md).

### Interrupt-service cost

The follow-up suite ran minimal acknowledgement, 32-bit kernel-tick plus event,
and indirect jump-table dispatch paths. It records paired timestamps inside a
single interrupt so the variable emulator entry delay cancels from the
post-prologue-to-resume interval. All three repetitions were identical and all
48 source and work-result checks passed per configuration.

| Path | 8502 1 MHz | 8502 2 MHz | Z80 stock | Z80 / 2 MHz 8502 |
|---|---:|---:|---:|---:|
| minimal | 247 | 123 | 425 | 3.46× |
| kernel tick | 268 | 134 | 475 | 3.54× |
| jump-table dispatch | 274 | 137 | 466 | 3.40× |

Values are median one-megahertz system ticks from the first post-prologue
timestamp through resumption after RTI. The 8502 kernel-tick and dispatch work
added 11 and 14 ticks at 2 MHz over its minimal path. The corresponding Z80
increments were 50 and 41 ticks. The stock Z80 configuration again used two
T-states per system tick with `double_z80_frequency = 0` and `tinker = 0`.

This strengthens the technical case for an 8502 executive: in the current
assembly implementations, its interrupt-service paths are about 3.4–3.5 times
less expensive even though the earlier SDCC workloads favored the Z80. It is
not conclusive because the ISR contracts intentionally preserve different
register sets, instrumentation is included, and the suite has not run in VICE
or on hardware. Task-context transfer is evaluated separately below.
See the [raw service results](../../bench/results/2026-09-24-1986-irq-service.md).

### Task-context save and restore

The context suite executes 64 save/restore primitives per sample, subtracts a
matching empty call/loop sample, and validates preserved registers and runtime
state before timing. Three runs of eight samples per variant were identical.

| Context contract | Bytes/task | 8502 1 MHz | 8502 2 MHz | Z80 stock |
|---|---:|---:|---:|---:|
| CPU core | 8502: 7; Z80: 16 | 48 | 24 | 116 |
| compiler-complete | 8502: 33; Z80: 16 | 412 | 206 | 116 |
| full admitted architecture | 8502: 33; Z80: 24 | 412 | 206 | 180 |

Values are one-megahertz system ticks per save/restore operation after empty
overhead subtraction. The 8502 compiler path uses an intentionally unrolled
copy of all 26 bytes declared by cc65 as zero-page runtime state. The Z80
compiler path preserves primary AF/BC/DE/HL, IX, IY, PC, and SP; its full path
also preserves AF'/BC'/DE'/HL'. I, R, IFF, and interrupt mode are kernel-global
under this provisional ABI.

This evidence is split. The 8502 CPU-only frame is extremely cheap, but cc65's
task-local zero-page runtime raises its practical cost to 206 ticks and 33
bytes. The stock Z80 needs 116 ticks and 16 bytes for SDCC-complete state, or
180 ticks and 24 bytes when applications may use the alternate bank. Thus the
Z80 wins context transfer even after optimizing the 8502 mechanism, while the
8502 wins interrupt service. Neither result subsumes the other; a production
preemption path combines both and still requires an agreed task ABI. See the
[raw context results](../../bench/results/2026-09-24-1986-context.md).

### Kernel dispatch, queues, and device access

The next suite combines identical C sources for dispatch and event queues with
CPU-specific assembly for validated MMU, CIA, and VDC transactions. Three runs
per configuration were identical and every independent checksum or transaction
count passed.

| Case | 8502 1 MHz | 8502 2 MHz | Z80 stock | Faster candidate |
|---|---:|---:|---:|---|
| direct switch dispatch | 36,979 | 18,489 | 13,634 | Z80, 1.36× |
| indirect table dispatch | 61,044 | 30,522 | 20,110 | Z80, 1.52× |
| event queue, 32 round trips | 33,517 | 16,759 | 22,524 | 8502, 1.34× |
| MMU, 128 transactions | 2,510 | 1,255 | 4,168 | 8502, 3.32× |
| CIA, 128 transactions | 2,510 | 1,255 | 4,174 | 8502, 3.33× |
| VDC, 128 transactions | 4,294 | 2,147 | 10,302 | 8502, 4.80× |

Values are one-megahertz system ticks. The MMU and CIA loops write back the
value first read and verify every readback. The VDC loop waits for readiness,
selects register 18, and completes a data read for every transaction. The Z80
was again at stock effective 2 MHz timing.

The result confirms two competing effects. SDCC generates faster dispatch code,
but the 8502 is substantially better at direct C128 device traffic and also
wins this queue implementation. This raises the likely system cost of a Z80
executive that delegates device work to the 8502; bidirectional handoff and
end-to-end offload thresholds are now essential evidence. See the
[raw kernel results](../../bench/results/2026-09-24-1986-kernel.md).

### Bidirectional ownership and mailbox cost

The handoff suite executes 64 real `$D505` round trips with either processor as
requester. Its bare path retains only minimal dispatch and a validated peer
counter; its full path publishes and validates an ABI 0.1 NOP request and
response. Three runs per configuration were identical.

| Requester → responder | Path | 8502 1 MHz | 8502 2 MHz |
|---|---|---:|---:|
| 8502 → Z80 | bare round trip | 95.172 | 88.531 |
| 8502 → Z80 | mailbox NOP | 434.266 | 373.125 |
| Z80 → 8502 | bare round trip | 65.453 | 45.969 |
| Z80 → 8502 | mailbox NOP | 403.562 | 323.062 |

Values are one-megahertz system ticks per round trip, which contains two
ownership changes. The stock Z80 setting was explicitly retained with
`double_z80_frequency = 0` and `tinker = 0`. At 2 MHz, mailbox processing adds
284.594 ticks above the bare path for an 8502 requester and 277.094 for a Z80
requester.

The no-work handoff measurement by itself does not answer the offload question. A
Z80 executive begins an 8502 device request about 323 ticks behind, while an
8502 executive begins a Z80 computational request about 373 ticks behind.
The following end-to-end sweep shows where these particular workers earn back
that fixed cost. See the
[raw handoff results](../../bench/results/2026-09-24-1986-handoff.md).

### End-to-end offload thresholds

The next suite compares local handwritten-assembly execution with a complete
mailbox request, two ownership changes, worker execution, and response
validation. It sweeps 16 bytes through 2 KiB for copy, unsigned 16-bit checksum,
and a deterministic XOR/rotate transform. Three runs per configuration were
byte-identical and all 96 paths validated.

| Executive | Worker | 8502 speed | Copy crossover | Checksum crossover | Transform crossover |
|---|---|---:|---:|---:|---:|
| 8502 | stock Z80 | 1 MHz | 128 bytes | none through 2 KiB | none through 2 KiB |
| Z80 | 8502 | 1 MHz | none through 2 KiB | 256 bytes | 128 bytes |
| 8502 | stock Z80 | 2 MHz | none through 2 KiB | none through 2 KiB | none through 2 KiB |
| Z80 | 8502 | 2 MHz | 256 bytes | 32 bytes | 32 bytes |

At 2 KiB with the 8502 at 2 MHz, a Z80 executive improves from 24,682 to
16,939 ticks by delegating copy, from 53,426 to 24,117 for checksum, and from
61,624 to 23,087 for transform. An 8502 executive is faster locally in all
three cases throughout the tested range.

This strengthens the 8502 case for assembly kernel mechanisms while preserving
the earlier contrary evidence from compiled C. It also shows that a secondary
engine needs operation- and mode-specific thresholds; “large job” is not a
sufficient dispatch policy. See the
[raw offload results](../../bench/results/2026-09-24-1986-offload.md) and the
[preserved PRGs](../../bench/artifacts/2026-09-24/README.md).

## Evidence sources

- [Commodore 128 Programmer's Reference Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf)
- [Preserved Commodore 128 CP/M Plus BIOS source](https://www.devili.iki.fi/Computers/Commodore/C128/CPM/)

## Decision

Open. Neither CPU is designated the permanent executive yet. The existing
8502 and Z80 scaffold images are experimental bring-up vehicles, not an
architecture commitment.

## Consequences while proposed

- Scheduler and permanent context ABI work is blocked by this decision gate.
- Boot and mailbox experiments must support handoff in both directions.
- Policy code should remain portable C where practical.
- CPU-specific mechanisms may be prototyped, but neither implementation is the
  reference solely because it was written first.
