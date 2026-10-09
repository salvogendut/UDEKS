# Independently scheduled console applications

Active: [issue #52](https://github.com/salvogendut/UDEKS/issues/52), branch
`tasking-native-console`, worktree `build/native-console`, 2026-10-09.
This advances the saved 2026-10-05 proposal after the disk-time service merged
in PR #51 (`15eddb4`). The [roadmap](ROADMAP.md) remains the priority list.

## Goal and three increments

A foreground console program should make the shell wait, not the whole OS.
Use the existing native allocator and cooperative scheduler, keep applications
independent of kernel name tables, and preserve the synchronous utility loader
and recovery paths during migration. This is not a new scheduler.

1. **Native execution:** independent C runtime, bounded private arguments,
   stdout/stderr, exit-status delivery, no implicit window or VIC startup.
   Accept when a console program's arguments/state survive sleeps while clock
   updates and window input continue, then the shell gets its exit status.
2. **Terminal ownership and jobs:** foreground stdin, task-based Ctrl+C,
   argument-bearing `&`, prompt-safe output, explicit rejection/suspension of
   background reads. Accept when cancellation restores the prompt, preserves
   other tasks, and releases owned resources. A window must not be required.
3. **Migration and qualification:** convert a small useful utility group,
   handle shared filesystem ownership, prove failure cleanup/reuse and mixed
   console/graphics operation in VICE, 1986 and a user hardware checklist.

General allocation, preemption, pipes, redirection and shell scripting are
separate work. Existing disk writes remain available through the synchronous
SDK; the first native-console runtime does not yet expose filesystem calls.
Cooperative code must sleep/yield; arbitrary tight loops can still starve peers.

## First execution checkpoint

Implemented, **not completion of increment 1**:

- `user/lib/native_console.c` copies counted output through UTRQ WRITE at the
  existing `$FF16` gate. It never passes bank-1 pointers to bank-0 veneers.
  Each task has its own cc65 runtime, software stack, BSS and request sequence.
- `udeks_write`, `udeks_write_byte`, `udeks_write_bytes` support fd 1/2 and
  `udeks_sleep` supports 1–600 ticks. Requests check reply ownership, bounds,
  errors and short writes. Sleep resumes with its task-owned reply.
- `user/examples/ticker.c` prints five ticks at two-second intervals. It
  opens no window, checks private state across sleeps, then returns through
  the existing EXIT path. `PULSE.BIN` is the same file under an unknown name.
- `tools/build_native_console.py` independently links UDEX 0.2, with no private
  kernel-map imports. TICKER is 1,602 file bytes, 1,338 image + 8 BSS bytes,
  fitting all four ordinary native allocations. No OS bytes or ABI change.

The entry deliberately supplies **argc=0 / argv=NULL**. Bare foreground
commands work; ordinary arguments do not. TICKER returns 37, but the shell's
native exit-status reporting is still missing. Do not use this checkpoint as
proof of stdin, Ctrl+C, `&` terminal arbitration or filesystem support.
The existing graphical native-stop path is window-close based; it is not a
general console cancellation mechanism. The demo finishes on its own.

WRITE is synchronous; SLEEP restores an owned response on resume. Raw YIELD
does not currently restore a private response, so the checked SDK does not
expose it. Never examine a different task's shared response after yielding.

## Try the checkpoint

From the feature worktree, build in the reference container, then install into
a **new disposable** disk copy (normal boot media remain unchanged):

```sh
distrobox-enter my-distrobox -- make -j8 boot native-console
python3 tools/add_disk_apps.py --disk build/boot/udeks.d64 \
  --output build/native-console/try.d64 build/native-console/ticker/TICKER.BIN
```

Cold-boot `build/native-console/try.d64` in 1986 or on C128/Pi1541. At the shell:

```text
ticker
xclock &
ticker
```

The first run must print its startup/stderr messages, ticks 1–5 and completion
without opening the graphical display. During the second run, drag the clock;
its input should work while the shell waits. The prompt returns after about
ten seconds of ticking. Try `echo returned` and `xclock -q` afterward.
Use bare `ticker`, not arguments or `ticker &`, for this checkpoint.

On the host, `make native-console-probe` repeats this against disposable D64
and D81 in Flatpak VICE, also launching the renamed PULSE, checking exact output,
native code/BSS/stack guards, slot retirement/reuse, clock scheduling and drag
during console execution. The pointer part injects test getters, not a native
1351 event; no new 1986/physical-hardware qualification is inferred.

## Next implementation: argument and completion contract

Copy bounded arguments into **charged task-private storage before RUNNABLE**;
never retain pointers to the shell's bank-0 parser. Account for strings,
terminators, argc and relocated argv pointers. Reject overflow atomically,
retain no-argument graphical compatibility, and test two tasks with distinct
arguments across sleeps. The shell currently has an eight-argument, bounded
line parser; the new task-entry limit/layout is not frozen by this document.
Harvest native exit status before the graphical bookkeeping reaps the slot.

Placement must be decided before inserting that code. Actual PR #51 maps:

| Area | Used / reservation | Remaining |
| --- | --- | --- |
| Resident through `$93CD`, time slot at `$93D0` | fixed | 2 bytes |
| Native loader CODE `$D900–$DFE6` | 1,767 / 1,792 bytes | 25 bytes |
| Relocator `$1880–$19ED` | 366 / 384 bytes | 18 bytes |
| Access bridge `$1F00–$1FFB` | 252 / 256 bytes | 4 bytes |

These small gaps are **not** evidence that argument delivery fits. Select a
measured service/loader placement before growing it; do not quietly steal
common RAM, display memory or stack reservations. Each native C-stack page
contains two guards, a 160-byte usable stack and an EXIT trampoline, not free
argument space. If an image/BSS trailer is chosen, charge it in both packer
capacity checks and loader validation. Existing ordinary and joined allocations
must continue rejecting overlaps and oversize images safely.

Console and graphical tasks share the same four compatible-size allocations;
this does not add extra console slots beside four graphical apps. Tasking and
terminal policy belong in services/SDK/shell, not the minimal context switch.

## References

- [Existing synchronous console SDK](GRAPHICAL-APPS-SDK.md#independent-console-commands)
- [Executable ABI](../abi/executable.md), [task requests](../abi/task-request.md)
- [Native allocation contract](../tools/native_app_layout.py)
- [Shell](../src/services/shell/shell.c), [loader](../src/services/app/banked_loader.s)
- [Preserved execution evidence](../bench/results/2026-10-09-native-console/README.md)
