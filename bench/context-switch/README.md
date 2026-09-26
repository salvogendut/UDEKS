# Context-switch spike

This standalone diagnostic image is the Tasking 0.1 step-2 spike from the
[handover](../../HANDOVER.md). It switches between two synthetic 8502 tasks
inside top common RAM and reports which task state survives each switch. It does
not link into the production kernel.

```sh
make bench-context-switch
python3 tools/context_switch_decode.py run.vsf
```

The launcher runs at `$2800`, enables top common RAM, seeds bank-private
sentinels, and copies the switch core to `$F800`. The core alternates two
tasks, each with its own relocated page-zero and page-one allocation in bank 1:

| Task | page 0 | page 1 | profile | stack base | seed A/X/Y | yield tag | resume markers |
|---|---|---|---|---|---|---|---|
| A | bank 1 page `$80` | bank 1 page `$81` | kernel I/O | `$FF` | `$40/$A5/$A1` | `$40/$A1` | `$E0`/`$E1` |
| B | bank 1 page `$82` | bank 1 page `$83` | worker I/O | `$F5` | `$80/$5A/$B2` | `$80/$B2` | `$E2`/`$E3` |

Each task owns a separate context record and two distinct resume labels. On
each round a task pushes a parity pad and a per-task stack marker, selects the
next resume label from the step parity, and yields; the core restores the
record with `jmp (ctx_pc)`.

Per switch the core qualifies:

- restored A/X/Y against formulas derived from the current step and per-task
  tags, not against the record;
- processor status captured before any flag-changing instruction, restored
  after A/X/Y, and compared against a replay of the task tail (N, V, D, Z, C);
- decimal-mode isolation: the restored D flag drives a per-entry probe, so A
  must produce a decimal result and B a binary result from the same operands;
- variable live-SP restoration: a step-derived pad of zero to three words plus
  a step-valued marker, with the exact live SP and marker bytes checked against
  the step formula;
- the resume marker against the parity-selected resume label, proving which
  program counter actually ran;
- the zero-page sentinel, the page-bottom overflow canary, the task-visible
  bank at `$8000`, and step continuity.

Interrupts run with the task. The dispatch path opens the interrupt window
before resuming, and the task sets `window_flag` before yielding; the CIA1
Timer A handler saves and restores A, X, Y, and P and keeps 16-bit boundary and
body counters, so interrupts at a switch boundary cannot corrupt a context and
the record shows both categories were exercised.

The 32-byte `CXSW` result block at `$F180` records the round and switch counts,
16-bit interrupt totals, check and canary failures, and the strategy result.
The relocation strategy moves zero page-one bytes per switch (`XFER = 0`),
which is the measured input for choosing it over the bounded copy primitive
already characterized in [`bench/context`](../context/README.md).

The corrected spike passes in `1986` (1087 interrupts) and VICE 3.10 (5019
interrupts) with 128 switches, one successful check per switch, zero canary
failures, and both boundary and body interrupts; the exact PRG, raw records,
provenance, and the placement recommendation are recorded under
[`bench/artifacts/2026-09-26-context-switch-r3`](../artifacts/2026-09-26-context-switch-r3/README.md)
and [`bench/results/2026-09-26-context-switch`](../results/2026-09-26-context-switch/README.md).
A physical C128 run remains required before the decision is frozen.
