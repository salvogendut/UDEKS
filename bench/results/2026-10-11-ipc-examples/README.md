# IPC slice 2 — native SDK and independent examples

Candidate on `ipc-0.1-foundation`, based on `4644a4c`, following
[slice 1](../2026-10-11-ipc-foundation/README.md). These local changes are
uncommitted. [Public SDK guide](../../../docs/IPC-SDK.md).

## Bootable media

- [Full D71 demo](../../artifacts/2026-10-11-ipc-examples/udeks-ipc.d71)
- [Full D81 demo](../../artifacts/2026-10-11-ipc-examples/udeks-ipc.d81)

Both preserve the standard applications and add only separately linked
`IPCSRV.BIN` and `IPCPING.BIN`. D64 has 16 free blocks and needs 33 for the
examples; the user approved skipping D64. `make ipc-demo` reproduces the media.
The client file is 4,400 bytes and fits task 3; the server is 3,788 bytes and
fits tasks 3 or 5. All 24 launch orders with xclock/xdraw fit existing allocations.
No task capacity, display backing, stack or IPC kernel change belongs to slice 2.
`kernel-parity.json` records identical normal/panic/hidden kernel hashes.
`optional-sdk-parity.json` records a byte-identical rebuild of the old ticker.

## Manual acceptance

Boot either demo image and type:

```text
xclock &
xdraw &
ipcsrv &
ipcping hello
ipcping 1234567890abcde
ipcping --stop
```

Expect `reply: HELLO`, `reply: 1234567890ABCDE`, then a stopped-server message.
Move the clock and draw while the server runs. `echo $?` after a successful
client prints 0. `ipcping hello` after shutdown prints an IPC error and exits 2.
`ipcsrv demo &`, `ipcping demo Zebra`, `ipcping demo --stop` exercise named
restart. The shell reserves `program -q` for cancellation; `--stop` uses IPC.
One client may run at a time; `reply` is its reserved endpoint name.
Each data reply deliberately sleeps for 60 scheduler ticks, making cooperative
waiting visible. This is application work, not an IPC performance measurement.

## Evidence and limits

The host suite passes 1,746 tests, including 11 compiled SDK tests for binary
copying, malformed reply envelopes, exact bounds, output preservation and
nonblocking behavior. Normal/panic placement and graphical capacity checks pass.
VICE raw captures and reports verify ordinary shell/disk loading, exact
request/reply contents, authenticated sender handles, unchanged application
code/stack guards, maximum payload, missing server and oversized text errors,
client cleanup, graceful shutdown, endpoint reuse and restart. All four native
tasks are observed during a pending request; clock scheduling, window movement,
drawing and the usable console are checked. Pointer getters are temporarily
patched and a WM click is injected; no IPC or task state is fabricated.

SDK sources and build/probe tools are snapshotted in `sources/`; manifests and
SHA256SUMS bind them to the demo media and raw evidence. No ROM snapshots are
included. This is automated VICE qualification, not manual acceptance.
Native 1986 IPC, broader cancellation/soak cases and physical C128 acceptance
remain slice 3. Slice-1 raw-gate queue/lifetime tests remain separate evidence.
