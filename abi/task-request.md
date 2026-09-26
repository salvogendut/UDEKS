# Bank-task request ABI 0.3

Bank-1 8502 tasks exchange bounded requests with the resident kernel through a
38-byte record in top common RAM. The task fills the record and calls `$FF16`.
That gate swaps cc65 zero-page contexts, selects bank 0, dispatches through the
fixed `$CF30` vector, and restores bank 1 before returning.

ABI 0.3 keeps every 0.2 operation number and behavior unchanged and adds
lifecycle operations `10`-`15`. The new operations are frozen here but not yet
implemented; the resident dispatcher returns `ENOSYS` for them until their
implementations land. Rebuilt 0.3 clients may keep using the 0.2 operations
unchanged, and the resident version check accepts minor `0`, `1`, `2`, and `3`.

## Record

The record occupies `$F359-$F37E`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `UTRQ` |
| 4 | 1 | ABI major (`0`) |
| 5 | 1 | ABI minor (`3`) |
| 6 | 1 | State |
| 7 | 1 | Operation |
| 8 | 1 | Sequence number |
| 9 | 1 | Unix-style file descriptor |
| 10 | 1 | Requested byte count, at most 24 |
| 11 | 1 | Completed byte count |
| 12 | 1 | Linux-compatible errno value |
| 13 | 1 | Flags; operation-specific |
| 14 | 24 | Inline payload |

States are idle (`0`), request (`1`), complete (`2`), and error (`$80`).

## Operations

| Value | Name | Since | Meaning |
|---:|---|---:|---|
| 1 | `READ` | 0.2 | Submit console-line bytes to the descriptor. |
| 2 | `WRITE` | 0.2 | Write payload bytes to descriptor 1 or 2. |
| 3 | `EXEC` | 0.2 | Compatibility command-line dispatch. |
| 4 | `WAIT` | 0.2 | Resident foreground-job wait. |
| 5 | `PROMPT` | 0.2 | Rearm the root terminal input field. |
| 6 | `OPEN` | 0.2 | Open a bootfs directory or file. |
| 7 | `GETDENTS` | 0.2 | Read a bootfs directory entry. |
| 8 | `STAT` | 0.2 | Read bootfs entry metadata. |
| 9 | `CLOSE` | 0.2 | Close a bootfs descriptor. |
| 10 | `YIELD` | 0.3 | Voluntarily leave the running state. |
| 11 | `EXIT` | 0.3 | Terminate the caller with a status. |
| 12 | `WAITPID` | 0.3 | Reap a child, blocking or nonblocking. |
| 13 | `SLEEP` | 0.3 | Sleep for bounded kernel ticks. |
| 14 | `CANCEL` | 0.3 | Terminate another task. |
| 15 | `SPAWN` | 0.3 | Load and create a new task. |

`EXEC` (`3`) is not task creation and its meaning does not change: it remains
the bounded command-line bridge for the resident compatibility shell. Real
loader-backed task creation is `SPAWN` (`15`).

All other operation values return `ENOSYS`.

## Flags

Flags are operation-specific. The 0.2 operations define no flag bits; a
nonzero flags byte on a 0.2 operation remains a protocol error (`EPROTO`).
Reserved bits on a 0.3 operation are rejected with `EINVAL` once the operation
is implemented.

| Operation | Flag bits | Meaning |
|---|---|---|
| `WAITPID` | `0x01` `NOHANG` | Return immediately when no child is reapable. |

## Payload layouts

Task ids are little-endian 16-bit values. Id `0` means "no task"; `WAITPID`
treats it as "any child". The initial table admits ids `1..8`; other nonzero
ids are rejected with `ESRCH` (or `ECHILD` for `WAITPID`, as noted below).

### YIELD (10)

- Request: `count = 0`, flags `0`; payload ignored.
- Response: state complete, `result = 0`, errno `0`.

### EXIT (11)

- Request: `count = 1`; payload byte `0` is the eight-bit exit status; flags
  `0`.
- The call does not return to the caller on success. The status is published
  when the parent reaps the task with `WAITPID`. Returning from a normal UDEX
  entry is equivalent to `EXIT` with the entry's result.

### WAITPID (12)

- Request: `count = 2`; payload bytes `0-1` are the target child id (`0` means
  any child); flags may set `NOHANG`.
- Matching child that is a zombie: state complete, `result = 1`; payload bytes
  `0-1` are the reaped child id, byte `2` is its eight-bit exit or termination
  status, byte `3` is zero, and the zombie is reaped.
- Matching live child with `NOHANG`: state complete, `result = 0`, errno `0`,
  and the payload is unchanged. This matches Linux `waitpid()` returning `0`
  for a child that has not changed state.
- Matching live child without `NOHANG`: the caller blocks until the child
  exits, then the response above is published when the caller resumes.
- No matching child, including a target that is not a child of the caller or
  is outside the table: `ECHILD`.
- Reserved flag bits or a nonzero descriptor: `EINVAL`.

### SLEEP (13)

- Request: `count = 2`; payload bytes `0-1` are the requested ticks in 1/60 s
  units, from `1` through `600` (ten seconds); flags `0`.
- Response on success: state complete, `result = 0`, errno `0`.
- Zero or out-of-range ticks: `EINVAL`.

### CANCEL (14)

- Request: `count = 3`; payload bytes `0-1` are the target task id, byte `2`
  is the eight-bit termination status (the conventional `Ctrl+C` result is
  `130`, `128 + SIGINT`); flags `0`.
- Response on success: state complete, `result = 0`, errno `0`. The status is
  recorded as the target's exit status and is returned by `WAITPID`.
- Unknown, reaped, or non-child target: `ESRCH`.
- Target id `0`, the caller's own id, or a bad count: `EINVAL`.

### SPAWN (15)

- Request: `count = 17`; payload byte `0` is the leaf-name length (`1..16`),
  bytes `1-16` hold the leaf name, and the unused bytes after the name are
  zero; flags `0`.
- Response on success: state complete, `result = 1`; payload bytes `0-1` are
  the new task id, little-endian.
- Name not found: `ENOENT`. Invalid UDEX image or unsupported CPU: `ENOEXEC`.
  No free task slot or allocation: `ENOMEM`. A bad name length, a non-zero pad
  byte, a character outside letters, digits, `.`, `_`, `+`, and `-`, or
  reserved flag bits: `EINVAL`.

## Errors

| Value | Name | Used by |
|---:|---|---|
| 2 | `ENOENT` | `SPAWN`, filesystem operations |
| 3 | `ESRCH` | `CANCEL` |
| 5 | `EIO` | `PROMPT`, terminal failures |
| 8 | `ENOEXEC` | `SPAWN` |
| 9 | `EBADF` | `READ`, `WRITE`, filesystem operations |
| 10 | `ECHILD` | `WAITPID` |
| 11 | `EAGAIN` | `READ` would-block |
| 12 | `ENOMEM` | `SPAWN` |
| 16 | `EBUSY` | resource already owned |
| 20 | `ENOTDIR` | filesystem operations |
| 22 | `EINVAL` | malformed counts, flags, ids, or ranges |
| 24 | `EMFILE` | filesystem descriptor exhaustion |
| 38 | `ENOSYS` | operation not implemented |
| 71 | `EPROTO` | malformed 0.2 request or version |

## Rejection is atomic

A rejected request must not alter lifecycle state, allocation metadata, or any
other scheduler state. Validation of the version, state, operation, flags,
count, task id, allocation bounds, and stack bounds happens before any
mutation; a caller may retry a rejected request without observing partial
effects.

## 0.2 behavior preserved

Writes accept binary chunks rather than zero-terminated strings. Reads consume
submitted console lines in chunks and include the terminating newline; they are
nonblocking and return `EAGAIN` when no line is ready. `EXEC` copies at most 54
bytes of command text to `$F3A0-$F3D6`, queues the command for deferred
resident dispatch, and returns result `1` after queuing. `WAIT` returns `1`
while a queued or foreground job owns the session and `0` after the resident
job path has restored the prompt. `PROMPT` rearms the root terminal input
field. The boundary uses `EIO` (5), `EBADF` (9), `EAGAIN` (11), `EINVAL` (22),
`ENOSYS` (38), and `EPROTO` (71) exactly as documented in ABI 0.2.

## Scheduling and record ownership

The 0.2 operations complete synchronously; they do not schedule, and `EXEC`
completion means only that the command was accepted for deferred resident
dispatch. The 0.3 lifecycle operations may context-switch: `YIELD`, a blocking
`WAITPID`, and `SLEEP` return only when the caller is resumed, `CANCEL` and the
nonblocking calls return without switching, and `EXIT` never returns.

`$F359` is a single shared record, so a blocked task cannot retain ownership of
it. When a lifecycle request blocks or switches, the kernel snapshots the
request (operation, flags, sequence, descriptor, count, and payload) into the
task's own state, releases the shared record, and writes the response fields
back—preserving the original sequence number—immediately before that task
resumes from the `$FF16` gate. While the record is released, another task may
use it. A task cancelled while blocked never resumes, so no response is
written and the record stays available.

A cooperative program must still return from its `$9000` poll entry when it has
no more immediate work.

## Placement note

The fixed `$F800` request gateway uses 262 of its 265 reserved bytes as of ABI
0.3. Resident lifecycle handlers cannot be added to that segment; they require
a separate placement or trampoline decision before implementation.
