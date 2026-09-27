# Tasking 0.1 — event-wait increment

Status: design proposal, started on `tasking-0.1-event-waits` after PR #3
merged as `00060f4` on 2026-09-27. Tracking issue:
[#4](https://github.com/salvogendut/UDEKS/issues/4). The pure policy below is
implemented, but no new resident request operation is installed or advertised.
[Task Request ABI 0.3](../abi/task-request.md) remains the published contract.

## First increment: pure policy (2026-09-27)

`src/kernel/task_poll_policy.c` implements request validation and a pure
readiness/deadline decision. Its constants live separately in
`include/udeks/task_poll_policy.h`; they do not extend the public ABI header.
Validation preserves the complete input record, every task slot and lifecycle
counter, and the decoded output on rejection. Protocol-envelope errors take
precedence over operation/version availability; then caller, descriptor, and
payload checks apply in that order.

Seventeen host tests cover those rules, 16-bit mask/timeout bounds, all flag
and descriptor bytes, finite clock wrap, immediate/infinite waits, readiness
winning a timeout tie, non-consuming observations of actual line-editor
submissions, and the existing stopped-waiter lifecycle behavior. These tests
do not claim to qualify resident registration, private response publication,
or cancellation/slot-reuse cleanup; those remain increment 3.

`make task-poll-policy` compiles and assembles this reference implementation
without linking it. The reference cc65 build emits 515 CODE bytes with zero
DATA/RODATA/BSS/zero-page allocation, before any imported helper cost. It does
not fit wholesale in the 501-byte overlay gap. Keep it as the executable
specification while measuring the bounded resident implementation/refactor;
do not add it to the link based on the source file's apparent size.

`make check` passes 613 tests and `make placement-check` passes. Rebuilding
normal D71/D64 leaves both images and the resident kernel byte-identical to
the merged baseline. No emulator requalification is claimed for this
compile-only change, and ABI 0.3 remains advertised.

## First useful event: stdin readability

Let a task wait for a submitted console line without repeatedly issuing
nonblocking `READ`. Keep `READ` unchanged: it consumes bytes; a readiness
wait only reports that a subsequent read can make progress. This is a
poll-shaped interface, not a claim of Linux binary or full `poll()` API
compatibility.

The existing line editor already owns the required level-triggered state:
`udeks_line_editor_submitted_ready_value`. The chunked reader leaves it set
until it consumes the final newline, including the newline for an empty line.
Readiness must follow that state rather than individual keyboard interrupts.
The keyboard and root-terminal service passes currently precede init's task
selection, providing a natural bounded wake-check point.

This increment does not introduce descriptor inheritance, a controlling-TTY
policy, multiple terminals, or arbitrary event handles. Preserve existing
console access rights. Readiness grants no reservation: if another permitted
reader drains the input before a resumed task reads, `READ` may still return
`EAGAIN` and the task must wait again.

## Proposed request extension — review before freezing

Use the existing `$F359` record and `$CF30`/`$FF16` gates. Propose minor 0.4
and operation 16, `POLL`, without renumbering operations 1–15 or silently
changing 0.3 behavior. Older minor versions must continue to reject operation
16 with `ENOSYS`; a kernel without 0.4 support still rejects the new version.

The initial operation handles one descriptor, not an array:

- Descriptor: stdin (`0`) only in this increment.
- Count: four payload bytes; request flags: zero.
- Payload bytes 0–1: little-endian requested readiness mask; initially only
  readable (`0x0001`) is supported.
- Payload bytes 2–3: little-endian timeout in the existing 1/60-second logical
  tick units: zero means immediate, 1–600 means bounded, and `$FFFF` means
  indefinitely. This wire timeout is deliberately not Linux milliseconds.
- Success: result one and a readable mask when ready; result zero and a zero
  mask on immediate no-readiness or timeout. Errno is zero in both cases;
  lack of readiness is not `EAGAIN`. Preserve the requested timeout bytes.
- Unsupported descriptors return `EBADF`; malformed counts, flags, zero or
  unsupported masks, and unsupported timeout values return `EINVAL`. Apply
  the existing current/RUNNING-caller validation before changing state.

These byte choices remain a proposal until policy tests, wrapper design, and
the placement audit agree. Multi-descriptor polling, other readiness bits,
and files/device-handle semantics are separate extensions.

## Ownership and wake rules

1. Validate without mutation, then inspect readiness. If ready, complete
   synchronously; if the timeout is zero, complete without blocking.
2. Otherwise snapshot the original request and sequence into the caller's
   private wait state, record INPUT as the wait reason, and release `$F359`
   before another task runs. No shared request pointer survives suspension.
3. Registration and the readiness check must not leave a lost-wakeup window.
   With the current cooperative line producer, check and registration belong
   to one non-yielding kernel operation. Any future IRQ producer requires an
   equivalent bounded atomic protocol, not an assumption that this remains
   safe automatically.
4. Scan at most the eight task slots during the resident service pass. Test
   readiness before deadline expiry when both are observed in the same pass.
   Use the existing wrap-safe 16-bit clock for finite deadlines; never treat
   the infinite sentinel as an arithmetic deadline. The signed-difference
   rule requires examining finite waits within half a clock cycle (32,768
   logical ticks) of the deadline; arbitrary multi-wrap suspension is not
   supported by that representation.
5. Mark a matching private request ready once. Publish its response with its
   original sequence only when that task resumes. Do not read console data
   in the scheduler, allocate memory in an IRQ, or reschedule from an IRQ.
6. Cancellation/exit/reap/reuse must discard the pending subscription and
   saved response. A stopped waiter may become ready but remains stopped;
   continue must not strand it on an event that already occurred. Test the
   state model even while STOP/CONTINUE remain outside the public requests.

The first wake source is console readiness only. Keep child exit in
`WAITPID`, timer-only waits in `SLEEP`, and defer Z80/device/IPC notifications.
The CPUs still execute mutually exclusive bus leases, not simultaneous tasks.

## Placement gate before resident code

The merged baseline leaves 501 bytes at `$C70B-$C8FF` after the linked
scheduler core/BSS. The lifecycle handler fills `$C900-$CDBC` exactly and is
adjacent to the fixed context records at `$CDBD`. The common task gate is
already 191/192 bytes; the request gateway is 262/265 bytes.

Do not append another dispatcher branch into a full reservation or grow the
resident kernel across the frozen VIC-shadow start. First measure a refactor
that moves sufficient handler/dispatch code into the existing overlay gap.
Charge new code, state, and any imported helpers to the actual linked map;
the 501 bytes are an upper bound, not a promised fit. Preserve public entries,
UAPP zero-page addresses, and the exact context reservation. Stop and propose
another placement if the measured image cannot fit.

## Implementation and qualification sequence

1. Add a pure, host-tested validation/readiness policy; decide and document
   the response layout and version gate. Keep the kernel advertising 0.3
   until the resident implementation can honor the extension.
2. Qualify the handler refactor without changing behavior: placement-check,
   shadow probe, and existing D71/D64 lifecycle/graphics probes stay green.
3. Add bounded wait registration, wake checking, timeout handling, cancellation
   cleanup, and private response publication. Qualify a compiled C task with
   a live software-stack frame, not only an injected table entry.
4. Add the task-side wrapper and migrate idle `/bin/ush` input waiting only
   after the probe passes. Keep the old read/yield path available during
   qualification. Foreground-job `WAIT` and graphics polling are not replaced
   by this increment.

Required regressions: ready-before-call; input arriving while waiting; zero,
finite, and infinite waits; clock wrap; readiness/timeout tie; empty lines;
chunked reads and final newline; cancellation followed by slot reuse; two
waiters without consumption by the scheduler; repeated wake checks; and
original-sequence restoration after another task uses the shared request.
Run invalid-field tests with unchanged task/allocation state.

Gate both disk formats in VICE, preserve independent 1986 and physical-C128
checks, and verify typing/history, mouse/joystick input, xclock/xwave repaint,
and foreground cancellation remain usable. Existing outstanding ADR 0010,
ADR 0012, and physical-context qualifications are not discharged by this work.
