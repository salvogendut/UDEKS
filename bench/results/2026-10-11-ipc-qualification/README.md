# IPC slice 3 — first qualification increment

Base: pushed `1de24a4`; [issue #58](https://github.com/salvogendut/UDEKS/issues/58).
Branch: `ipc-0.1-qualification`. This new qualification work is uncommitted.

The focused VICE D81 run passes real foreground Ctrl-C cancellation of the
public IPC client during a pending server request. The actual shell parent
issues CANCEL. The server retains its endpoint, the client endpoint/queues
are retired, the cancelled request produces no successful reply, and a new
client receives the exact expected response. Three complete server restart
cycles then pass fresh-handle, exact-reply, code/stack guard, endpoint-cleanup,
graphical peer and task-canary checks. Kernel and SDK binaries are unchanged.

The disk hash matches the preserved [slice-2 D81 demo](../../artifacts/2026-10-11-ipc-examples/udeks-ipc.d81).
The probe observes a pending request and queues Ctrl-C keyboard input in one
paused monitor session. It restores the live MMU and resumes normal shell
processing. It does not fabricate IPC or task state.

Reproduce with `python3 tools/ipc_demo_probe.py --format d81 --lifecycle-only
--restart-cycles 3` (one command line). `make ipc-lifecycle-probe` runs this
coverage on D81 and D71; only D81 has been qualified in this initial increment.

An early audit found that `program -q` requests graphical CLOSE, rather than
parent-authorized CANCEL. Console-only IPC examples do not consume that event.
Background-server cancellation remains open and must use a real parent CANCEL
path. Other open gates: D71 lifecycle, longer mixed soak, 1986, manual emulator
acceptance and physical C128. This archive does not claim slice 3 complete.
See the [qualification checklist](../../../docs/IPC-QUALIFICATION.md).

Raw captures, the report, log and probe source snapshots are preserved here;
SHA256SUMS binds them. No ROM-bearing snapshots are included.
