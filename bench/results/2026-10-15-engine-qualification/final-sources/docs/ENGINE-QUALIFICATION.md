# Engine IPC qualification — issue #60

Production service and SDK: [ENGINE-IPC.md](ENGINE-IPC.md).
Contract: [engine-ipc.md](../abi/engine-ipc.md).
Base commit for this qualification is `9d109fa` on `services-engine-ipc`.
The qualification adds test harnesses and fixtures; production ENGINE/ENGTEST,
kernel, public IPC examples and default xwave are unchanged.
Automated slice-3 qualification is complete on VICE D71/D81 and native 1986
D81. Manual emulator and physical C128 acceptance remain separate open runs;
supplemental native D71 loading remains unqualified as described below.

## Automated evidence

VICE cold-boots both D71/1571 and D81/1581 demo copies through ordinary
shell, disk loader and native SDK paths. Each format passes:

- Missing/stopped service returns ENOENT (2), with usable shell and graphics.
- 96 exact wave requests: phases 0/250/255, steps 0/1/7/255 and counts 1–8.
  Samples use a frozen legacy waveform; the final phase wraps modulo 256.
- NOP and seven invalid requests: zero/nine samples, surface/unknown opcode,
  malformed STOP, short envelope and invalid message kind. All return exact
  errors; invalid requests do not execute a worker job or stop the server.
- Real parent CANCEL of the public foreground ENGTEST during an orphaned
  shutdown ACK wait; exit 130, reply endpoint/queued-message retirement,
  bounded server recovery and a fresh successful public wave request.
- Real parent CANCEL of the public foreground ENGINE while awaiting STOP ACK;
  exit 130, stale-handle SEND returns EBADF (9), and the waiting test peer closes.
- Twelve complete start/NOP/WAVE/acknowledged-stop cycles, strictly increasing
  server handles, empty endpoints/queues after each stop, code/stack guards,
  task canary and clock/draw window survival.

The final cancellation harness additionally records server state 2, the peer's
pending state and both real endpoint owners before it queues ordinary Ctrl-C
key events in one paused monitor session. No task, request, endpoint or reply
state is fabricated. The worker itself is synchronous and bounded; these
checks exercise blocked IPC/ACK waits, not preemption during Z80 ownership.

Native sibling 1986 D81 passes both public peers' real keyboard Ctrl-C
cancellation, ACK-timeout recovery, stale-handle rejection, three restart cycles,
exact samples/NOP, missing/stopped service, real 1351 drawing and clock dragging,
code/stack guards and cleanup. It resumes the verified private initial-boot
checkpoint from slice 2; this is not another complete cold-boot pass.
Earlier lifecycle/restart runs that timed out are retained as incomplete
evidence, never full passes.
The core remains unmodified at `65c1fe660ce2b04b785937550d521614544f808d`.

Supplemental native 1986 D71/real-1571 testing is **unqualified**: startup
reports an I/O error loading the existing `TIME.SVC`; ENGTEST then reports
loader error 13 with client state still zero. This occurs before the engine
client executes. The same D71 candidate passes VICE. Preserve the failure for
separate native drive/storage investigation; do not attribute it to the engine
protocol or change emulator behavior to manufacture a pass.

Host tests separately exercise full/empty queues, bounded backpressure,
accepted requests never being replayed, malformed/authenticated replies,
unchanged caller outputs on errors, ACK source/sequence/reserved fields and
timeout recovery even under junk traffic. The machine bounds fixture is
also compiled against the actual worker C and protocol policy on the host:
104 replies, 97 worker jobs and one successful endpoint close.
The complete host suite passes 1,773 tests; boot, IPC layout, kernel placement
and graphical-app gates pass. Kernel/hidden/panic and production engine program
hashes match the slice-2 baseline.

Evidence: [preserved qualification results](../bench/results/2026-10-15-engine-qualification/README.md).
ROMs, emulator executables and ROM-bearing snapshots are not published.

## Reproducing the automated checks

Use native cc65/SDCC and `gh` on this ChromeOS Linux container. Build in this
branch's worktree; never clean the root `build/` directory containing worktrees.

```sh
make engine-demo
make engine-vice-probe
make engine-native-lifecycle-probe
make check
```

VICE is the `net.sf.VICE` Flatpak with a local monitor socket. Native 1986 uses
the sibling source checkout, its local SDL3 pkg-config and the private ROM
bundle under the common checkout's `build/1986-roms` directory. The lifecycle
target cold-boots D81. For repeated development runs, the Python wrapper accepts
`--resume PATH` for a verified private initial-boot checkpoint; provenance
records that reuse. This does not count as another complete cold-boot pass.
`--format d71` selects the supplemental real-1571 path described above.

`ENGPEER.BIN` and `ENGBOUND.BIN` are test-only programs, added only to disposable
qualification media. The shipped demo still adds just ENGINE and ENGTEST.
ENGPEER is 3,325 file bytes / 2,719 installed bytes / 26 BSS; ENGBOUND is
3,938 / 3,216 / 31. Both fit ordinary slots 3 and 5. The peer either consumes
a STOP reply and retires without ACK, or waits for server cancellation before
checking its stale handle. It never patches production state or sends an ACK.

## Migration decision

Keep the existing xwave direct worker path as the default. The IPC candidate
supports NOP and at most eight wave samples per reply. Existing xwave uses
25-sample surface rows and a private 525-byte surface cache; the worker gate
can return 25/50-byte batches, so xwave cannot switch
to this protocol unchanged. A later, separately versioned protocol must define
surface chunks, row/job identity, authentication, bounded waits and cancellation
before a client can assemble a complete row privately and publish it atomically.

Capacity is explicit: ENGINE consumes one of four ordinary task allocations
and one of two endpoints. One serialized active client consumes the other
endpoint. The present demonstration uses all four task slots for server,
client, clock and draw; it does not support four graphical apps plus a server.
ENGTEST has 72 bytes of file staging headroom in slot 3; ENGINE has 158 in slot 5.
Any surface client and expanded server must be measured again, including their
private assembly/cache storage, stacks and launch orders.

A future migration should be opt-in first, compare its samples and frame output
with the frozen direct path, and preserve the existing direct implementation
as rollback. Do not silently replay an accepted IPC job through the direct gate
after a timeout: the remote job may already have completed. Missing-service
fallback may be chosen before submitting a request. No default app behavior
changes in this qualification.

## Separate manual emulator acceptance

This is an open acceptance run, independent of automated qualification. Boot
the public D71/D81 demo, verify startup and existing time service, then run:

```text
engtest
echo $?
xclock &
xdraw &
engine &
engtest --nop
engtest
engtest --stop
engine &
engtest
engtest --stop
engtest
echo $?
```

Both missing-service checks must report 2; successful calls print `engtest: OK`.
Move the clock and draw while the engine is available, then repeat a successful
wave request. Shutdown must leave the console and both graphical apps usable.
Close them with `xdraw -q` and `xclock -q`. Console server shutdown is
`engtest --stop`; `engine -q` is not a parent-cancellation test.

For optional interactive cancellation, use the archived qualification media
containing ENGPEER. Run `engpeer &`, immediately run foreground `engine`, then
press Ctrl-C during its roughly 600-tick ACK wait. Confirm exit 130, missing
service, and a successful fresh background server/client exchange. For client
cancellation, run `engine &`, `engpeer abandon`, then foreground `engtest` and
Ctrl-C before the orphaned ACK wait expires. After recovery, a fresh request
must succeed. If the timing window expires, repeat; do not claim cancellation
from an ordinary completed request.

Record emulator/version, media hashes, visible results, input behavior and
whether either program required recovery or reboot.

## Separate physical C128 acceptance

Still open; automated emulator evidence does not satisfy it. Record machine
model, PAL/NTSC, memory configuration, drive/media interface, disk hashes and
test date. On real 1571/D71 and 1581/D81 paths where available:

- Cold boot, verify normal startup/time service, then perform the manual
  sequence above and twelve stop/restart cycles without rebooting.
- Exercise real keyboard Ctrl-C through the parent shell and actual 1351
  drawing/clock movement; verify another exact public ENGTEST request afterward.
- Check missing service after shutdown, fresh restart, usable shell/windows
  and normal graphics close. Record unexpected error codes or task exhaustion.
- Repeat after a cold power cycle. Keep IPC physical qualification from #58
  separately open until its checklist has also been executed.

Preserve failures and timings. Additional drive/storage failures belong in
their own diagnosis; do not mark an engine pass when its executable never ran.
