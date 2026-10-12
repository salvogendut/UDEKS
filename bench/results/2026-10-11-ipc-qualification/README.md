# IPC slice 3 — automated qualification

Base: pushed `1de24a4`; first increment `0a696a3`;
[issue #58](https://github.com/salvogendut/UDEKS/issues/58), branch
`ipc-0.1-qualification`. Manual emulator acceptance and physical C128 testing
are separate runs by user agreement and are not claimed here.

VICE D71 and D81 pass cancellation of each public peer during a pending
request, recovery, and twelve complete restart cycles per medium. Client
cancellation uses actual foreground Ctrl-C and the shell parent's CANCEL.
Server cancellation uses a public foreground server and the separate
WAITPING fixture; the orphaned peer exits with EAGAIN (11), rejects its stale
server handle with EBADF (9), and closes its endpoint. Fresh public programs
then exchange exact replies. Every restart checks monotonic handles, code and
stack guards, queue/endpoint cleanup and surviving graphical peers.

The expanded raw fixture passes fifteen boundary/lifecycle/coexistence checks
on each medium, including duplicate/overlong names, invalid operations and
receive capacity, pool exhaustion, foreign access, sixteen copied bytes,
full/empty/undersized receive, stale handles, EXIT/CANCEL cleanup and reuse.
Kernel and SDK binaries remain unchanged from the previous slices.

Native 1986 D81 passes exact and maximum replies, parent client cancellation,
recovery, three restarts, real 1351 drawing and clock dragging, code/stack guards
and cleanup. The final run resumes the private initial checkpoint made by a
verified cold boot in the earlier coordinate-failure run. It qualifies the
pinned native engine; the installed Flatpak app is not claimed as qualified.
Four evidence checks and all 1,750 host tests pass, along with placement,
graphical application and IPC layout gates.

## Evidence layout

- `vice-d81-client-cancel` and `sources`: preserved first increment with three
  restarts; the original source snapshots remain historical.
- `vice-d71-both-peers` / `vice-d81-both-peers`: final twelve-cycle runs and
  captures, bound to public program hashes and the disposable WAITPING disk.
- `waiting-peer` / `both-peer-sources`: test-only peer and lifecycle probe.
- `vice-boundary-d71` / `vice-boundary-d81`: expanded raw-gate results;
  `raw-fixture` / `boundary-sources` bind their actual programs and probe.
- `native-1986-d81` contains the passing report, provenance and raw captures;
  `native-sources` and SDL build records identify its unchanged pinned engine.
- Native attempt logs preserve incomplete boot, short-budget and wrong
  clock-coordinate runs honestly; none of those attempts is a complete pass.

Base disks match the [slice-2 public images](../../artifacts/2026-10-11-ipc-examples/README.md).
The lifecycle probe observes pending work and queues ordinary Ctrl-C keyboard
input in one paused monitor session before restoring the live MMU and resuming
normal shell processing. Graphical VICE checks use the documented temporary
pointer-getter patch and acknowledged WM click. No IPC or task state is
fabricated. The native harness uses actual keyboard and 1351 events.

`program -q` requests graphical CLOSE; console-only IPC programs do not consume
it. Graceful public shutdown is `ipcping --stop`. No shell cancellation command
was added. Common VICE status observations now explicitly read physical bank-0
RAM. An earlier D71 command-wait timeout is retained; no unproven cause is claimed.

Reproduce with `make ipc-boundary-probe`, `make ipc-lifecycle-probe`,
`make ipc-native-1986-probe` and `make check`. Native source/SDL/ROM setup and
separate manual/hardware instructions are in the
[qualification document](../../../docs/IPC-QUALIFICATION.md).

SHA256SUMS binds every preserved file. ROMs, emulator binaries and ROM-bearing
snapshots are excluded. D64 public demo images remain skipped because they do
not fit the standard application disk.
