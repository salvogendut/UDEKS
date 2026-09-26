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

| Task | page 0 | page 1 | profile |
|---|---|---|---|
| A | bank 1 page `$80` | bank 1 page `$81` | kernel I/O |
| B | bank 1 page `$82` | bank 1 page `$83` | worker I/O |

A task yields with `jmp yield_core` after storing its resume address; the core
saves registers, processor status, stack pointer, and that program counter and
restores all four with `jmp (save_pc)`. Interrupts stay masked until the task
resumes, so a timer interrupt can never clobber a half-built switch. Per switch
the core qualifies:

- A, X, Y, P, SP, and PC restore;
- the page-one canary and the relocated task page;
- zero-page sentinel, step counter, and restored-register observations;
- the task-visible bank at `$8000` under its selected MMU profile;
- interrupts from CIA1 Timer A arriving during task execution, with the
  handler running from common RAM on the task stack.

The 32-byte `CXSW` result block at `$F180` records the round count, switch
count, interrupt count, check and canary failures, and the strategy result. The
relocation strategy moves zero page-one bytes per switch (`XFER = 0`), which is
the measured input for choosing it over the bounded copy primitive already
characterized in [`bench/context`](../context/README.md).

The spike passes in `1986` and VICE 3.10 with 128 switches, zero check or
canary failures, and zero page bytes per switch; the raw records and the
placement recommendation are recorded under
[`bench/results/2026-09-26-context-switch`](../results/2026-09-26-context-switch/README.md).
A physical C128 run remains required before the decision is frozen.
