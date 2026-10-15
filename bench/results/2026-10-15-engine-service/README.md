# Engine IPC service slice 2

Issue [#60](https://github.com/salvogendut/UDEKS/issues/60), branch
`services-engine-ipc`, based on merged IPC `923e4a4`. Work is uncommitted.

The independently loaded ENGINE server and ENGTEST client provide NOP, exact
1–8 wave samples and authenticated acknowledged STOP through the copied IPC
SDK. The server uses the existing bounded worker gate and snapshots borrowed
output before IPC/yield. No private kernel imports or new resident slot are used.
This is an IPC broker checkpoint, not complete extraction of the worker core.

Host tests exercise the actual server/worker C and client SDK: exact bytes,
malformed envelopes, no partial outputs, no replay of accepted work, queue
backpressure, stop/ACK sender/sequence/operand validation, bounded timeout even
under junk traffic, retired peers and meaningful CLI error exits. Two evidence
tests bind all files, programs, disk hashes, placement and final machine bytes.
The complete host suite passes 1,768 tests.

Sibling native 1986 D81 passes NOP, exact eight samples and next phase 50,
missing/stopped server, acknowledged stop, one restart, real 1351 drawing and
clock dragging, code/stack guards and endpoint/queue cleanup. The passing run
resumes a verified private initial boot checkpoint from the earlier cold run.
The cold run and a diagnosis exposed an error-output bug: printing reset errno,
so ENOENT exited as 1. The saved error is now returned and regression-tested.
Those two failed logs/provenance are retained as incomplete evidence, not passes.
The emulator core is unchanged at `65c1fe660ce2b04b785937550d521614544f808d`.

Native reports bind the executed harness snapshots under `sources/`.
`final-sources/` records the final source/documentation state, including a
controller default-path fix that supports both root checkouts and linked
worktrees; it does not change the machine assertions or runtime service.
The compiled emulator executable, ROMs and ROM-bearing snapshots are excluded.

[Public demo disks and binary layouts](../../artifacts/2026-10-15-engine-demo/README.md).
All 24 server/client/clock/draw orders fit ordinary allocations. The normal,
panic and sealed hidden kernel hashes match IPC; existing IPC example binaries
also match byte for byte. D64 cannot fit 34 additional blocks and is skipped
without removing standard apps. No root downloads are refreshed.

Reproduce: `make engine-demo`, `make engine-native-probe`, `make check`.
The sibling emulator's local SDL3 and owned ROM bundle are required. See the
[development plan and manual commands](../../../docs/ENGINE-IPC.md).
Native D71, VICE runtime, live cancellation, extended restart soak, manual
acceptance and physical C128 remain later qualification. SHA256SUMS binds this
archive. No physical-machine acceptance is inferred.
