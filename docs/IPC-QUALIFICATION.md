# IPC slice 3 — qualification in progress

Tracking: [issue #58](https://github.com/salvogendut/UDEKS/issues/58), branch
`ipc-0.1-qualification`, current worktree `build/ipc-foundation`, based on
pushed commit `1de24a4`. Slices 1 and 2 are preserved in their dated archives.
Full public demo images remain D71/D81; D64 is skipped by user agreement.

## First qualification increment

Extend `tools/ipc_demo_probe.py` with `--lifecycle` (foreground-client cancellation) and `--restart-cycles N`.
Run the public independently loaded programs with xclock/xdraw, then:

1. Cancel the client during the server's deliberate work sleep using shell
   Ctrl-C on a foreground client. The actual shell parent sends CANCEL. Require client allocation retirement, only the server endpoint,
   empty queues, a surviving server and a successful fresh client.
2. Background-server cancellation remains open: `program -q` requests a
   graphical CLOSE event, which console-only IPC examples never consume. The
   first probe exposed this distinction. Add a real parent-authorized CANCEL
   path and require server retirement, empty queues, a bounded EAGAIN client
   exit and a successful fresh server/client exchange.
3. Repeat full create, lookup, exact reply and acknowledged shutdown cycles.
   Require fresh monotonic server handles, intact application code/stack guards,
   no endpoint leaks, two surviving graphical windows and a clear task canary.

```sh
python3 tools/ipc_demo_probe.py --format d81 --lifecycle-only --restart-cycles 3
```

`make ipc-lifecycle-probe` runs this initial coverage on both formats.
The cancellation helper observes the pending request and enqueues ordinary
keyboard events in one paused monitor session, then resumes normal shell
processing. This avoids monitor round trips missing the short work interval.

This initial run is a lifecycle check, not a long soak. Broaden it to both media
and longer cycles after its assertions pass. The monitor observes program
state and injects graphical input; peer cancellation uses normal shell control.
No IPC, endpoint or task state is fabricated.

## First result

The focused D81 VICE run passes actual foreground Ctrl-C cancellation during a
pending request, client endpoint/queue cleanup, unchanged server reply count
for the cancelled request, successful recovery and three complete restart
cycles. Each cycle checks fresh handles, exact replies, code/stack guards,
empty endpoint pools and surviving graphical peers. This is a first increment;
D71 lifecycle, longer soak, background-server cancellation and 1986 remain open.
[Preserved evidence](../bench/results/2026-10-11-ipc-qualification/README.md).

## Remaining acceptance

- Preserve slice-3 source snapshots, exact demo hashes, raw captures and reports.
- Audit the raw-gate/CPU coverage for queue bounds, malformed requests, foreign
  receive/close, duplicate names and stale handles; add missing real lifecycle
  cases rather than duplicate already established policy tests.
- Complete longer mixed graphical/console restart and cancellation runs and
  the relevant existing input/console/placement regression gates.
- Qualify 1986, then obtain manual emulator acceptance. Physical C128 remains
  unqualified until actual hardware testing.

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

The repository's existing native harness links emulator sources and requires
SDL3 through pkg-config. Sibling source is absent here. If the Flatpak cannot
provide sufficiently observable runs, build a pinned harness inside the
workspace with the appropriate SDL3 toolchain and record that separate engine
provenance. Keep installed Flatpak behavior distinct from a native harness pass.
