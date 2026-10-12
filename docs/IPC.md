# Bounded message IPC

The next architectural slice lets two independently disk-loaded native C
programs exchange requests and replies while the shell and graphical peers
remain usable. The baseline is merged REU graphics (`4644a4c`). Slice 1
implements the foundation described in [the wire contract](../abi/ipc.md). Slice 2 adds the [native SDK and public server/client demo](IPC-SDK.md). Slice 3 completes automated qualification. The user confirmed the manual emulator check on 2026-10-12. Physical C128
testing remains a separate follow-up run.

## First increment

Use the existing cooperative scheduler and bank-task request gate. Copy small
messages into owned storage before returning to the sender; never retain a
pointer into another task's bank or runtime. Endpoint ownership must include
the task's lifetime, so closing, exiting, cancelling and reusing an allocation
cannot grant access to an earlier instance's messages.

The foundation provides two named endpoints, one queued message per endpoint
and a 16-byte inline payload. Handles are monotonic 16-bit serials that never
repeat within a boot; exhausting the serial space fails closed until reboot.
Send and receive are nonblocking: a full queue or empty receive returns a retryable error,
and clients yield or sleep between attempts. A receive with insufficient
capacity must leave the queued message intact. Reject oversized messages
before modifying a queue.

Separate endpoint discovery from receive ownership. A client may discover a
named server endpoint and send to it, but only its owner may receive or close
it. Replies use a validated destination handle carried in the request;
sender identity is supplied by the IPC boundary rather than trusted from
payload bytes. The wire contract defines stale-handle detection, exhaustion
and duplicate-name errors before the SDK is exposed.

## Delivery gates

1. Inventory normal and panic placement, request dispatch and task retirement
   hooks on the merged baseline. Reserve code, queues and metadata without
   shrinking the four executable allocations, stacks, display backing or
   recovery path. Establish the wire contract and ownership/error policy.
2. Implement endpoint creation/discovery, send, receive and close, plus cleanup
   on every task retirement path. Add an SDK and two separate disk programs:
   a server and a client exchanging counted requests and replies. Neither
   program requires a kernel name table or a hardcoded peer allocation.
3. Qualify actual disk loading and message contents in VICE and 1986, with
   console and graphics running. Cover full/empty queues, malformed requests,
   foreign receive/close, duplicate names, stale handles, cancellation of
   either peer, endpoint reuse and repeated restart. Preserve exact demo
   images and provide a short manual acceptance sequence.

Host policy tests cover ownership and queue transitions; emulator tests must
exercise the public banked gate and real task lifecycle. Run the existing
placement, app, input and console regression gates. Emulator qualification
does not imply physical C128 acceptance.

## Scope

This increment does not require preemption, a general task allocator, dynamic
message allocation, transferred file handles, a daemon framework or further
service extraction. IPC storage must work without REU. Blocking waits and
service migration can follow once the bounded exchange and cleanup gates pass.

## Slice 1 placement

The existing checked startup image has enough physical bank-0 RAM under I/O
for IPC without REU, display-pool reductions or a new loader. IPC adds 602 code
bytes and 64 state bytes there, plus 32 resident bytes for request/retirement
veneers. Normal and panic links leave 24 bytes before the service startup
reservation and 68 bytes before the hidden image trailer. Public gate addresses,
all four native image/stack allocations, recovery bootfs and retained drawing
storage remain within their established limits.

`make ipc-layout-check` measures both links. `make ipc-check` executes the real
6502 policy, common request dispatcher, router and retirement hook under
sim6502, including an independent queue oracle, exhaustion and a missing-hook
negative control. `make ipc-fixture` builds the raw-gate test executable;
`make ipc-probe` runs its D81/D64 VICE checks. This fixture is qualification
infrastructure, not the slice-2 SDK or a normal boot application.

[Slice 1 candidate disks, evidence and limits](../bench/results/2026-10-11-ipc-foundation/README.md).

## Slice 2 SDK and examples

The optional native SDK wraps the banked gate and validates reply envelopes
before copying outputs. Independent `IPCSRV.BIN` and `IPCPING.BIN` exchange
counted messages, authenticate the sender and perform an acknowledged graceful
shutdown. They fit alongside xclock/xdraw in all 24 launch orders without
changing the slice-1 kernel. Full D71/D81 media preserve standard applications;
D64 lacks space and is skipped by user agreement.

[SDK usage](IPC-SDK.md) and [candidate media/evidence](../bench/results/2026-10-11-ipc-examples/README.md).
Slice 3 completes both-peer cancellation, twelve restarts per medium and
expanded boundary checks on VICE D71/D81, plus native 1986 D81 IPC/input
qualification. The user confirmed manual emulator acceptance on 2026-10-12; physical-C128
testing remains pending for a separate run. [Qualification evidence and reproduction](IPC-QUALIFICATION.md).
