# Independently scheduled console applications

Active: [issue #52](https://github.com/salvogendut/UDEKS/issues/52), branch
`tasking-native-console`, worktree `build/native-console`, 2026-10-09.
This advances the saved proposal after PR #51 (`15eddb4`).
The [roadmap](ROADMAP.md) remains the priority list.

## Goal and three increments

A foreground console program should make the shell wait, not the whole OS.
Use the existing allocator and cooperative scheduler, without application
name tables. Preserve synchronous utility loading and recovery during migration.

1. **Native execution — implemented:** independent C runtime, private arguments,
   stdout/stderr, exit status, no implicit window or VIC startup. Arguments
   survive sleeps while clock updates/input continue, then ush gets the result.
2. **Terminal ownership/jobs — next:** foreground stdin, task-based Ctrl+C,
   argument-bearing `&`, prompt-safe output and rejection/suspension of
   background reads. Cancellation must release resources and restore the
   prompt without requiring a window or disturbing peers.
3. **Migration/qualification:** convert a useful small utility group, handle
   shared filesystem ownership, prove failure cleanup/reuse and mixed app
   operation in VICE, 1986 and a user hardware checklist.

Preemption, pipes, redirection and scripting are separate work. Disk writes
remain available in the synchronous SDK; the native runtime has no filesystem
calls yet. Cooperative code must sleep/yield; tight loops can still starve peers.

## Current checkpoint: arguments and completion

The SDK copies counted fd 1/2 output through UTRQ WRITE at `$FF16`, not through
bank-0 pointer veneers. Each task has private cc65 runtime, BSS, C stack and
request sequence. `udeks_write`, `udeks_write_byte`, `udeks_write_bytes` and
`udeks_sleep` (1–600 ticks) check ownership, bounds, errors and short writes.

[UARG 0.1](../abi/executable.md#native-argument-record-uarg-01-2026-10-09)
occupies 81 bytes of existing task-private ZP, logical `$80-$D0`. It holds up
to eight arguments within the 54-character command line, initialized before
RUNNABLE. No pointer refers to the shared parser. The new SDK returns 126 on
missing/unsupported UARG. Existing graphical entries still work: UDEX 0.2 and
initial CPU registers are unchanged.

Normal native foreground exit is harvested before reap; ush snapshots it on
completion. Exact `echo $?` prints that byte; echo itself then succeeds (0).
Background exit does not overwrite it. This is not general variable expansion.

`tools/build_native_console.py` independently links UDEX 0.2 without private
kernel-map imports. TICKER.BIN is 2,076 file bytes, 1,738 image + 91 BSS.
QUIET.BIN, a silent qualification peer, is 1,464 file bytes, 1,240 image + 85
BSS. Both fit all four ordinary allocations, shared with graphical tasks.

The user accepted no-argument checkpoint `f56eb32` (platform unspecified).
Its [evidence](../bench/results/2026-10-09-native-console/README.md) remains
unchanged. Current [argument evidence](../bench/results/2026-10-09-native-console-arguments/README.md)
is separate. Published download snapshots still represent PR #51.

## Try the checkpoint

From the feature worktree, build and add TICKER to a **new disposable** disk:

```sh
distrobox-enter my-distrobox -- make -j8 boot native-console
python3 tools/add_disk_apps.py --disk build/boot/udeks.d64 \
  --output build/native-console/try.d64 build/native-console/ticker/TICKER.BIN
```

Cold-boot `build/native-console/try.d64` in 1986 or on C128/Pi1541:

```text
ticker Alpha mixed-case 37
echo $?
xclock &
ticker hello
echo $?
xclock -q
```

TICKER prints its arguments, ticks 1–5 and completion over about ten seconds,
with no window of its own. Both status queries should print 37. During the
second run, drag the clock while the shell waits.
`ticker a b c d e f g h` has nine tokens: expect `Too many arguments`, then
`echo $?` prints 2. A second consecutive status query prints 0.
Quoting/escaping, stdin, Ctrl+C for no-window tasks, argument-bearing background
launch, background terminal arbitration and native file calls remain unimplemented.
The demo finishes by itself; QUIET is a silent test, not a background utility.

`make native-console-probe` runs disposable D64/D81 in Flatpak VICE: ordinary
and eight-argument runs, unknown-name PULSE on D81, distinct concurrent arguments,
status, reuse, code/guards, no implicit VIC startup, clock progress and drag.
It injects keyboard queues/pointer getters, not native mouse transport.
Separate four-app VICE and native 1986 service/keyboard/1351 regressions pass;
the 1986 run does not test native arguments. No new physical-C128 or periodic-NMI
stress qualification is inferred.

## Placement and validation

No allocation, stack or display reservation grows. The 237-byte C tokenizer is
replaced by a 77-byte assembly implementation, retaining C as the test reference.
The existing 65-byte basename adapter moves into existing MODULECODE. This
bounded placement change makes room for the feature; it is not an optimization
project. UARG consumes unused private ZP, not software stack.

Actual normal/panic link gates establish:

| Area | Used end / capacity | Remaining |
| --- | --- | --- |
| Resident BSS before TIME slot `$93D0` | `$93CB` | 4 bytes |
| Native loader CODE | `$DFF4` / `$E000` | 11 bytes |
| Relocator | `$19ED` / `$1A00` | 18 bytes |
| Access bridge | `$1FFE` / `$2000` | 1 byte |
| Bank-0 module | 775 / 836 bytes | 61 bytes |

Container `make native-console-parser-check` runs 11,520 real-6502 comparisons
against C, an incorrect-separator negative control, and actual argument-copy/
entry instructions. It tests counts 0/1/3/8, full 54-character input, adjacent
guards, zero padding despite dirty source suffixes, calling convention and
fail-closed ABI handling. It is not an MMU model; VICE proves private mapping.
Host tests cover all 256 exit bytes and foreground/background exit selection.
Keep the guards and 160-byte usable C stack.

WRITE is synchronous; SLEEP restores an owned response. Raw YIELD does not
currently restore a private reply, so this SDK does not expose it. Never examine
another task's response after yielding. This feature adds no task capacity.

## References

- [Synchronous SDK](GRAPHICAL-APPS-SDK.md#independent-console-commands)
- [Executable ABI](../abi/executable.md), [task requests](../abi/task-request.md)
- [Allocation contract](../tools/native_app_layout.py)
