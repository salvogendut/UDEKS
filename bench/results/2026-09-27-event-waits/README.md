# Task Request ABI 0.4 input waits — 2026-09-27

Qualified using Flatpak VICE 3.10 (`net.sf.VICE`, x128), native cold boot,
PAL defaults, seed 0, warp enabled. Reference build: cc65/ca65/ld65 from
`my-distrobox`, Makefile `-Oirs`, branch `tasking-0.1-event-waits`.
The preserved artifact directory contains the exact compiled probe UDEX,
checksummed scheduler payload and both native probe disks. Linker maps are
preserved beside this report; raw monitor saves retain their two-byte load
address prefix. SHA256SUMS are checked by `make check`.

Both D71 and D64 complete with `UPOL A5 00 A1 00` (failure zero). The compiled
C task checks immediate/malformed/version requests, finite clock wrap,
infinite wake, repeated and chunked reads through newline, empty lines,
stopped wake/continue, original sequence restoration after shared-record
spoofing, and live stack-local array preservation. Two additional monitor-seeded
STOPPED subscriptions become ready without running: the infinite waiter and
the finite waiter whose deadline coincides with submitted input both report
readable. Repeated wake scans preserve STOPPED with resume RUNNABLE. These
seeded entries qualify wake scanning, not three-task execution/allocation.

Additional final-build VICE regressions passed on both disk formats:

- Idle native ush suspension count remains `2 -> 2` without input; xinit,
  xclock &, xwave &, cowsay, ls, cd, pwd and echo complete, ending at 22
  suspensions and restoring INPUT waiting.
- SPAWN/compiled-child/EXIT(37)/blocking-WAITPID/reap completes two reuse cycles.
- SLEEP(600) blocks and resumes after exactly 600 logical ticks.
- CANCEL --input-wait clears every blocked child's private snapshot, publishes
  zombie status 130 and lets WAITPID reap it.
- Shadow probe clears all 8,000 bytes at $A1E0-$C11F, verifies the installed
  3,179-byte tail, preserves the 50-byte $CD8B-$CDBC gap, and compares bank-0
  shadow with bank-1 VIC bitmap (identical).

The live probe exposed a second input reader: the transitional resident shell
could drain native input while its owner was stopped. The private $C90F bridge
now suppresses only that reader after native USH READY, retaining deferred
EXEC and foreground handling. Monitor injection also explicitly selects bank
0 and restores the live MMU profile in one paused session, eliminating an
emulator-test race during VIC/Z80 bank leases.

Current placement: core 1,721 emitted +154 BSS bytes at $C120-$C872,
141-byte gap before the handler; handler 1,163 bytes at $C900-$CD8A, 50-byte
gap before the unchanged $CDBD context binding. No new BSS or resident growth.
Production ush is 2,121 emitted bytes; six-entry bootfs is 11,707 /11,708 bytes.
`make check` passes 626 tests and all preserved hashes; reference-container
placement-check passes. A full `make clean` followed by parallel `make -j8`
reproduces both production hashes below and byte-identical preserved probe disks.

Production image SHA-256 identities used for the shell/graphics regressions:

```text
f32fd445267ff39fa2428db9d7ad8ac6ff4658703a85f86a385ca5bf579e6e91  udeks.d71
78d483bd0a61bbd20244873d3da841bdbd755bb05317cf962f996c00c59f5031  udeks.d64
```

Reproduce after building the probe/lifecycle disks in the reference container:

```sh
python3 tools/task_poll_probe.py
python3 tools/task_poll_probe.py --disk build/boot/udeks-task-poll-probe.d64
python3 tools/task_yield_probe.py
python3 tools/task_yield_probe.py --disk build/boot/udeks.d64
python3 tools/task_cancel_probe.py --input-wait
python3 tools/task_cancel_probe.py --input-wait --disk build/boot/udeks-task-cancel-probe.d64
python3 tools/task_spawn_probe.py
python3 tools/task_spawn_probe.py --disk build/boot/udeks-task-spawn-probe.d64
python3 tools/task_sleep_probe.py
python3 tools/task_sleep_probe.py --disk build/boot/udeks-task-sleep-probe.d64
python3 tools/shadow_boot_probe.py --vic-compare
```

Independent 1986, physical C128, manual typing/history, pointer/dragging and
foreground Ctrl+C checks remain open. No Tasking 0.1 acceptance or discharge
of older hardware gates is implied. Every probe terminates its own VICE process.
