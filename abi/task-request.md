# Bank-task request ABI 0.8

Bank-1 8502 tasks exchange bounded requests with the resident kernel through a
38-byte record in top common RAM. The task fills the record and calls `$FF16`.
That gate swaps cc65 zero-page contexts, selects bank 0, dispatches through the
fixed `$CF30` vector, and restores bank 1 before returning.

ABI 0.3 keeps every 0.2 operation number and behavior unchanged and adds
lifecycle operations `10`-`15`. `YIELD`, `EXIT`, immediate/nonblocking and
blocking `WAITPID`, `SLEEP`, `CANCEL`, and `SPAWN` are implemented. Rebuilt
0.3 clients may keep using the 0.2 operations unchanged, and
the resident version check accepts minor `0` through `8`.
ABI 0.4 adds non-consuming stdin readiness (`POLL`, operation 16). A 0.0–0.3
request for operation 16 returns `ENOSYS`; an unsupported future minor returns
`EPROTO`. Operations 1–15 retain their existing numbers and behavior.
ABI 0.5 adds read-only IEC `MOUNT`/`UMOUNT` through a private bank-1 C service.
Existing stream/directory clients continue to request their minimum ABI 0.4;
`POLL` accepts 0.4 through 0.8. The current shell uses 0.8; `df` uses 0.6
for `STATFS`. ABI 0.7 adds deferred numeric service control; 0.8 adds root
namespace routing and working-directory operations. No published entry address changes.

## Record

The record occupies `$F359-$F37E`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `UTRQ` |
| 4 | 1 | ABI major (`0`) |
| 5 | 1 | ABI minor (`8`; earlier compatible minors remain accepted) |
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
| 16 | `POLL` | 0.4 | Wait for stdin readability without consuming input. |
| 17 | `MOUNT` | 0.5 | Mount IEC device 8–11 read-only at `/mnt`. |
| 18 | `UMOUNT` | 0.5 | Unmount `/mnt` if no storage handle is open. |
| 19 | `STATFS` | 0.6 | Read mounted CBM-DOS total/free block counts. |
| 20 | `CONTROL` | 0.7 | Enqueue a root-session graphics/engine action. |
| 21 | `CHDIR` | 0.8 | Validate and change the root session's working directory. |
| 22 | `GETCWD` | 0.8 | Return the root session's absolute working directory. |

`EXEC` (`3`) is not task creation and its meaning does not change: it remains
the bounded command-line bridge to the executable loader. There is no resident
builtin-name table anymore: current `ush` owns builtins and graphics option
parsing; old clients cannot depend on the removed resident builtin catalog. Real
loader-backed task creation is `SPAWN` (`15`).

After validating the protocol envelope, all other operation values return
`ENOSYS` before operation-specific field checks.

## System-root namespace (0.8)

The [filesystem contract](filesystem.md#root-namespace-contract-26) now applies
to the live service. The system disk (default device 8) backs `/`, `/bin`,
and `/etc`; a separate data volume may occupy `/mnt`. Bootfs is used only by
the explicit recovery path. Bare command names search system `/bin`, never
data media. Directory lookup rejects ambiguity with `EEXIST` rather than
choosing the first entry. The older 0.5 section below describes the original
wire shapes; its `/mnt`-only route and first-match policy are superseded here.

`CHDIR`: descriptor/flags zero, count 1–23, ASCII path with a NUL at
payload[count]. Success returns result zero after checking the directory and
mount; rejection leaves cwd unchanged. `GETCWD`: descriptor/flags/count zero;
returns canonical `/`, `/bin`, `/etc`, or `/mnt`, with result excluding the
trailing NUL. Earlier minors return `ENOSYS`; malformed fields return `EINVAL`.
Cwd is still a shared root-session token, not isolated per-process state.

`OPEN`/`STAT` accept normalized absolute or cwd-relative paths with the same
count/NUL convention. Descriptor `2` on `OPEN` (0.8 only) means a UDEX
candidate: `.SH` and `.ETC` are rejected with `ENOEXEC`, directories with
`EISDIR`; the executable loader still validates the actual header/size/slot.
Ordinary read and directory opens retain descriptors 0 and 1. `.SH` files
are readable/listable; no general script interpreter is advertised yet.

`STATFS` retains its 0.6 counted, non-NUL-required payload and response, but
accepts any of the four directory paths (including relative spellings).
Leaves are `EINVAL`. The path selects the owning system/data device. Missing
mounts are `ENODEV` for 0.8 clients; earlier clients retain `ENOENT`.

The bootstrap alone can `MOUNT` a device at `/` (count 2: unit then slash),
or release it with `UMOUNT /` (count 1) after a failed shell load. Both require
0.8 and boot-source state zero. Once a disk/recovery shell is selected, root
mount/unmount returns `EBUSY`. This is a boot-state guard, not memory protection.
Data mount shapes remain unchanged. A handle owns its mount until CLOSE;
cwd in `/mnt` or a data handle blocks its unmount. A root handle does not block
removing an unused data mount. Mount probes and STATFS cannot interrupt an
open handle. File STAT still returns `ENOSYS` (no invented byte sizes).

## Deferred root-session control (0.7)

`CONTROL`: descriptor/flags `0`, count exactly `3`, payload `[target, action,
background]`. Targets: desktop `1`, clock `2`, wave `3`, engine `4`.
Actions: start `0`, stop `1`, self-test `2`. Desktop accepts start/stop;
clock/wave accept start/stop; engine accepts only self-test. Background is
`0` or `1`, and `1` is valid only for clock/wave start. Earlier minors return
`ENOSYS`; invalid fields return `EINVAL`; an occupied queue, pending EXEC or
foreground job returns `EBUSY`. Rejection changes neither queue nor reply.

Acceptance returns complete/result `1`, meaning **queued**, not successfully
started. Sequence is preserved. The assembly wrapper explicitly clears carry:
set carry means scheduler suspension and must not leak out of a C helper.
No bank/graphics/engine action runs on the request stack. Init's bank-0 session
poll performs it after the caller yields and the task gateway has unwound.

This is a serialized root-session interface, not general per-task IPC. The
single completion mailbox reuses `$F3A0-$F3A4` as `[ready, target, action,
background, result]`. It is safe to reuse because EXEC first copies command
text privately. Producer publishes ready `$A5` last; `ush` consumes the reply
and clears ready before doing output. Ordinary stream requests do not touch it;
no new control/EXEC request is submitted while that completion is printed.
Managed-app results are 0 success, 1 not ready, 2 already running, 3 program
not found (also covers an unmounted command disk), 4 task slot busy, 5 invalid
program/loader ABI, and 6 disk I/O failure. These are service results, not
POSIX errnos. Busy is taken from the loader's direct return; its untouched
task-status record must not be mistaken for the latest error.
Result `0` means success, otherwise it is the selected service's error code;
`130` reports foreground interruption. WAIT reports foreground ownership;
`ush` prints notices, waits if necessary, and owns prompt rearming, including
suppression between RC lines. A later root command may replace the mailbox.
Callers must serialize commands and consume completion before submitting again.

Device/window/app services remain preloaded or retained as documented; this
boundary does not claim general processes, memory protection or loadable drivers.

## Filesystem capacity (0.6)

`STATFS`: descriptor/flags `0`, count `4`, payload `['/', 'm', 'n', 't']`.
Like MOUNT/UMOUNT, no terminating NUL is required. Older minors return
`ENOSYS`; invalid fields return `EINVAL`, no mount `ENOENT`, an open storage
handle `EBUSY`, and media/invalid-BAM errors `EIO`. Validation precedes I/O,
and the temporary channel is closed before returning. Existing handles are
never consumed or closed by a rejected request.

Success returns eight bytes (`result = 8`): little-endian 16-bit block size
(256), total data blocks (664 single-sided / 1328 double-sided), free data
blocks, then device and flags (bit 0 read-only; other bits zero). Counts come
from track 18/sector 0's CBM-DOS BAM, including second-side counts for a D71.
Directory tracks 18 and 53 are excluded, matching DOS free-block accounting.
These are allocation blocks, not payload bytes (linked file sectors reserve
two link bytes). No write support, filesystem repair, or media caching is implied.

## Read-only IEC mount (0.5)

`MOUNT`: descriptor/flags `0`, count `5`, payload `[device, '/', 'm', 'n', 't']`.
`UMOUNT`: descriptor/flags `0`, count `4`, payload `['/', 'm', 'n', 't']`.
Neither payload has a terminator. Earlier minors return `ENOSYS`. Success is
complete/result `0`; invalid fields are `EINVAL`. Duplicate mount or unmount
with an open handle is `EBUSY`; unmount without a mount is `ENOENT`.
An empty bus can report `ENODEV`; address-specific timeouts on a bus with
another drive report `EIO`. A failed mount never publishes the mount.

`OPEN /mnt` returns the single storage descriptor `4`; bootfs retains `3`.
Paths include the existing trailing NUL outside count. `GETDENTS` accepts
18–24 bytes and returns the existing type/name-length/name record, or zero at
end. It converts the two PETSCII uppercase ranges to console ASCII. `STAT
/mnt` returns a directory with size zero. `READ` on this directory returns
`EISDIR`; other invalid non-stdio descriptors return `EBADF`. Close is required
even after EOF or an I/O error. File `STAT` below `/mnt/` returns `ENOSYS`;
the service does not invent byte lengths from directory block counts. `/mnt-other` is not routed
to the mount. Other paths, bootfs handles, and lifecycle operations retain the
existing fallback. The shared record's sequence is preserved on every reply.

`OPEN /mnt/NAME` with descriptor `O_RDONLY` (`0`) opens a named file on that
same descriptor `4`. Names are 1–16 ASCII letters, digits, spaces, `.`, `-`,
or `_`; ASCII lowercase folds to uppercase. Both PETSCII uppercase ranges
compare equally; the first matching directory entry wins.
DOS commands, wildcards, embedded NULs and nested paths are rejected with
`EINVAL`. This is a deliberately restricted filename mapping, not a complete
PETSCII namespace. `O_DIRECTORY` on a file returns `ENOTDIR`. Closed SEQ, PRG,
and sequential USR files are supported; unclosed and REL files return `EINVAL`.

`READ` on descriptor `4` accepts counts 0–24. A zero count consumes nothing;
otherwise result is the explicit number of bytes in payload, including NULs
and the final recorded file byte. The sector chain's last-byte count defines
EOF, including empty and one-byte files; later reads return zero. A transport
failure after some bytes returns those bytes first, then `EIO` on the next
read; an immediate failure returns `EIO`. Failed opens publish no handle:
an absent directory name maps to `ENOENT`; malformed chains and
DOS/status/transport failures map to `EIO`.
`GETDENTS` on a file is `ENOTDIR`. Always `CLOSE`, including after errors.
The service uses read-only DOS `U1` sector reads, checking status before
consuming data. It rejects invalid track/sector addresses, inconsistent block
counts, truncated sectors and bounded chain exhaustion. A read error remains
sticky until close; it must not turn into successful EOF on a later request.
Unmount before changing media. Removal errors release the physical channel;
close/unmount/remount recovers without reboot. An immediate remount may return
`EIO` while the drive is still busy; retry after it settles. This is not an
automatic media-generation detector: undetected swaps during a live handle
are unsupported, especially disks with identical IDs/content.

This initial single-handle service is synchronous and IRQ-masked per request,
with finite transport waits and a maximum of 19 directory sectors per lookup
and 1,366 data sectors per file (also bounded by its directory block count). It does
not schedule, yield, call KERNAL, or call window code while its bank is mapped.
It is not yet per-process descriptor ownership or cancellation-aware I/O.

## Flags

Flags are operation-specific. The 0.2 operations define no flag bits; a
nonzero flags byte on a 0.2 operation remains a protocol error (`EPROTO`).
Reserved bits on a 0.3 operation are rejected with `EINVAL` once the operation
is implemented.

| Operation | Flag bits | Meaning |
|---|---|---|
| `WAITPID` | `0x01` `NOHANG` | Return immediately when no child is reapable. |

All 0.3 lifecycle operations require descriptor `0`; a nonzero descriptor is
rejected with `EINVAL`. The caller must be the task the kernel reports as
current and `RUNNING`: a lifecycle request from any other state is rejected
with `EINVAL`, and an undefined caller with `ESRCH`.

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
- The initial production handler releases the shared request record, marks the
  caller `ZOMBIE`, and returns only to the kernel poll frame; D71/D64 probes
  verify that the retired task cannot issue another request.

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
- Selector `0` waits for any child: when no zombie exists the selector stays
  `0` and the response is published when any child exits, not only the child
  that happened to be observed first.
- No matching child, including a target that is not a child of the caller or
  is outside the table: `ECHILD`.
- Reserved flag bits: `EINVAL`.

The production path implements immediate zombie reap, `NOHANG`, and blocking
waits. A blocking request is privately snapshotted, the shared record is
released, and child exit publishes the response only when the parent resumes.

### SLEEP (13)

- Request: `count = 2`; payload bytes `0-1` are the requested ticks in 1/60 s
  units, from `1` through `600` (ten seconds); flags `0`.
- Response on success: state complete, `result = 0`, errno `0`.
- Zero or out-of-range ticks: `EINVAL`.
- The scheduler maintains a 16-bit modulo clock normalized to 60 logical ticks
  per second by the raster IRQ: NTSC advances once per frame; PAL distributes
  six ticks over five frames. Durations are limited to 600, so signed deadline
  subtraction remains unambiguous across counter wrap.

### CANCEL (14)

- Request: `count = 3`; payload bytes `0-1` are the target task id, byte `2`
  is the eight-bit termination status (the conventional `Ctrl+C` result is
  `130`, `128 + SIGINT`); flags `0`.
- Response on success: state complete, `result = 0`, errno `0`. The status is
  recorded as the target's exit status and is returned by `WAITPID`.
- Unknown, reaped, or non-child target: `ESRCH`.
- Target id `0`, the caller's own id, or a bad count: `EINVAL`.
- Cancellation is limited to the caller's children: an unrelated live task is
  not cancellable through this operation.

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
- Before any allocation metadata changes, the loader resolves the executable
  and preflights the proposed placement. The candidate record holds the
  unchanged 16-byte UDEX header plus the proposed stack base and size, so a
  wrong magic, unsupported major or minor version, unsupported CPU,
  invalid executable flags, a zero-length image, or an entry outside the image is
  `ENOEXEC`; a missing, under-sized, or image-overlapping stack is `EINVAL`;
  an address-space overflow or overlap with the resident kernel, common RAM,
  display memory, or another task's allocation is `ENOMEM`. Valid UDEX 0.1
  flags are `0`, persistent `$01`, and managed `$02`; unknown bits and the
  combined `$03` value are rejected. Ranges may end exactly at the top of the
  address space.
- Tasking 0.1 has one ordinary allocation: task id 2 owns bank-1 APP1 at
  `$0200-$0BFF`, with relocated page zero/page one in physical pages
  `$D3/$D4`. A second child is rejected with `ENOMEM` until the first exits and
  is reaped. Publication is the final commit step: the image and BSS are
  installed, private context and stack pages are initialized, and only then is
  the lifecycle slot made `RUNNABLE`.
- The task begins through a common-RAM launcher at `$F280`. It calls the
  validated UDEX entry with zeroed A/X/Y; a normal `RTS` uses A as the exit
  status and issues `EXIT` through `$FF16`. The next successful load restores
  the overwritten loader status/header area before installing a fresh launcher.

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
| 17 | `EEXIST` | ambiguous folded filename or virtual-directory collision |
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

### POLL (16, introduced in 0.4)

- Request: descriptor `0` (stdin), flags `0`, count `4`. Payload bytes `0–1`
  contain a little-endian mask, currently exactly `0x0001` (readable).
  Bytes `2–3` contain a little-endian timeout in logical 1/60-second ticks:
  `0` for immediate, `1–600` for finite, `0xFFFF` for infinite.
- Response: complete, errno `0`, result `1` and mask `0x0001` when readable;
  result `0` and mask `0` when an immediate/finite wait expires. Preserve
  both timeout bytes and the original sequence; response flags remain `0`.
- Undefined callers receive `ESRCH`; a defined caller not current/`RUNNING`
  receives `EINVAL`; descriptors other than stdin receive `EBADF`; malformed
  flags, count, mask or timeout receive `EINVAL`. Validation precedes any
  lifecycle, allocation, or subscription mutation.
- A submitted line is readable through its final newline, including an empty
  line. `POLL` does not consume or reserve input: another permitted reader can
  drain it before `READ`, which may then return `EAGAIN`.
- Registration snapshots into the existing private per-task arrays and
  releases the shared request. A bounded eight-slot service scan observes
  readiness before finite expiry, marks the response ready once, and publishes
  only when the caller resumes. Infinite waits have no arithmetic deadline.
  Finite comparisons are wrap-safe provided the wake scan occurs within half
  the 16-bit clock period of the deadline.
- Ready stopped tasks remain stopped with a `RUNNABLE` saved resume state.
  Cancellation discards their subscriptions and responses. STOP/CONTINUE are
  still private lifecycle operations, not public request operations.

The 0.2 operations complete synchronously; they do not schedule, and `EXEC`
completion means only that the command was accepted for deferred resident
dispatch. The 0.3 lifecycle operations may context-switch: `YIELD`, a blocking
`WAITPID`, `SLEEP`, and a blocking 0.4 `POLL` return only when the caller is resumed; `CANCEL` and the
nonblocking calls return without switching, and `EXIT` never returns.

`$F359` is a single shared record, so a blocked task cannot retain ownership of
it. When a lifecycle request blocks or switches, the kernel snapshots the
request (operation, flags, sequence, descriptor, count, and payload) into the
task's own state, releases the shared record, and writes the response fields
back—preserving the original sequence number—immediately before that task
resumes from the `$FF16` gate. While the record is released, another task may
use it. A task cancelled while blocked never resumes, so no response is
written and the record stays available.

The persistent `/bin/ush` task blocks in `POLL(stdin, infinite)` while idle,
then reads the submitted line. It retains `YIELD` between bounded work passes
and the compatibility foreground-job `WAIT` path. The resident shell still
dispatches pending `EXEC` and graphical jobs, but its private input bridge
returns `EMPTY` while native ush advertises `READY` at `$F3D9`. Init resets
that ownership byte at boot; lifecycle-driven terminal ownership is deferred.
Other legacy UDEX entries
retain their existing return convention until they migrate to lifecycle tasks.

## Placement note

The fixed `$F800` request gateway uses 262 of its 265 reserved bytes as of ABI
0.3, and the host-testable policy compiles to 2,245 bytes (about 2.2 KiB) of
cc65 code without long-arithmetic helpers. The active scheduler core occupies
1,721 emitted bytes plus 154 bytes of BSS at `$C120-$C872`; the permanent
1,163-byte lifecycle request handler occupies `$C900-$CD8A` outside both
application slots. Its per-task wait snapshots preserve blocking requests
while the shared record is released. The policy module remains
compile-qualified but nonresident. ABI 0.4 uses bounded assembly equivalent to
the host-tested POLL policy; it adds no BSS. The measured remaining gaps are
141 bytes before `$C900` and 50 bytes before the fixed `$CDBD` context binding.

The preferred direction is to keep validation, lifecycle policy, and
scheduling in bank 0 and retain only a small MMU/context-switch tail in
always-mapped common RAM. Bank-0 space must first be reclaimed by extracting or
relocating transitional services; the C policy is not placed wholesale in
common RAM. [SCHEDULER-PLACEMENT.md](../docs/SCHEDULER-PLACEMENT.md) records
the measured budget, the fully occupied upper common RAM (zero uncontested
bytes), and the reclaim order with its emulator gates. The switch tail is
planned for the legacy `$FF05-$FFC4` reservation once the scheduler replaces
the implementation behind the frozen `$FF10`, `$FF13`, and `$FF16` entry
trampolines; those addresses remain the documented task-bank entry points.
