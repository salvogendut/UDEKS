# Bank-task request ABI 0.2

Bank-1 8502 tasks exchange bounded requests with the resident kernel through a
38-byte record in top common RAM. The task fills the record and calls `$FF16`.
That gate swaps cc65 zero-page contexts, selects bank 0, dispatches through the
fixed `$CF30` vector, and restores bank 1 before returning.

## Record

The record occupies `$F359-$F37E`:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `UTRQ` |
| 4 | 1 | ABI major (`0`) |
| 5 | 1 | ABI minor (`2`) |
| 6 | 1 | State |
| 7 | 1 | Operation |
| 8 | 1 | Sequence number |
| 9 | 1 | Unix-style file descriptor |
| 10 | 1 | Requested byte count, at most 24 |
| 11 | 1 | Completed byte count |
| 12 | 1 | Linux-compatible errno value |
| 13 | 1 | Flags; zero in ABI 0.1 |
| 14 | 24 | Inline payload |

States are idle (`0`), request (`1`), complete (`2`), and error (`$80`). ABI
0.2 implements `READ` (`1`), `WRITE` (`2`), `EXEC` (`3`), `WAIT` (`4`), and
`PROMPT` (`5`). Descriptors use the Unix convention: standard input is 0,
standard output is 1, and standard error is 2.

Writes accept binary chunks rather than zero-terminated strings. Reads consume
submitted console lines in chunks and include the terminating newline. They are
nonblocking: when no line is ready, the call returns error state with `EAGAIN`
(11). This lets a shell poll return to init so input, graphics, windows, and Z80
work continue to receive service.

`EXEC` is the bounded migration bridge for commands whose policy has not yet
moved out of the resident compatibility shell. The task copies at most 54
bytes of command text to `$F3A0-$F3D6`; the kernel copies it into private
resident storage and returns result 1 after queuing it. The bank-0 shell poll
performs dispatch only after the bank-1 request gate has unwound, so a command
may safely hand ownership to the Z80 without leaving a bank-switched task frame
on the 8502 stack. `WAIT` returns 1 while that queued or foreground job owns the
session and 0 after the resident job path has restored the prompt. `PROMPT`
rearms the root terminal input field.

The boundary uses the familiar Linux errno numbers `EIO` (5), `EBADF` (9),
`EAGAIN` (11), `EINVAL` (22), `ENOSYS` (38), and `EPROTO` (71). The task runtime exposes
`udeks_read`, `udeks_write`, `udeks_write_byte`, and `udeks_errno`; the API is
deliberately small, but its descriptors, short reads/writes, and error model are
compatible with later POSIX-shaped libc veneers.

A request call itself is synchronous, not a scheduler yield; `EXEC` completion
means that the command was accepted for deferred resident dispatch. A
cooperative program must return from its `$9000` poll entry when it has no more
immediate work.
