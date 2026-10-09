# Independently scheduled console applications

Completed and merge-authorized: [issue #52](https://github.com/salvogendut/UDEKS/issues/52),
[PR #53](https://github.com/salvogendut/UDEKS/pull/53), branch
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
3. **Migration/qualification — implemented, merge approved:** convert `cat`, handle
   shared filesystem ownership, prove failure cleanup/reuse and mixed app
   operation in VICE and 1986. A user hardware checklist is supplied; merge
   approval does not constitute a new physical-C128 test report.

Preemption, pipes, redirection and scripting are separate work. Native and
synchronous SDKs support file I/O. Cooperative code must sleep/yield;
tight loops can still starve peers.

## Current checkpoint: native files and CAT

`user/lib/native_files.c` adds optional OPEN/CLOSE to the independent native
runtime. READ/WRITE now also accept mounted-file descriptor 4: paths contain
1–23 bytes, transfers at most 24 bytes, and READ returns zero at EOF. Modes
are `UDEKS_O_RDONLY` and create-only SEQ `UDEKS_O_CREATE_EXCL`; no overwrite,
append, directory enumeration or file POLL in this SDK slice. Counted writes
preserve binary bytes. Check CLOSE after any short/error WRITE; do not retry.
Only stdin performs the blocking POLL before READ.

The existing service already owns streams by trusted task ID **and generation**.
Foreign READ/WRITE/CLOSE returns EBADF. Validated EXIT/CANCEL invokes cleanup
before changing the generation or reusing the allocation. The SDK does not
claim ownership or hold the MMU/IEC lease across SLEEP. No resident code,
allocation reservation, syscall number or executable ABI is added here.
SLEEP/POLL restore owned reply fields, but not the common ABI-minor byte;
SDK validation respects that distinction while checking synchronous versions.

**One stream is available system-wide.** Competing OPEN returns EMFILE, not a
shared handle. That also means loading a disk application can fail while a
native file reader/writer has a stream open. Start graphical peers first.
Each IEC operation is still synchronous; cancellation is serviced between
chunks, not halfway through a disk request. This is not asynchronous disk I/O.
Recovery bootfs has no file READ path: any directory handle returned by its
OPEN is immediately closed by the native SDK and reported as EISDIR.

Normal D64/D71/D81 now package `CAT.BIN` from `user/bin/cat.c`, a relocatable
native command, rather than the fixed APP1 multicall utility. `cat FILE`
sleeps one logical tick between chunks, reports meaningful errors, closes on
ordinary completion, and returns 0/1/2 for success/I/O-or-open failure/usage.
Ctrl+C yields 130 via the normal parent-owned cancellation path. CAT has
2,707 file bytes, 2,263 image + 2 BSS, fitting tasks 3/4/5 (not the smallest
task-6 allocation). It shares the four allocations with graphical programs;
there is no additional console slot. Other shipped utilities remain on the
synchronous path; the legacy multicall CAT implementation stays for compatibility.

Build with `distrobox-enter my-distrobox -- make -j8 boot` in this worktree.
Boot `build/boot/udeks.d64`, `.d71` or `.d81` and try:

```text
xclock &
xwave &
cat /hello
cat /etc/rc
cat /nofile
echo $?
```

The last command should print 1. Both windows should remain usable afterwards.
The disposable `build/native-console/files.d64` / `.d81` candidates also
include `/long`, `/empty`, `/one`. Run `cat /long`, interrupt with Ctrl+C,
check `echo $?` = 130, then `cat /hello` again. `cat /long &` may print above
an edited prompt; wait for it to finish before loading another disk app.

Container `make native-console-file-fixtures` builds two SDK clients;
host `make native-console-file-probe` qualifies disposable D64/D81. D81 adds
foreign-handle denial and deliberately leaked READ/WRITE handles on real
EXIT/CANCEL, including persisted binary bytes. Test flags only release the
clients; no owner, request, result or scheduler state is patched. The native
1986 disk-service harness checks CAT success/missing-file status beside a clock,
with actual keyboard and 1351 drag input. The user authorized finishing and
merging the feature; fresh physical C128/Pi1541 acceptance remains unreported.
Published downloads now match the exact normal images in the
[final evidence record](../bench/results/2026-10-09-native-console-files/README.md).

## Earlier checkpoint: arguments and completion

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
is separate. At that checkpoint the downloads still represented PR #51;
those exact inputs are now archived for historical evidence tests.

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
Increment 3's native filesystem ownership and utility migration are above.

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
