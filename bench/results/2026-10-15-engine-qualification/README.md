# Engine IPC service qualification

Issue [#60](https://github.com/salvogendut/UDEKS/issues/60), branch
`services-engine-ipc`, production base `9d109fa`. This archive is a slice-3
checkpoint built on the unchanged slice-2 production binaries.
See [acceptance, reproduction and migration decision](../../../docs/ENGINE-QUALIFICATION.md).

`vice-d71-soak` and `vice-d81-soak` cold-boot the full candidate with clock/draw,
exercise both public peers' real parent cancellation, stale handles and recovery,
104 raw protocol exchanges (96 exact waves, NOP and seven invalid requests),
then complete twelve start/NOP/WAVE/acknowledged-stop cycles. Endpoint handles
increase, code/stack guards and task canary survive, queues/endpoints clear,
and the graphical peers remain available. Each report binds its disposable
test disk, production/fixture binaries and the actual executed harness snapshot.

`vice-d71-cancel` and `vice-d81-cancel` rerun the same checks
with one cycle and the final stricter observation: server ACK-wait state, peer
state and both endpoint owners read from physical RAM before Ctrl-C is queued.
The earlier 12-cycle reports do not claim that additional recorded observation.

`native-1986-d81` passes both public peers' real keyboard Ctrl-C cancellation,
ACK-timeout recovery, stale-handle rejection, three restart cycles, exact
samples/NOP, missing/stopped service, real 1351 drawing and clock dragging,
code/stack guards and cleanup. Its unmodified sibling core is revision
`65c1fe660ce2b04b785937550d521614544f808d`, with local SDL3 3.4.8.
This passing run resumes the verified private initial-boot checkpoint from
slice 2; it is not another full cold-boot pass. ROM-bearing checkpoints remain
private. Earlier slice-2 evidence remains in `2026-10-15-engine-service`.

Preserved failures/incomplete runs are explicitly unqualified:

- `native-d71-loading-failure`: unmodified real-1571 native core cold-boots,
  but the existing TIME.SVC startup reports an I/O error; ENGTEST then fails
  loading with error 13 and client state zero. No engine request was executed.
- `native-d81-incomplete-soak`: wrapper timeout; seven of twelve restart cycles
  completed, but there is no final PASS. It does not qualify twelve native cycles.
- `native-d81-incomplete-cancel`: wrapper timeout after a recovered exchange;
  it has no final PASS and does not qualify both peers or a complete soak.

The temporary native source snapshots are bound to provenance, including the
clean sibling revision, compiler/SDL3, complete core C/header hashes, local ROM
hashes, input media and runner hash. No emulator core patch is part of this work.

`fixtures/peer` and `fixtures/bounds` preserve test-only programs/maps/layouts.
They fit ordinary slots 3/5 and are only added to disposable qualification
media. Standard demo disks still add just ENGINE and ENGTEST. Production
programs/maps and public disks remain in `bench/artifacts/2026-10-15-engine-demo`.

The host bounds fixture runs against actual worker C/protocol validation and
completes 104 replies, 97 worker jobs and one endpoint close. Existing host
tests cover full/empty queues, bounded backpressure, no replay after acceptance,
malformed replies, unchanged caller outputs, STOP/ACK validation and retirement.
`host-1769.log` records the completed full host gate before archive tests were
added; `host-1773.log` records the final full gate including those four tests.
`placement-gates.log` records the final kernel/app placement gates. Kernel,
hidden/panic and production engine program hashes match the slice-2 baseline.

`final-sources/` records the final working sources/docs; per-run snapshots
identify the actual harness for each historical run. `manifest.json` binds
reports, production binaries and final sources. `SHA256SUMS` covers every
preserved file. ROMs, emulator executables and private snapshots are excluded.

Migration decision: retain direct-worker xwave by default. Surface chunks,
private row assembly, protocol versioning and fresh task/endpoint placement
must be designed and measured before an opt-in migration. No accepted job is
silently replayed via another transport. Manual emulator and physical C128
acceptance remain separate, open runs; supplemental native D71 loading remains
an explicitly unqualified drive/storage investigation.
