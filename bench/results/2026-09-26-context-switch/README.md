# Context-switch spike results

The corrected standalone context-switch spike (`-r4`) was run against the two
qualified emulators. Both completed the relocation strategy with one successful
check per switch, no canary failure, and zero page bytes moved per switch.
Interrupts were observed both inside the marked switch-boundary windows and
during task execution; the counters are 16-bit, so the totals are exact.

| Run | Switches | Interrupts | Boundary | Body | Checks | Canary | Page bytes/switch |
|---|---:|---:|---:|---:|---:|---:|---:|
| `1986` | 128 | 1349 | 887 | 462 | 128/128 | 0 | 0 |
| VICE 3.10 | 128 | 7111 | 5019 | 2092 | 128/128 | 0 | 0 |

The exact image is preserved as
`bench/artifacts/2026-09-26-context-switch-r4/context-switch.prg`
(SHA-256 `5bf1788a1b225da58b551b28d515a05f0e51864e9f43072c935ee9ad1a72d9f3`).
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

## Decision input

Both runs prove the relocated page-zero/page-one ownership path: A, X, Y, P,
SP, and PC restore per switch; the relocated zero-page and stack pages survive;
the task-visible bank matches the selected profile; and interrupts arrive at
the switch boundary and during task execution without corrupting a switch.
Relocation moves no page bytes per switch, while the bounded copy primitive
already characterized by [`bench/context`](../../context/README.md) transfers
the 33-byte context plus any live stack bytes.

Recommendation: adopt relocated page-zero/page-one ownership for the
cooperative scheduler, keep a bounded copy fallback, and confirm on a physical
C128 before freezing the ABI. The spike remains outside the production kernel
so the permanent scheduler placement is decided with this evidence.
