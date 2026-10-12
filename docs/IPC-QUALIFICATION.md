# IPC slice 3 — automated qualification complete

Tracking: [issue #58](https://github.com/salvogendut/UDEKS/issues/58), branch
`ipc-0.1-qualification`, current worktree `build/ipc-foundation`, based on
pushed commit `1de24a4`. Slices 1 and 2 are preserved in their dated archives.
Full public demo images remain D71/D81; D64 is skipped by user agreement.

## Automated qualification scope

Extend `tools/ipc_demo_probe.py` with `--lifecycle` (foreground-client cancellation) and `--restart-cycles N`.
Run the public independently loaded programs with xclock/xdraw, then:

1. Cancel the client during the server's deliberate work sleep using shell
   Ctrl-C on a foreground client. The actual shell parent sends CANCEL. Require client allocation retirement, only the server endpoint,
   empty queues, a surviving server and a successful fresh client.
2. Cancel a foreground public server with a separately disk-loaded waiting
   SDK peer. `WAITPING.BIN` starts first, discovers the server, sends its
   request and waits. Ctrl-C then makes the actual shell parent retire the
   server. Require the peer's bounded EAGAIN exit, EBADF on sending to the
   stale server handle, empty endpoints/queues and a fresh successful exchange.
   This uses existing CANCEL ownership; no new shell command is needed.
3. Repeat full create, lookup, exact reply and acknowledged shutdown cycles.
   Require fresh monotonic server handles, intact application code/stack guards,
   no endpoint leaks, two surviving graphical windows and a clear task canary.

```sh
python3 tools/ipc_demo_probe.py --format d81 --lifecycle-only --restart-cycles 3
```

`make ipc-lifecycle-probe` builds the waiting peer and runs both cancellation
cases plus twelve restart cycles on D81 and D71. `--server-cancel` adds
WAITPING only to a disposable disk copy; public demo disks stay unchanged.
The cancellation helper observes the pending request and enqueues ordinary
keyboard events in one paused monitor session, then resumes normal shell
processing. This avoids monitor round trips missing the short work interval.

Both media pass twelve complete restart cycles and cancellation of each peer.
This is bounded lifecycle coverage rather than an indefinite soak. The monitor observes program
state and injects graphical input; peer cancellation uses normal shell control.
No IPC, endpoint or task state is fabricated.

## Results

The focused D81 VICE run passes actual foreground Ctrl-C cancellation during a
pending request, client endpoint/queue cleanup, unchanged server reply count
for the cancelled request, successful recovery and three complete restart
cycles. Each cycle checks fresh handles, exact replies, code/stack guards,
empty endpoint pools and surviving graphical peers. This is a first increment;
D71 and D81 now also pass server cancellation, the orphaned peer
timeout/stale-handle checks, recovery and twelve restarts each. Native 1986 is
qualified by the native pinned-source harness on D81, including exact
and maximum replies, client cancellation/recovery, three restarts, actual
1351 drawing/clock dragging, code/stack guards and final cleanup.
[Preserved evidence](../bench/results/2026-10-11-ipc-qualification/README.md).

## Remaining acceptance

By user agreement, slice 3 covers automated qualification and its preserved
evidence. Manual emulator acceptance and real C128 testing will be performed
in separate runs; they do not block completion of this slice. Neither is
claimed by an automated emulator result.

Automated VICE D71/D81 and native 1986 D81 qualification is complete. The
evidence checks bind reports to actual disks, programs and machine captures.
On 2026-10-12, after the installed 1986 manual-check instructions, the user
reported “all is well” and authorized PR/merge. Manual emulator acceptance is
complete. Physical C128 testing remains pending for a separate run.
[Recorded user acceptance](../bench/results/2026-10-11-ipc-qualification/manual-acceptance.md).

## 1986 on this machine

Installed Flatpak version 0.3.0, commit
`5141979cf20508e71c393813a033ce415deec1b8ffafaa643d2568961b951b51`, is built
from emulator source `d360c114e33216bf38a086f65af27533f581f6ba`. ROM configuration
points to the locally assembled `build/1986-roms` bundle. Earlier GUI/headless
attempts loaded ROMs but did not complete; they establish no IPC pass.

Inspection of that exact version's
[main.c](https://github.com/salvogendut/1986/blob/d360c114e33216bf38a086f65af27533f581f6ba/src/main.c)
confirms `--disk`, `--rom`, `--paste`, `--paste-at`, `--frames`,
`--no-throttle`, and snapshot options. `C128_BOOT_TRACE` and one-shot PPM capture
also exist. Start with bounded boot/progress observations and explicit output
paths accessible through the Flatpak. Frame budgets alone do not prove shell
or IPC completion. Exclude ROM-bearing snapshots from published evidence.

The `tools/ipc_1986_probe.py` harness uses the pinned installed-version source,
an independently built static SDL3 3.2.26 and existing native keyboard/1351
helpers. It executes a real 1581 DOS ROM against a disposable D81. Early boot
and short-budget attempts timed out; a subsequent cold boot passed IPC but
failed a harness clock-drag coordinate check. A retry used the older clock
app's height and also failed that check. The final corrected run resumes the
private initial boot checkpoint and passes all IPC and input checks, using the
disk-loaded clock's actual position and pointer bias. This qualifies the native
engine separately from the installed Flatpak application. All failed attempts
are retained as incomplete evidence, alongside the passing final run.

The source is in `build/ipc-1986-source`; `.udeks-provenance.json` binds the
revision, tarball and every original source file. The probe rejects changed
core sources. Static SDL is installed at `build/ipc-sdl3`. Its build disables
X11, Wayland, ALSA, PulseAudio, JACK, PipeWire and KMSDRM, enables
`SDL_UNIX_CONSOLE_BUILD`, and uses `SDL_SHARED=OFF`, `SDL_STATIC=ON`. No
emulator core patch or IEC trap is used. Published provenance binds the compiler,
SDL library, runner, ROM hashes, disk and harness sources. ROMs and snapshots
remain private. Native probing defaults to a 1,200-second budget; `--resume`
accepts a local initial cold-boot checkpoint and records its use explicitly.

## Boundary and policy coverage

The expanded disk-loaded raw fixture passes on VICE D71 and D81: duplicate
name, overlong name, unknown operation, endpoint pool exhaustion, invalid
receive capacity, foreign receive/close, sixteen exact copied bytes, full and
empty queues, undersized receive preservation, stale handles, sender EXIT
purging a peer queue, normal EXIT, foreground CANCEL and slot reuse. Clock and
drawing coexistence and operation after graphics shutdown also pass. Existing
CPU tests supply handle exhaustion, randomized policy comparison and negative
controls for missing retirement hooks. The kernel and SDK remain unchanged.

```sh
make ipc-boundary-probe
make ipc-lifecycle-probe
make ipc-native-1986-probe
make check
```

## Separate manual and hardware runs

Use the preserved public D71/D81 demo images. Start `xclock &`, `xdraw &` and
`ipcsrv &`; run `ipcping hello` and `ipcping 1234567890abcde`. Interrupt a
foreground client with Ctrl-C, confirm a fresh client can exchange a reply,
then run `ipcping --stop`. Repeat server startup, reply and shutdown while
moving the clock and drawing. Record the actual emulator or C128 configuration
and observed results in the separate acceptance run. D64 is excluded because
the public programs do not fit the full demo disk.
