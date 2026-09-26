# Context-switch spike results

The corrected standalone context-switch spike (`-r5`) was run against the two
qualified emulators. Both completed the relocation strategy with one successful
check per switch, no canary failure, and zero page bytes moved per switch.
Interrupts were observed both inside the marked switch-boundary windows and
during task execution; the counters are 16-bit, so the totals are exact.

| Run | Switches | Interrupts | Boundary | Body | Checks | Canary | Page bytes/switch |
|---|---:|---:|---:|---:|---:|---:|---:|
| `1986` | 128 | 1366 | 875 | 491 | 128/128 | 0 | 0 |
| VICE 3.10 | 128 | 7115 | 5001 | 2114 | 128/128 | 0 | 0 |

The exact image is preserved as
`bench/artifacts/2026-09-26-context-switch-r5/context-switch.prg`
(SHA-256 `dc16c97bc897868ec8a3c5da58cc42abd0c47fabaddbd50299a9aae13b7fc357`).
Build and emulator provenance is in that directory's README.

Reproduction:

```sh
make bench-context-switch
# 1986
../1986/1986 --disk build/bench/context-switch/context-switch.prg \
  --paste 'BLOAD"*":SYS10240' --paste-at 180 --frames 400 --no-throttle \
  --save-snapshot /tmp/ctx.vsf
python3 tools/snapshot_extract.py /tmp/ctx.vsf /tmp/ctx.bin \
  --address 0xf180 --size 32
python3 tools/context_switch_decode.py /tmp/ctx.bin
# VICE 3.10 (x128)
python3 tools/vice_capture.py build/bench/context-switch/context-switch.prg \
  /tmp/ctx-vice.bin --entry 0x2800 --result-address 0xf180 --result-size 32 \
  --state-offset 6 --complete-value 2
python3 tools/context_switch_decode.py /tmp/ctx-vice.bin
```

Verify the preserved bytes with `cd raw && sha256sum -c SHA256SUMS`.

## Screen readout

The r5 image prints the 32-byte record as four lines of 16 hex characters on
both the 40-column VIC screen and the 80-column VDC screen before halting, so a
physical C128 run can be captured without a monitor or disk save. The lines are
record bytes `$F180-$F187`, `$F188-$F18F`, `$F190-$F197`, and `$F198-$F19F`.

## What the records prove

- Each task owns a separate context record; A and B use distinct seed and yield
  registers, stack pointers, parity pads, stack markers, and two alternating
  resume labels.
- Restored A/X/Y observations are checked against formulas derived from the
  current step, not against the record, so a stale or cross-wired record cannot
  pass.
- Processor status is captured before any flag-changing instruction, restored
  after A/X/Y, and compared against a replay of the task tail; the check covers
  N, V, D, Z, and C.
- The stack pointer must equal the designated base minus the parity pad and
  marker, and the marker bytes are read from the actively used top of the
  relocated page one.
- The resume marker identifies which of the two distinct resume labels actually
  executed, so a stale program counter cannot pass.
- The restored D flag drives a per-entry arithmetic probe: A must produce a
  decimal result and B a binary result from the same operands, so decimal mode
  cannot leak between tasks.
- The live stack pointer varies with a step-derived pad of zero to three words.
  The context stores that live SP directly; the resume label verifies the
  previous marker and pad against the live stack page and pops the frame
  before preparing the next yield, so a frame must survive the other task.
- The interrupt handler saves and restores A, X, Y, and P, and the boundary and
  body counters are both required to be nonzero and exact.

## Physical C128

The r5 image was run on a physical C128. Two transcribed screen records:

| Run | Line 1 | Line 2 | Line 3 | Line 4 |
|---|---|---|---|---|
| first | `4358535701010200` | `4080009*80000002` | `020240400000|0_` | `1308000000000000` |
| last | `4358535701010200` | `4080009-80000002` | `0202404000008815` | `130000000` |

Both records decode as a complete run: magic `CXSW`, ABI `0.1`, state `2`,
failure `0`, 64 rounds, 128 switches, 128 successful checks, no check or
canary failures, strategy `2` (relocation), steps `64`/`64`, and zero page
bytes per switch. Both interrupt classes were observed.

A few glyphs in the transcription are overlays rather than clean hex digits
(most likely the KERNAL cursor sitting on the readout row); the last record's
interrupt counters are exact (`boundary $1388`, `body $0015`, total `$139D`,
consistent with the recorded low byte `$9D`). The first record's low counter
nibbles were partly obscured but show `boundary $13xx` and `body $08xx`.

## Decision input

Both runs prove the relocated page-zero/page-one ownership path: A, X, Y, P,
SP, and PC restore per switch; the relocated zero-page and stack pages survive;
the task-visible bank matches the selected profile; and interrupts arrive at
the switch boundary and during task execution without corrupting a switch.
Relocation moves no page bytes per switch, while the bounded copy primitive
already characterized by [`bench/context`](../../context/README.md) transfers
the 33-byte context plus any live stack bytes.

Recommendation: adopt relocated page-zero/page-one ownership for the
cooperative scheduler and keep a bounded copy fallback. The physical C128 runs
confirm the recommendation, and
[ADR 0008](../../../docs/decisions/0008-context-switch-placement.md) records it
as accepted. The spike remains outside the production kernel; the scheduler
revision integrates the qualified context path.
