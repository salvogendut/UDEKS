# Bounded message IPC ABI

UTRQ **0.21**, operation **29**, exchanges copied messages through the existing
38-byte request record and `$FF16` banked gate. Its descriptor selects the
suboperation below; flags must be zero. IPC calls return synchronously without
yielding. They accept native scheduler callers 1–8, identified by the router,
and reject synchronous foreground/bootstrap contexts with `EACCES` (13).
Operation 29 requires minor 21; older minors return `EINVAL` (22). The common
gate continues accepting earlier minors for existing operations; unsupported
future versions and malformed signatures return `EPROTO` (71).

## Endpoints and ownership

There are **two endpoints**, each with one mailbox containing **1–16 bytes**.
Each endpoint has a unique, case-sensitive name of 1–8 printable ASCII bytes
(33–126, no spaces). Names are counted, not NUL-terminated; trailing request
bytes are ignored and normalized internally. Any native task may discover an
endpoint and send to it. Only its creating task may receive or close it.

A handle is a nonzero 16-bit little-endian serial, issued monotonically across
both endpoints. Serial values are never reused during a boot. After issuing
65535, CREATE returns `ENOSPC` until reboot even when endpoints are free.
Closing an endpoint invalidates its handle before reuse. Retirement closes all
endpoints owned by the departing task before its task allocation is reused.
A message carries the sender's validated source-endpoint handle; the sender
must own that endpoint. This handle identifies its endpoint lifetime, rather
than a recyclable task ID or an untrusted payload identity.

## Requests and replies

All offsets below are relative to the request's 24-byte payload. COUNT is the
input size on entry and output size on success. RESULT equals output COUNT.
Successful calls set COMPLETE and errno zero; errors set ERROR, RESULT zero
and the listed errno. Sequence, operation, descriptor and flags are preserved.
Clients must not assume COUNT is unchanged on success. Unused reply bytes are
unspecified and must not be interpreted.

| Descriptor | Input COUNT and payload | Successful output |
| --- | --- | --- |
| 0 CREATE | 1–8 name bytes | COUNT 2, new handle at 0 |
| 1 LOOKUP | 1–8 name bytes | COUNT 2, existing handle at 0 |
| 2 SEND | COUNT 5–20: destination handle at 0, source handle at 2, message at 4 | COUNT 0; complete copy queued |
| 3 RECEIVE | COUNT 3: owned handle at 0, capacity 0–16 at 2 | COUNT 3–18: source handle at 0, message at 2 |
| 4 CLOSE | COUNT 2: owned handle at 0 | COUNT 0 |

CREATE returns `EEXIST` (17) for an existing name and `ENOSPC` (28) for a full
pool or exhausted serial space. LOOKUP returns `ENOENT` (2) for a missing name.
Unknown/closed handles return `EBADF` (9); foreign receive/close or a foreign
source endpoint returns `EACCES` (13). SEND to a full mailbox and RECEIVE from
an empty mailbox return `EAGAIN` (11). Clients may sleep/yield before retrying;
no blocking IPC wait or timeout is provided.

RECEIVE returns `EMSGSIZE` (90) when capacity is too small, including zero for
any queued message. It leaves that message queued. Zero-length SEND, oversized
messages, invalid names, reserved flags, unknown suboperations and malformed
counts/capacities return `EINVAL`. Validation completes before modifying any
endpoint or queued message. Rejected calls may normalize bytes in the shared
request payload; their endpoint/queue/serial state remains unchanged. Handle
validation can precede suboperation-specific count checks, so malformed calls
with an invalid handle may return `EBADF`.

## Lifetime and scheduling

SEND copies bytes before returning; changing the request or yielding cannot
change the queued message. A successful RECEIVE consumes the entire message.
There is no partial receive, retained task pointer, transferred file handle or
message allocation. A task may own both endpoints, including self-send.

CLOSE and EXIT/CANCEL discard the departing endpoint's own mailbox and any
queued message in the other endpoint whose source is the departing handle.
Thus messages from a retired sender do not cross task-allocation reuse.
Closing a destination drops its queued message; no delivery receipt or
request/reply completion guarantee is implied. Peers must handle `EBADF` and
rediscover/restart explicitly. A server can reply to the authenticated source
handle received with a request while that endpoint remains live.

The service uses the existing serialized gate and trusted `$C883` retirement
hook. Code and initialized state share the checked startup image in physical
bank-0 RAM under I/O. IPC does not use REU and stays available when the graphical
desktop stops. CPU simulation checks policy/dispatch; real MMU, scheduling and
retirement behavior require emulator qualification.

The native C wrapper and independently loaded examples are documented in
[the SDK guide](../docs/IPC-SDK.md).
