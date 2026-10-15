# Engine IPC candidate 0.1 — slice 1

Issue [#60](https://github.com/salvogendut/UDEKS/issues/60). This is a proposed
wire contract and compiler-placement checkpoint, not a delivered service.
Native clients use the published copied-message IPC SDK. An independently
scheduled `ENGINE.BIN` will own endpoint `engine`; one active client owns
`engreply`. The two-endpoint pool permits one request/reply pair, so clients
serialize and fail clearly on endpoint contention. No task ID is on the wire.
Both handles come from the kernel; replies must match the discovered server
handle and the request sequence. A client binds each transaction to that handle,
never silently rebinding to a newly restarted server.

All words are little-endian. Each request is exactly eight bytes:

| Offset | Meaning |
| --- | --- |
| 0 | Version 1 |
| 1 | REQUEST=1, STOP=3, ACK=4 |
| 2–3 | Nonzero client sequence, scoped to this transaction and peer handle |
| 4 | Existing worker opcode: NOP=0 or WAVE=4 |
| 5 | Wave phase, unsigned byte |
| 6 | Wave phase step, unsigned byte |
| 7 | Sample count: 1–8 for WAVE, zero for NOP |

NOP, STOP and ACK require zero bytes 4–7. WAVE allows any phase/step byte,
including zero step. Samples are the existing signed-byte 64-entry wave table,
returned as byte values; sample i indexes `((phase+i*step) modulo 256) >> 2`.
Worker result is the phase after the final increment, zero-extended to LE16.
NOP returns result zero and no samples. This preserves the existing integer
wave profile; it is not a newly calculated sine function.

Replies are exactly 8 + sample-count bytes:

| Offset | Meaning |
| --- | --- |
| 0 | Version 1 |
| 1 | REPLY=2 |
| 2–3 | Echoed request sequence |
| 4 | Errno; zero on success |
| 5–6 | Worker result LE16; zero on error or STOP |
| 7 | Sample count; zero on error, NOP or STOP |
| 8–15 | Up to eight private copied sample bytes |

Invalid length/version/sequence/kind is EPROTO (71); invalid operation-specific
operands are EINVAL (22); unsupported worker opcodes, including surface rows,
are ENOSYS (38). Reply only when version and a nonzero sequence are recoverable
from at least four request bytes; otherwise discard without executing work.
A client validates source, version, kind, sequence, errno/count/result shape
and exact length before changing caller outputs. Never copy borrowed worker
output after yielding: snapshot it into private memory immediately following
the synchronous operation-24 worker gate (ABI 0.11), before another syscall.
That gate returns result count 3; its payload holds result LE16 and sample count.
No private kernel functions or map-generated imports are used.

Each send/receive wait is bounded to 600 one-tick sleeps. Retry SEND only on
EAGAIN before successful enqueue; do not resend accepted work after a reply
wait expires. Missing server returns ENOENT, stale peer EBADF, exhausted waits
EAGAIN and endpoint contention the CREATE error. Reply SEND failures caused
by a retired client discard the result and leave the server available. Other
transport failures report a service error and retire normally. No IPC call
implicitly retries. Sequence matching is correlation, not durable exactly-once
execution or protection from arbitrary RAM writes on a machine without an MPU.

For STOP, the server sends a zero-data successful reply and waits for ACK with
the same authenticated client handle and sequence. The client stays alive
until LOOKUP proves the old server endpoint gone or replaced. Only then may
it close its own endpoint. The server closes after consuming ACK; ordinary
replies leave the server alive. A missing ACK times out back to normal serving,
without claiming successful shutdown. Ignore unmatched ACKs. EXIT/CANCEL purges
owned endpoints and outbound queued messages; it is never safe to enqueue a
reply and immediately exit. Cancellation uses the actual trusted parent path.

Surface rows currently produce 25 or 50 bytes and cannot fit one reply. They,
checksum/copy operations, chunking, multiple clients and default xwave migration
are outside this checkpoint. The kernel retains MMU/CPU ownership and bounded
handoff. Existing worker clients and the time service remain unchanged.
