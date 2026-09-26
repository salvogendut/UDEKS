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
sentinels, and copies the switch core to `$F800`. The core then alternates two
tasks, each with its own relocated page-zero and page-one allocation in bank 1:

| Task | page 0 | page 1 | profile | stack init | seed A/X/Y | yield tag |
|---|---|---|---|---|---|---|
| A | bank 1 page `$80` | bank 1 page `$81` | kernel I/O | `$FF` | `$41/$A5/$A1` | `$40/$A1` |
| B | bank 1 page `$82` | bank 1 page `$83` | worker I/O | `$F5` | `$82/$5A/$B2` | `$80/$B2` |

Each task owns a separate context record. Dispatch copies that record into the
restore registers, stores the dispatched values as per-task expectations, and
resumes at the task's own saved program counter with `jmp (ctx_pc)`. A task
yields after pushing a per-task stack marker into the actively used top of its
relocated page one; the core saves registers, processor status, and the stack
pointer above that marker and verifies all of them before switching. Per switch
the core qualifies:

- A, X, Y, P, SP, and PC restore from the task's own record;
- the page-one stack marker and the page-bottom overflow canary;
- the zero-page sentinel and the restored-register observations;
- the task-visible bank at `$8000` under its selected MMU profile;
- step continuity across switches.

Interrupts stay disabled only while a context record is being updated. The
dispatch path opens the interrupt window just before resuming a task, and the
task reopens it just before yielding; `window_flag` marks those boundary
windows. The CIA1 Timer A handler saves and restores A, X, and Y and counts
boundary versus body arrivals, so the record shows interrupts landed at the
switch boundary and during task execution without corrupting a context.

The 32-byte `CXSW` result block at `$F180` records the round count, switch
count, interrupt counts, check and canary failures, and the strategy result.
The relocation strategy moves zero page-one bytes per switch (`XFER = 0`),
which is the measured input for choosing it over the bounded copy primitive
already characterized in [`bench/context`](../context/README.md).

The spike passes in `1986` and VICE 3.10 with 128 switches, one successful
check per switch, zero canary failures, and both boundary and body interrupts;
the exact PRG, raw records, provenance, and the placement recommendation are
recorded under [`bench/artifacts/2026-09-26-context-switch-r1`](../artifacts/2026-09-26-context-switch-r1/README.md)
and [`bench/results/2026-09-26-context-switch`](../results/2026-09-26-context-switch/README.md).
A physical C128 run remains required before the decision is frozen.
