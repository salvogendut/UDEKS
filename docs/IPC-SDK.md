# Native IPC SDK and examples

Slice 2 exposes the bounded [IPC contract](../abi/ipc.md) to independently
loaded native bank-1 C programs. Include `udeks/native_ipc.h` and build with
`tools/build_native_console.py`; its optional library member is linked only
when used. Include `udeks/task_request.h` for symbolic errno values.

| Call | Success | Failure |
| --- | --- | --- |
| `udeks_ipc_create(name)` | Nonzero owned handle | 0 |
| `udeks_ipc_lookup(name)` | Nonzero discovered handle | 0 |
| `udeks_ipc_send(destination, source, buffer, count)` | 0 | `UDEKS_IO_ERROR` |
| `udeks_ipc_receive(endpoint, &sender, buffer, capacity)` | 1–16 copied bytes | `UDEKS_IO_ERROR` |
| `udeks_ipc_close(endpoint)` | 0 | `UDEKS_IO_ERROR` |

Failures set `udeks_errno`. Names are NUL-terminated printable ASCII, 1–8
characters. Send copies 1–16 bytes immediately; receive supplies an
authenticated sender handle. Use task-private buffers. Receive leaves both
outputs untouched on failure, including an undersized buffer. The SDK checks
the returned envelope and operation-specific lengths before copying outputs.

Calls are nonblocking. On `EAGAIN`, explicitly yield or sleep before retrying.
The SDK performs no implicit retry. Close owned endpoints when finished;
EXIT/CANCEL also retire them. Retirement discards queued messages sourced from
the departing endpoint, so a sender must stay alive until its final message is
consumed. Two endpoints and one queued message each are available per boot;
handles never repeat until reboot. See the wire contract for exact errors.

## Build and run

`make ipc-demo` builds two separate disk executables and adds them to full
standard D71/D81 images in `build/ipc/demo/`. The D64 image has 16 free blocks;
the examples need 33, so D64 is skipped without removing standard applications.
The manifest records hashes and verifies all 24 launch orders with `xclock`
and `xdraw` within the existing four allocations.

Boot either demo disk, then enter:

```text
xclock &
xdraw &
ipcsrv &
ipcping hello
ipcping 1234567890abcde
ipcping --stop
```

Expect `reply: HELLO`, `reply: 1234567890ABCDE`, and a stopped-server message.
`echo $?` reports 0 after a successful client. Move the clock and draw while
the server runs; the console remains available. The server sleeps for 60
scheduler ticks before each data reply to make cooperative waiting observable.
This delay is application work, not a measurement of IPC latency.

`ipcsrv demo &`, `ipcping demo Zebra`, and `ipcping demo --stop` demonstrate named
discovery and restart. Text must contain 1–15 characters because the 16-byte
message includes a kind byte. Missing servers and overlong input exit with 2.
The client reserves endpoint name `reply`; run one client at a time and choose
a different server name. Neither executable hardcodes a peer task allocation.

Use `--stop` because the shell reserves `program -q` for task cancellation.
Shutdown uses STOP, STOPPED and ACK messages. The client keeps its endpoint
alive until the server consumes ACK and closes; the server keeps its endpoint
alive until STOPPED is consumed. This respects retirement's queued-message
cleanup. Example retries and waits are bounded at 600 sleep steps.

## Qualification

`make ipc-demo-probe` cold-boots D71 and D81 through the shell, loads both
programs from disk, verifies exact binary replies and untouched code/stack
guards, and exercises coexistence, maximum text length, errors, shutdown and
restart. It observes all four native tasks during a pending request and checks
clock scheduling, window movement and drawing. It never fabricates IPC or task
state. Host SDK tests cover malformed replies, argument bounds and output
preservation. Slice 3 adds both-peer cancellation and twelve restarts per
medium, expanded raw boundaries and native 1986 D81 IPC/input checks.
[Automated qualification](IPC-QUALIFICATION.md) is complete; the user confirmed manual emulator
acceptance on 2026-10-12. Physical C128 testing remains pending separately.

[Passing D71/D81 VICE evidence and preserved candidate disks](../bench/results/2026-10-11-ipc-examples/README.md).
