# UDEKS task ABI 0.1

This document freezes the compiler-neutral task identity, lifecycle states,
transition rules, and read-only diagnostic record used by Tasking 0.1. The
[handover](../HANDOVER.md) defines the milestone; this file is the byte-level
contract that its host module, resident kernel, and emulator decoders share.

Tasking 0.1 is observational first. It represents the existing init service,
the resident compatibility shell, the persistent bank-1 `/bin/ush`, and the
managed `xclock` and `xwave` applications in one bounded table without changing
how any of them are dispatched. Context switching, scheduling, and new syscall
gates are added in later revisions, after the assembly context-switch spike
selects and qualifies a save/copy strategy.

## States

Values are the byte stored in the task table and reported by the diagnostic
record. `FREE` is the only state from which a slot may be allocated.

| Value | Name | Meaning |
|---:|---|---|
| 0 | `FREE` | Slot unused; identity and context may be reallocated. |
| 1 | `NEW` | Slot allocated and validated but not yet admitted. |
| 2 | `RUNNABLE` | Ready to be dispatched; waiting only for a turn. |
| 3 | `RUNNING` | Currently owns the 8502; at most one task may hold this. |
| 4 | `WAITING` | Blocked on a reason recorded in the wait field. |
| 5 | `STOPPED` | Suspended; not runnable until continued. |
| 6 | `ZOMBIE` | Exited; exit status available until the parent reaps it. |

## Events

Events request a transition. They are the only way lifecycle state changes,
apart from slot allocation by `create`, which is itself a distinct operation.

| Value | Name | Meaning |
|---:|---|---|
| 1 | `CREATE` | Allocate a `FREE` slot as `NEW`. Performed by `create`. |
| 2 | `ADMIT` | `NEW` becomes `RUNNABLE`. |
| 3 | `DISPATCH` | `RUNNABLE` becomes `RUNNING`. |
| 4 | `YIELD` | `RUNNING` voluntarily becomes `RUNNABLE`. |
| 5 | `BLOCK` | `RUNNING` becomes `WAITING` on a validated reason. |
| 6 | `UNBLOCK` | `WAITING` becomes `RUNNABLE`. |
| 7 | `STOP` | `RUNNABLE`, `RUNNING`, or `WAITING` becomes `STOPPED`. |
| 8 | `CONTINUE` | `STOPPED` becomes `RUNNABLE`. |
| 9 | `EXIT` | `NEW` or `RUNNING` becomes `ZOMBIE`; records status. |
| 10 | `REAP` | `ZOMBIE` becomes `FREE`; identity is released. |
| 11 | `CANCEL` | Any live state becomes `ZOMBIE`; records status 0. |

For `BLOCK` the event argument is a wait reason; for `EXIT` it is the eight-bit
exit status. Other events ignore the argument. `CREATE` is rejected if passed
to the generic transition operation.

## Wait reasons

`WAITING` records why the task is blocked. Zero is not a valid reason for a
blocking transition.

| Value | Name | Meaning |
|---:|---|---|
| 0 | `NONE` | Not blocked. |
| 1 | `CHILD` | Waiting for a child task to exit. |
| 2 | `INPUT` | Waiting for console or keyboard input. |
| 3 | `TIMER` | Waiting for monotonic kernel time. |
| 4 | `Z80` | Waiting for a bounded Z80 worker lease. |
| 5 | `TERMINAL` | Waiting for terminal ownership. |

## Transition result codes

Every operation returns an eight-bit result. Zero is success. A rejected
request must not alter scheduler state, and it increments the rejected-request
counter published in the diagnostic record.

| Value | Name | Meaning |
|---:|---|---|
| 0 | `OK` | Transition applied, or a same-task dispatch was a no-op. |
| 1 | `BAD_ID` | Task id 0 or outside the bounded table. |
| 2 | `BAD_STATE` | The event is illegal for the slot's current state. |
| 3 | `EXISTS` | `CREATE` targeted a slot that is not `FREE`. |
| 4 | `TABLE_FULL` | Reserved; a fixed id table cannot fill implicitly. |
| 5 | `BAD_REASON` | `BLOCK` reason was 0 or unknown. |
| 6 | `BUSY` | `DISPATCH` targeted a task while another one is `RUNNING`. |
| 7 | `BAD_EVENT` | Event value was 0 or unknown, including `CREATE`. |

## Bounded table

The initial table has eight slots. Task ids are `1..8`; id `0` means "no
task". A slot's state is `FREE` until `create` allocates it, so an id is an
opaque handle and must be validated before every operation.

The minimum per-task fields that the scheduler must eventually own are:

- task id, parent task id, state, flags, and exit status;
- executable CPU, bank/MMU profile, validated image, BSS, and allocation
  bounds, and entry address;
- saved 8502 registers, program counter, processor status, hardware stack
  state, cc65 software-stack pointer, and compiler-owned zero-page bytes;
- standard descriptors, current working-directory handle, controlling
  terminal/session owner, and foreground/background ownership;
- wait reason and bounded wake data for child exit, input, timer, or Z80 work;
- stack bounds plus canary state.

Tasking 0.1 implements only the identity and lifecycle subset above; the
resident table is private to the kernel and is not yet read by another CPU.
Byte offsets for the context fields are deliberately not frozen until the
context-switch spike chooses between relocated page-zero/page-one ownership
and a bounded save/copy strategy, as required by the handover.

## Diagnostic record

Task 0.1 reserves a read-only 16-byte `UTSK` record in common RAM so emulator
tests can observe the table without reaching into private state. It occupies
`$F110-$F11F`, between the CIA time status at `$F100` and the keyboard status
at `$F120`. The host-tested state module fills the record for host tests; the
resident kernel publishes it once the table is linked behind the scheduler
seam. The address is frozen now so later work cannot collide with neighboring
records.

The initial linker-map audit found the resident bank-0 image ending at `$ACAB`
with the VIC-IIe shadow fixed at `$AF00`, leaving about 595 bytes before the
shadow. The first complete state module compiles to roughly 1.2 KiB, so linking
it unchanged cannot preserve the boot image. Resident publication therefore
arrives together with the context-switch spike and a deliberate decision about
where scheduler state and code live; it must not silently consume the gap or
move the VIC-IIe shadow without its own boot-chain validation.

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `UTSK` |
| 4 | 1 | ABI major (`0`) |
| 5 | 1 | ABI minor (`1`) |
| 6 | 1 | State: `0` uninitialized, `1` ready, `$80 | code` internal failure |
| 7 | 1 | Current running task id; `0` when none |
| 8 | 1 | Runnable count (`RUNNABLE` plus `RUNNING`) |
| 9 | 1 | Defined count (every state except `FREE`) |
| 10 | 1 | Rejected transitions since reset |
| 11 | 1 | Canary failures since reset |
| 12 | 2 | Completed dispatches, little-endian |
| 14 | 1 | Last accepted event value; `0` before the first transition |
| 15 | 1 | Reserved; zero |

Published counts are derived from the table, not stored separately. The
decoder rejects a ready record whose runnable count exceeds its defined count,
whose defined count exceeds the table capacity, or whose reserved byte is
nonzero.

`create` never increments the dispatch counter. `DISPATCH` increments it only
when it moves a task other than the current one into `RUNNING`; redispatching
the current task is a successful no-op. The canary counter starts at zero and
is only incremented by the context path once it checks stack bounds.
