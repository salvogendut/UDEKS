# ADR 0008: Cooperative context-switch placement and page ownership

- Status: accepted
- Date: 2026-09-26

## Context

Tasking 0.1 step 2 required a spike that switches between two synthetic 8502
tasks and proves independently that A, X, Y, P, PC, and the hardware stack
pointer, page-one contents, cc65 zero page and its software-stack pointer, the
selected MMU profile and visible bank, and interrupts before and after a
switch all survive. The handover requires the spike to choose between
relocated page-zero/page-one ownership and a bounded save/copy strategy before
the choice is integrated into the kernel.

[`bench/context-switch`](../../bench/context-switch/README.md) runs the switch
core from common RAM while two tasks alternate between the kernel-I/O and
worker-I/O profiles. Each task owns a bank-1 physical page for zero page and
another for page one (`$80`/`$81` and `$82`/`$83`). The context record stores
the live stack pointer and resume program counter directly; each resume label
verifies the previous marker and pad on the live stack page and pops the frame
before preparing the next yield. Restored state is validated against
step-derived formulas, a status replay, stack markers and canaries, a
decimal-mode probe, and boundary/body interrupt counters.

The image passed in `1986` and VICE 3.10 and passed first and repeated runs on
a physical C128 with a complete `CXSW` record, 128 of 128 successful checks,
zero canary failures, exact step counts, and zero page bytes moved per switch.
The preserved evidence is under
[`bench/artifacts/2026-09-26-context-switch-r5`](../../bench/artifacts/2026-09-26-context-switch-r5/README.md)
and [`bench/results/2026-09-26-context-switch`](../../bench/results/2026-09-26-context-switch/README.md).

## Decision

The cooperative scheduler uses relocated page-zero and page-one ownership.

- Each task owns a bank-1 physical page for zero page and a bank-1 physical
  page for page one, selected with `$D507-$D50A` as part of the switch.
- The saved context is the 8502 register and status set (A, X, Y, P, SP), the
  resume program counter, the selected MMU profile, and the task's page-0 and
  page-1 bank/page selectors. The live stack, including its frame, stays in the
  task's relocated page one across switches.
- The switch routine executes from RAM mapped in every task profile: common
  RAM during the spike, and the resident kernel's always-mapped region once
  integrated. It must not depend on the active task's zero page or stack, and
  it must select an I/O-visible profile before reconfiguring the MMU or page
  registers.
- Interrupt entry and return preserve the interrupted task's full register and
  status set; boundary and body arrivals are both qualified.
- A bounded save/copy context remains the fallback for any task whose pages
  cannot be relocated. It is not the primary strategy.

Exact task-control-block byte offsets remain internal to the resident kernel
until the scheduler links; the semantic fields above are frozen.

## Consequences

- No per-switch page copying is required, and the measured relocation path
  moves zero page bytes per switch.
- The switch path requires strict discipline: while a task is mapped, its zero
  page and page one belong to that task, so core state and compiler temporaries
  may not use them.
- Page-zero and page-one allocations become validated per-task resources that
  the memory map, task table, and allocator must account for.
- The resident context-switch code must live in always-mapped RAM, which is an
  explicit placement constraint on the scheduler revision.
- This ADR freezes the placement strategy only. A compiled C task using the
  real cc65 software stack is the integration test for the scheduler revision.
