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
2. **Terminal ownership/jobs — implemented and user-accepted:**
   task-based Ctrl+C, foreground stdin, EIO rejection of background reads,
   argument-bearing `&` and prompt-safe background output. Cancellation releases
   resources and restores the prompt without requiring a window or disturbing peers.
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
kernel-map imports. TICKER.BIN is 2,077 file bytes, 1,739 image + 91 BSS.
QUIET.BIN, a silent qualification peer, is 1,465 file bytes, 1,241 image + 85
BSS. Both fit all four ordinary allocations, shared with graphical tasks.

The user accepted no-argument checkpoint `f56eb32` (platform unspecified).
Its [evidence](../bench/results/2026-10-09-native-console/README.md) remains
unchanged. Current [argument evidence](../bench/results/2026-10-09-native-console-arguments/README.md)
is separate. Published download snapshots still represent PR #51.

## Ctrl+C checkpoint: parent-owned cancellation

The user also accepted the argument/exit slice `bca650a` (platform unspecified).
The next slice replaces Ctrl+C's graphical close notification with a real
task cancellation, without modifying the scheduler, loader or common switch.
The terminal queues a private notice identifying the foreground task; ush,
running as its actual parent, submits existing UTRQ CANCEL with status 130.
Normal retirement clears the blocked request, destroys any owned window, reaps
the allocation and only then releases foreground ownership and the prompt.
No program cooperation with a graphical EVENT is required.

The same route handles graphical foreground tasks. Background peers are not
selected, and Ctrl+C with no foreground job cancels nothing. A natural exit
that wins the race retains its actual exit status; an ESRCH cancellation reply
is silent. Other cancellation errors are reported without pretending the task
stopped. Repeated keys cannot retarget a reused slot: ush consumes the notice
while waiting for the old foreground completion, before another launch.

This remains cooperative, **not preemption**: a program that never sleeps,
yields or otherwise returns to the scheduler can still prevent input polling.
Foreground stdin and background output are implemented below.
Bare `name -q` and `xinit -q` still use their existing graphical close policy;
this slice changes foreground Ctrl+C only. System disk/recovery ush are rebuilt
together with the private notice producer; do not mix in an older shell binary.

`make native-console-cancel-fixtures` builds NAP and TICKER; host
`make native-console-cancel-probe` tests all four foreground slots, peer
survival, status 130, private-wait cleanup, one retirement per task, slot reuse,
old-deadline non-resumption, graphical cancellation and idle-prompt behavior on
VICE D64/D81. Native 1986 separately passes four-app keyboard/mouse/Ctrl+C
regression. [Preserved evidence and limits](../bench/results/2026-10-09-native-console-cancel/README.md)
do not imply physical-hardware qualification or a native 1986 NAP run.

## Try the checkpoint

The user accepted Ctrl+C checkpoint `98ff762` (platform unspecified); its push
was confirmed before this foreground-input slice. The new SDK implements
`udeks_read(0, buffer, count)` as owned POLL + nonblocking READ, copying up to
24 bytes into private task memory after resumption. `udeks_poll(0, timeout)`
supports 0–600 ticks or `UDEKS_TREQ_POLL_FOREVER`. An empty line returns newline,
not EOF; zero-length SDK reads are immediate no-ops. No Ctrl+D/raw input yet.

The trusted current-task query and foreground allocation determine ownership.
Background READ/POLL returns EIO (5), including raw READ requests, without
consumption, editor activation or wait registration. The editor is armed on
the first permitted read/poll; an existing submitted line remains available
across short reads. Shell history cannot be recalled or modified by application
input. On return/cancellation, PROMPT discards partial/unread input but retains
command history. Counted background output now preserves the editor row.

The independent `ASK.BIN` example is 1,867 file bytes (1,579 image + 4 BSS),
fits all four allocations and echoes one edited line. Its input runtime is
pulled from an SDK archive only for programs that read/poll, so TICKER/QUIET
do not pay for unused input code. No kernel application-name table changes.

Build an ASK/TICKER test disk from this worktree:

```sh
distrobox-enter my-distrobox -- make -j8 boot native-console-input-fixtures
python3 tools/add_disk_apps.py --disk build/boot/udeks.d64 \
  --output build/native-console/jobs.d64 \
  build/native-console/ask/ASK.BIN build/native-console/ticker/TICKER.BIN
```

Cold-boot it in 1986 or on C128/Pi1541, then:

```text
xclock &
ask
```

Type a mixed-case line, correct it with Backspace, and press Enter. ASK echoes
it and returns; `echo $?` should print 0. Run `ask` again, type a partial line
and press Ctrl+C: expect the shell prompt and status 130, with no leftover
input executed. The clock should remain usable throughout. Try an empty line
and a long line; Up in ASK must not reveal old shell commands.

Qualification uses `make native-console-input-check` in the container (real
6502 owner/reader guards and a deliberate bypass negative control) and host
`make native-console-input-probe` (disposable D64/D81, all slots, background
denial, partial-input cancellation/reuse, no implicit VIC startup). The latter
uses keyboard-queue injection and warp for functional checks, not timing or
native keyboard transport qualification. The independent native 1986 four-app
regression covers keyboard/1351 input, not ASK itself.
[Exact input evidence and limits](../bench/results/2026-10-09-native-console-input/README.md).

### Earlier output/argument checks

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
`ticker a b c d e f g h` has nine tokens: expect `Invalid command`, then
`echo $?` prints 2. A second consecutive status query prints 0.
Now run `ticker stop-me` and press Ctrl+C while it ticks: expect `Interrupted`,
the prompt and `echo $?` equal to 130. A background clock must survive and still
be draggable. Launch TICKER again to check slot reuse. The separate test-only
`NAP.BIN` sleeps indefinitely without a window and is used to prove cancellation
cannot be mistaken for natural return.

Quoting/escaping and native file calls remain unimplemented.
The demo finishes by itself; QUIET is a silent test, not a background utility.

`make native-console-probe` runs disposable D64/D81 in Flatpak VICE: ordinary
and eight-argument runs, unknown-name PULSE on D81, distinct concurrent arguments,
status, reuse, code/guards, no implicit VIC startup, clock progress and drag.
It injects keyboard queues/pointer getters, not native mouse transport.
Separate four-app VICE and native 1986 service/keyboard/1351 regressions pass;
the 1986 run does not test native arguments. No new physical-C128 or periodic-NMI
stress qualification is inferred.

## Background jobs checkpoint

The accepted input slice was committed/pushed as `9c9bfad`. This slice completes
increment 2's bounded launch/output behavior, not general Unix job control.
The user accepted the delivered candidate and requested commit/push; the test
platform was unspecified, so this does not add physical-C128 qualification.
Try the new `build/native-console/jobs.d64` or `.d81` in this worktree:

```text
xclock &
ticker Alpha mixed-case &
```

While it ticks, type `echo draft` **without Enter**, move the cursor left, and
wait for more ticks. The line/cursor should stay intact; finish editing and
press Enter. `ticker a B c D e F last &` exercises all eight arguments without
passing the operator to the program. Background completion must not replace
the shell's last status. Then run `ticker hello &`, followed by `ask`; type a
partial line while ticker continues, and try Enter and Ctrl+C on separate runs.
Clock dragging and the VDC input should still work. TICKER stops itself.

Each counted WRITE is serialized, but separate writes from different programs
may interleave. The editor row is pinned below the output area; it moves down
once if initially at row zero. Output scrolls/clears above that row and retains
its cursor across chunks, without inserting per-request newlines. This uses
the existing console cells, not another text buffer. Synchronous legacy
utilities do not gain background execution, and bg stdin still fails EIO.

`make native-console-jobs-probe` cold-boots disposable VICE D64/D81 media:
eight-argument launch, mid-line cursor/draft preservation, Enter/history,
foreground input beside output, targeted cancellation/reuse, status isolation,
invalid launches and code/stack guards. D81 adds a silent BGREAD denial peer;
the D64 test adds only ASK/TICKER to fit without deleting existing apps.
The exact records and limits are in the
[background-job evidence](../bench/results/2026-10-09-native-console-jobs/README.md).
Next is increment 3's native filesystem ownership and utility migration.

## Placement and validation

No allocation, stack or display reservation grows. The 237-byte C tokenizer is
replaced by a 77-byte assembly implementation, retaining C as the test reference.
The existing 65-byte basename adapter moves into existing MODULECODE. This
bounded placement change makes room for the feature; it is not an optimization
project. UARG consumes unused private ZP, not software stack.

Actual normal/panic link gates establish:

| Area | Used end / capacity | Remaining |
| --- | --- | --- |
| Resident BSS before TIME slot `$93D0` (stdin slice) | `$93CE` | 1 byte |
| Native loader CODE | `$DFF4` / `$E000` | 11 bytes |
| Relocator | `$19ED` / `$1A00` | 18 bytes |
| Access bridge | `$1FFE` / `$2000` | 1 byte |
| Bank-0 module | 818 / 836 bytes | 18 bytes |

Foreground input adds one editor-mode byte. It fits by sharing the existing
line-copy helper and using a guarded assembly whole-line reader alongside the
chunk reader; C remains the host reference. The contiguous ten wait arrays
use a link-asserted reset loop, recovering scheduler space without changing
snapshot fields. Scheduler code/RODATA/BSS ends `$C862`, 29 bytes below the
storage router. Its private caller query at `$C8FC` fills that existing router
reservation; it is not a public syscall. The common request gate uses 264/265
bytes. No app, software/hardware stack, display or service reservation moves.

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
