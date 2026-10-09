# Native console execution checkpoint — 2026-10-09

Issue #52 / `tasking-native-console`, based on PR #51 `15eddb4`.
This is a no-argument foreground execution proof, **not** finished console
job control. No resident, shell, loader or ABI change; all normal disk hashes
remain identical to the published PR #51 release and its adjacent
`2026-10-09-default-time/build.json` provenance.

TICKER.BIN SHA-256:
`05b524e3e60fbf4393701ab6d635725b27e7944bf24146a953b6beb60cefaa0a`.
The exact 1,602-byte UDEX, app map and size report are preserved here. It has
1,338 image bytes + 8 BSS and fits all four ordinary native allocations.
Tests run it twice in the smallest slot, not in every allocation. The second
file, PULSE.BIN, is a byte-identical independently named copy.

Reproduce from this worktree revision:

```sh
distrobox-enter my-distrobox -- make -j8 boot native-console \
  placement-check graphics-apps-check service-layout-check
make native-console-probe
make check
```

VICE 3.10 Flatpak `net.sf.VICE`, x128 default PAL/128K with true-drive
emulation: D64/1541 and D81/1581 pass. Each probe uses a fresh copy, seed zero,
warp for boot then warp off for timed task/input observation, and closes its
own process. Source media remain unchanged. No D71 live run, native 1986,
physical-C128, periodic-NMI or performance qualification is claimed.

`make check` passes 1,561 host tests, including eight SDK tests and three
evidence-integrity/behavior tests. Actual-build placement, graphics admission
and service-layout gates pass in `my-distrobox`.

Proven through shell keyboard-queue commands and the ordinary native loader:

- Bare `ticker` prints exact ordered stdout/stderr/tick/completion text,
  sleeps and resumes with private state intact, returns, and releases its slot.
  VIC diagnostic state is unchanged; no window is created.
- `xclock &` followed by foreground `pulse` keeps the clock task scheduling:
  its saved sleep deadline advances while PULSE is live. Test-only pointer
  getters exercise a clock drag during ticks 1–5; this is not a native mouse
  transport test. Clock window and console remain usable afterward.
- Both incarnations retain exact relocated program bytes, private `1234`
  data, no failure flag, and both software-stack guards. No task canary error.
  `echo native console returned` and `xclock -q` complete afterward.

`d64/` and `d81/` retain raw monitor dumps (two-byte LE load address followed
by data) and the report with source/fixture/program hashes. Reconstruct the
fixtures using `add_disk_apps.add_apps` on the published base disks with
TICKER.BIN and PULSE.BIN; tests require exact fixture hashes. Full disposable
disks/logs stay under `build/native-console/vice/`; the test D64 is also at
`build/native-console/try.d64`.

The program entry receives argc=0/argv=NULL. Its return value is 37, but this
proof does not harvest or assert native exit status at the shell. No stdin,
arguments, filesystem SDK, Ctrl+C or prompt-safe background output is supplied.
Those remain explicit next increments in [the plan](../../../docs/NATIVE-CONSOLE-APPS.md).
