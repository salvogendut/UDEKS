# Disk-loaded Z80 engine service — issue #60

Branch `services-engine-ipc`, worktree `build/engine-ipc`, based on merged IPC
`923e4a4`. [Candidate message contract](../abi/engine-ipc.md).

## Slice 1 checkpoint

Slice 1 defined NOP and 1–8 wave samples per request, validates the envelope and
operand bounds, and measures separately linked native server/client probes.
The probes include IPC, worker-gate access, private output copy, bounded sleeps,
console output and close dependencies. They are named EPLSRV/EPLCLI and **must
not be used as runnable services**: live receive/reply validation, pending peer
state, STOP/ACK handling and complete retirement paths are absent from these probes. Their
sizes are checkpoints, not upper bounds on the final implementation.

Server: 3,955 file bytes, 3,269 installed image bytes and 33 BSS bytes. Client:
3,177 file bytes, 2,631 image bytes and 9 BSS bytes. Both fit ordinary tasks 3/5
without adjacent-slot borrowing. The server has 538 bytes remaining before
task 5's protected stack page. Server/client plus native clock/draw fit all 24
launch orders. They require all four ordinary task allocations; four graphical
apps plus the service are not supported. No resident bytes or permanent module
slot are added. Normal boot/disks and current worker users are unchanged.

Four host tests check envelopes, operations/control bounds, NOP output
preservation, and the actual worker C against a frozen existing-wave oracle:
8,192 phase/step/count combinations, untouched output tails and final phase
wraparound. This is host/compiler evidence, not machine qualification.
The complete `make check` suite passes 1,754 tests.
[Preserved slice-1 evidence](../bench/results/2026-10-14-engine-contract/README.md).

```sh
make engine-contract-check engine-placement
make check
```

Slices 1–2 are committed as `9d109fa` on `services-engine-ipc`.
Slice 3 qualification is recorded in [ENGINE-QUALIFICATION.md](ENGINE-QUALIFICATION.md),
including cancellation fixtures, protocol bounds, restart soak, migration and
separate manual/physical acceptance. Native emulator checks use
the sibling `../1986`, currently clean revision
`65c1fe660ce2b04b785937550d521614544f808d`, rather than the Flatpak. Its existing
binary is built with `-O3 -march=native -mtune=native -flto=2` and its local SDL3.
Record the actual revision for every run; never change emulator core behavior
to make a UDEKS test pass. ROM-bearing snapshots remain private.

## Slice 2 implemented

`ENGINE.BIN` is a separately scheduled C server, and `ENGTEST.BIN` is an
independent console client. `user/include/udeks/native_engine.h` exposes NOP,
wave and acknowledged STOP. WAVE validates count 1–8 and copies samples/result
only after authenticated envelope validation and successful endpoint close.
Errors leave caller outputs unchanged. Accepted work is never resent; mailbox
backpressure and response waits are bounded. A STOP reply alone does not
retire the server: it waits for the matching sender/sequence ACK. Missing ACKs
expire even under junk traffic; a cancelled peer cannot strand the server.

The server still uses the published synchronous worker gate. This is an IPC
broker and migration checkpoint, not complete extraction of the engine policy
or worker image from the kernel. Surface rows/chunking, multi-client routing,
new copy/checksum operations, preemption and default xwave migration are deferred.

Measured delivery: server 3,938 file bytes, 3,200 installed bytes and 29 BSS,
fits tasks 3/5; client 4,536 file bytes, 3,656 installed bytes and 43 BSS, fits
task 3. All 24 server/client/clock/draw launch orders fit without joining slots.
The build opts into counted-output-only runtime helpers for these programs;
normal SDK output helpers remain available by default. Kernel/hidden/panic
hashes and both existing IPC example binaries are unchanged. D71/D81 demo disks
add only the two executables; D64 cannot fit their 34 blocks alongside standard
apps and is skipped. The server leaves 158 bytes of file-staging headroom in
slot 5; the client leaves 72 in slot 3. Keep future growth measured.

Host tests cover 8,192 wave inputs, SDK malformed replies/output guards,
backpressure/timeouts, actual server C with the worker C, invalid STOP/ACK and
peer retirement, plus preservation of CLI exit errors after successful output.
All 1,768 host tests and the layout, placement and graphical-app gates pass.
Native sibling 1986 D81 passes NOP/exact eight-byte samples and final phase,
missing/stopped server, acknowledged stop, one restart, actual 1351 drawing and
clock drag with the service alive, code/stack guards and final cleanup. The
passing run resumes a verified local initial boot checkpoint; the prior cold
boot and diagnosis exposed the CLI error-output bug, whose logs are preserved.
That bug is fixed and regression-tested. No emulator core patches or fabricated
IPC/task state were used. Those are the preserved slice-2 results; see the
qualification document for subsequent slice-3 results and open checks.

```sh
make engine-programs
make engine-demo
make engine-native-probe
make check
```

Boot [the D71/D81 demo disks](../bench/artifacts/2026-10-15-engine-demo/README.md)
and enter:

```text
xclock &
xdraw &
engine &
engtest --nop
engtest
engtest --stop
engine &
engtest
engtest --stop
```

Expect `engine: ready`, then `engtest: OK` for each successful client. The
ordinary `engtest` independently checks eight exact samples and next phase 50.
After shutdown, `engtest` prints an error; `echo $?` reports ENOENT (2). Move
and draw while the engine is available, then verify another successful request.
Do not use `engine -q`: acknowledged shutdown is `engtest --stop`.

[Preserved slice-2 source, provenance and raw evidence](../bench/results/2026-10-15-engine-service/README.md).
