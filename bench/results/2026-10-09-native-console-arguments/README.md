# Native console arguments and exit — 2026-10-09

Issue #52, `tasking-native-console`, following pushed execution checkpoint
`f56eb32`. The user accepted that earlier checkpoint (platform unspecified).
This record qualifies increment 1, not completed terminal/job control.

The exact candidate base D64/D81, independent TICKER/QUIET UDEX files, maps,
CPU reports and raw VICE dumps are preserved under this directory. `SHA256SUMS`
covers every evidence file except this narrative. Tests reconstruct the two
fixture disks from the preserved bases and compare hashes with the live reports.
Published `build/udeks.*` remain the merged PR #51 release; they are not these
candidates. The previous no-argument evidence is intentionally unchanged.

Reproduce in the feature worktree:

```sh
distrobox-enter my-distrobox -- make -j8 boot native-console \
  native-console-parser-check placement-check graphics-apps-check service-layout-check
make native-console-probe
distrobox-enter my-distrobox -- make graphical-example
python3 tools/four_native_probe.py --disk build/boot/udeks.d81 \
  --drive 1581 --output build/native-console/four-native
distrobox-enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --disk-service --emulator /var/home/salvogendut/Dev/1986 \
  --roms /var/home/salvogendut/Dev/1986/roms \
  --disk build/boot/udeks.d64 --output build/native-console/1986-service
make check
```

VICE 3.10 Flatpak x128, PAL/default RAM, true-drive 1541/D64 and 1581/D81:

- Foreground `ticker Alpha mixed-case 37` receives exact private arguments,
  outputs through fd 1/2, sleeps five times and returns 37. No VIC/window start.
- `echo $?` reports 37; another reports 0. Nine tokens reject with status 2.
- Eight-argument TICKER (renamed PULSE on D81) runs with `xclock &` and a
  silent `quiet &` peer. Their distinct UARG records survive switches/sleeps.
  The clock's sleep deadline advances, and an injected drag occurs during
  ticks 1–5. Clock remains usable and shuts down normally afterward.
- Exact relocated program bytes, private state, both stack guards, retirement
  and reuse pass. QUIET's later completion/reap leaves foreground status 37
  unchanged. Its expected source return is 67; that exit byte itself was not
  captured before reap, and is not claimed as an independently observed result.

Raw `*.bin` monitor captures include a two-byte load-address prefix. Solo
TICKER uses task 6; with clock+QUIET it uses task 5. `*-arguments.bin` contains
the task's saved initial UARG record; tasks independently check it across sleeps.
Probe commands use keyboard-queue input and test pointer getters, not native
keyboard/mouse transport. Each owned VICE session was terminated.

CPU qualification runs 11,520 production-assembly/C-reference tokenizer cases,
including capacities 0–8, line lengths through 255 and both whitespace forms.
The deliberately wrong tab separator fails. Actual argument-copy and entry
instructions cover argc 0/1/3/8, length 54, adjacent guards, dirty-source suffix
padding, cc65 calling convention and old/malformed ABI rejection. This tests
CPU instructions, not MMU hardware; the live runs establish private mapping.
`make check` passes 1,571 host tests. Coverage checks all 256 exit bytes,
foreground-only harvesting and parser
rejection before either loader. Actual normal/panic placement gates pass.

Separate regressions: VICE four-native-app move/resize, unknown binaries,
capacity/reuse and console cleanup pass. Native 1986 at revision
`d360c114e33216bf38a086f65af27533f581f6ba` passes the existing D64/1571
disk-time service/keyboard/1351 drag/stop/reload/input sequence. That 1986 run
does not exercise the new console arguments. Reports/logs are in `regressions/`.

The new SDK requires UARG 0.1; old SDK/graphical binaries continue to run.
No app/display/stack reservation moved or grew. Native arguments use 81 bytes
of each task's existing private ZP; the 160-byte software stack is unchanged.
Full code/space rationale is in [the plan](../../../docs/NATIVE-CONSOLE-APPS.md).
No native stdin/filesystem calls, no-window Ctrl+C, background terminal policy,
full shell expansion, D71 live run, physical-C128 or periodic-NMI stress
qualification is claimed here. These are not new slots in addition to graphics.
