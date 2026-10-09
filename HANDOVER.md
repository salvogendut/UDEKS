# UDEKS engineering handover — Tasking 0.1 and graphics bring-up

This records the Tasking 0.1 implementation plan as of 2026-09-27 and later
engineering checkpoints. It is retained for reproducibility and handover, not
as the current priority list. The [roadmap](docs/ROADMAP.md) now sets the next
feature milestones; [PLAN.md](docs/PLAN.md) remains the architecture and ADR
0007 remains authoritative about the resident-core boundary.

## Current handoff — background console arguments/output, 2026-10-09

Issue #52, branch `tasking-native-console`, worktree `build/native-console`.
User accepted the input slice (platform unspecified); committed/pushed as
`9c9bfad`. The user also accepted this background-console slice and requested
commit/push. The test platform was unspecified; no new hardware result is inferred.
Root main's unrelated notes and published PR #51 downloads remain untouched.

Generic native `command args &` now receives up to eight argv entries, without
the trailing operator. A ninth parser offset recognizes the operator before
the eight-argument limit is enforced. Bare `&`/excess tokens give status 2;
embedded/nonfinal `&` stays text. Background launch skips the synchronous
loader and successful launch sets 0 instead of inheriting its stale exit byte.

Validated UTRQ fd 1/2 WRITE calls the terminal service, which temporarily
routes output above the active editor row. The existing root grid retains
prompt/input prefix, draft and cursor; output cursor persists between chunks.
Scroll/formfeed excludes the editor; a row-zero editor moves down once. New
input resets the output cursor; zero-count output changes nothing. No buffer,
queue, syscall number or native ABI added. Interleaving is allowed between
WRITEs, not within a counted request. Background stdin remains EIO; Ctrl+C
still selects only the foreground task. Legacy utilities remain synchronous.

Feature-enabling C size work shares row clear/copy and the cell writer, uses
cc65 `-Os`/serialized static scratch, and replaces the editor's disjoint copy
loop with resident memcpy. Normal/panic BSS ends `$93A7` (40 free), HIGHBSS
`$E2E0` (1 free), module `$E631` (18 free), TASKREQUEST 247/265. Scheduler
ends `$C862`. No app/stack/display/service reservation moves or shrinks.

Host tests exercise 21 editor rows × 55 draft lengths, mid-line editing,
submission, zero/full writes, wraps and formfeed; shell tests now use the real
tokenizer rather than pre-tokenized mocks. VICE D64/D81 cold boots qualify
eight arguments, split output, draft/cursor/history, input alongside ticker/
clock, cancellation/reuse, exit isolation, errors, code and stack guards.
D81 adds the BGREAD denial peer; D64 adds only ASK/TICKER because three extra
test apps exceed its free blocks. Existing D64 apps are not removed.
Native 1986 independently passes four-app keyboard/1351/drag/resize/Ctrl+C
regression, not the new TICKER/ASK scenario. Existing parser/UARG, input and
service-request CPU gates and their negative controls pass. Exact
[evidence and limitations](bench/results/2026-10-09-native-console-jobs/README.md)
include media, maps, sources, reports and checksummed captures.
Final `make check`: 1,600 tests pass. Placement/graphics/service-layout gates
pass; rebuilt D64/D81 match the qualified base media byte for byte. All owned
VICE sessions are closed.

Manual candidate: `build/native-console/jobs.d64` / `.d81` inside this
worktree. Run `xclock &`, `ticker Alpha mixed-case &`; partially edit an
`echo` command while it ticks, including left/right and Backspace, then Enter.
Run ticker again, then `ask`; verify typed input survives output and Ctrl+C
returns 130 without closing the clock or ticker. TICKER finishes itself.
No new physical-C128 or periodic-NMI qualification is claimed.

**Next:** increment 3: native filesystem ownership/SDK and one useful utility
migration. The current request is commit/push only. Do not
merge #52 as complete yet; keep quoting, pipes, arbitrary job control and
performance tuning outside this feature.

## Previous handoff — foreground canonical stdin, 2026-10-09

Issue #52, branch `tasking-native-console`, worktree `build/native-console`.
User accepted `98ff762` (platform unspecified), requested commit/push and the
next part. Push confirmed already synchronized; no empty commit was made.
Root main's unrelated notes and published PR #51 downloads remain untouched.

Foreground native apps now read edited lines through owned POLL + READ, with
24-byte private-buffer chunks, a 54-character line and newline. Background
SDK and raw READ/POLL return EIO before editor/consumption/wait mutation. Root
or ush owns input without a foreground child; otherwise only the selected
native task does. Query `$C8FC` reads the actual map-bound scheduler caller.
No public gate or executable ABI changes. SDK input is an optional archive
member so output-only programs do not carry it.

Application input cannot recall/add shell history. PROMPT resets partial and
unread input while keeping history. Existing parent CANCEL handles blocked
INPUT, cleans up, reaps, returns 130 and leaves peers intact. No raw/EOF mode,
background output arbitration, argument-bearing `&` or filesystem wrappers.

The small placement changes are feature-enabling: reuse line-copy code, share
the assembly whole-line/chunk-reader adapter, and clear the contiguous private
wait arrays with an asserted bound. Actual normal/panic BSS ends `$93CE` (1
byte spare), module ends `$E631` (18 spare), request gate uses 264/265 bytes.
Scheduler ends `$C862`, 29 bytes below storage; router/query uses its full 128
bytes. No app, stack, VIC/VDC, loader or service reservation changes.

ASK.BIN: 1,867 file bytes, 1,579 image + 4 BSS. BGREAD.BIN: 1,806 file bytes,
1,518 image + 4 BSS. Both fit all four ordinary allocations. ASK echoes one
input line; BGREAD is a silent negative-test peer, not a shipped utility.

Final VICE D64/D81 all-slot input/empty/full/backspace/cancel/reuse/background
denial suites pass, using keyboard queues and warp (no timing claim). Native
1986 separately passes real four-app keyboard/1351/Ctrl+C/guards regression,
not the ASK scenario. CPU ownership/reader tests pass 2,048 + 6,270 cases and
an intentional ownership-bypass negative control. Service request/stack bridge
CPU regression passes. Host SDK/editor/prompt tests and placement/graphics/
service-layout gates pass; `make check` passes 1,589 tests. Final rebuilds match
the qualified disks/apps byte for byte. [Evidence](bench/results/2026-10-09-native-console-input/README.md)
preserves exact media, apps, maps, raw captures, sources and hashes. Probe-only
repairs fix command synchronization, bank-explicit observation and allocation
expectations; no failed records are presented as qualification.

Manual media: `build/native-console/input.d64` / `.d81` inside this worktree.
Earlier `try.*` files are retained. Run `xclock &`, then `ask`: edit/Enter,
empty/long line, Ctrl+C mid-line (status 130), and drag clock during input.
The user accepted this foreground-input slice and authorized commit/push and
the next step. The test platform was unspecified; no new physical-C128 result
is inferred. All owned VICE instances close.

**Next:** finish increment 2 with argument-bearing background launch and
prompt-safe output; keep filesystem ownership/utility migration in increment 3.
Do not merge #52 as a completed feature yet.

## Previous handoff — task-based foreground Ctrl+C, 2026-10-09

Issue #52, branch `tasking-native-console`, worktree `build/native-console`.
The user accepted `bca650a` (platform unspecified) and asked for commit/push and
the next slice; it was already pushed with a clean feature worktree.
Root main's unrelated notes and published PR #51 images remain untouched.

Ctrl+C now queues a private root-session notice containing the exact foreground
native task id. Ush consumes it while waiting, then submits the existing CANCEL
operation as the real parent task 1. No window is required; no new syscall,
scheduler mutation, common gate or memory reservation was introduced.
Existing cancellation retires resources and discards pending waits; normal
bookkeeping harvests exit 130, destroys any window, reaps and releases the
foreground. Ush reports `Interrupted` after successful cancellation; `echo $?`
reports 130. A natural-exit race (ESRCH) is silent and keeps the real status;
other errors do not falsely release a live foreground job. New commands cannot
reuse the target id before the old notice/completion is consumed.

The matched disk and recovery shells implement the new private notice. Do not
mix an older ush into this candidate. Graphical foreground Ctrl+C uses the same
path; ordinary window Close, `name -q` and `xinit -q` remain advisory graphics
operations. Background output/stdin policy is still unimplemented. This is
cooperative cancellation, not an interrupt for arbitrary CPU-bound loops.

Placement: resident BSS now ends `$93C4` (11 bytes before TIME), seven bytes
smaller than the accepted checkpoint. Ush's actual BSS ends `$9F44`; its fixed
368-byte header reservation still fits below `$A000`. Loader/RELOC/ACCESS,
private stacks, display reservations and service module bounds are unchanged.
NAP.BIN is an independent, silent, non-returning sleep fixture: 1,231 file
bytes, 1,045 image + 5 BSS, fits all four allocations. It is added only to
disposable qualification media, never normal boot contents.

VICE D64/D81 passes all four foreground slots, untouched peers, status 130,
private wait/allocation cleanup, one storage retirement each, old-deadline
non-resumption, reuse with normal exit 37, graphical cancellation and idle
Ctrl+C. Native 1986 passes actual four-app keyboard/1351/Ctrl+C/cleanup
regression (not windowless NAP). Host tests cover the normal-exit race, failure
handling, notice consumption and exact parent request. Both actual-link
variants and graphics/service-layout gates pass. See [evidence](bench/results/2026-10-09-native-console-cancel/README.md).
`make check` passes 1,580 tests; the final rebuilt disks match the qualified
media byte for byte. Refreshed manual media are `build/native-console/try.d64`
and `.d81` inside this worktree.
Probe-only fixes made clock observations atomic and drained keyboard count,
not queue head; only fresh successful evidence is retained. No new hardware,
periodic-NMI or performance result is claimed. All owned VICE sessions close.

**Next:** foreground stdin and explicit rejection of background reads, then
argument-bearing background launch/prompt-safe output. Keep increment 3's
filesystem ownership/utility migration separate. Do not merge #52 as complete.

## Previous handoff — native console arguments and exit, 2026-10-09

Issue [#52](https://github.com/salvogendut/UDEKS/issues/52), branch
`tasking-native-console`, worktree `build/native-console`. The user accepted
execution checkpoint `f56eb32` (platform unspecified) and requested commit/push
and the next slice. It was pushed before this implementation. Root main's
unrelated notes remain untouched; published `build/udeks.*` remain PR #51 images.

**Increment 1 implemented:** 81-byte UARG 0.1 in existing private relocated
ZP `$80-$D0`, up to eight arguments/54-character line, copied before RUNNABLE.
No stack borrowing, header change, private kernel imports or extra allocation.
Old graphical entry registers remain zero; the new SDK returns 126 if UARG
is missing/unsupported. Foreground status is harvested before reap into SHLL+10;
ush snapshots it on completion and supports exact `echo $?`. Background exit
does not replace foreground status. Synchronous utilities are unchanged.

TICKER: 2,076 file bytes (1,738 image + 91 BSS); silent peer QUIET: 1,464 file
bytes (1,240 image + 85 BSS). Both fit all four ordinary allocations.
Placement replaces the 237-byte C tokenizer with 77 bytes of assembly (C remains
the test reference), and moves the 65-byte basename adapter into MODULECODE.
No reservations move. Resident ends `$93CB` (4 free); loader CODE/RELOC/ACCESS
have 11/18/1 free; MODULECODE has 61 free. Measure before growing any service.

`make check` passes 1,571 tests. CPU differential/entry checks and normal/panic placement, graphics and
service-layout gates pass. VICE D64/D81 proves private arguments across sleeps,
eight tokens, foreground 37, background exit isolation, parser error 2, code/
guards, clock scheduling and injected dragging. Four-app VICE and native 1986
service/keyboard/mouse regressions pass. The 1986 regression is not a new
native-console argument test; no new hardware or periodic-NMI claim is made.
[Evidence](bench/results/2026-10-09-native-console-arguments/README.md) preserves
candidate media, programs, raw dumps, reports and reproduction instructions.

**Next: increment 2 — terminal ownership.** Start with no-window task Ctrl+C
and foreground stdin, then argument-bearing background launch and prompt-safe
output/read policy. Cancellation must not require a window. Bare `name &`
is unchanged, not general console job control. Raw YIELD still lacks an owned
reply; use SLEEP. Filesystem wrappers/utility migration remain increment 3.
Do not merge #52 as complete. See [the plan](docs/NATIVE-CONSOLE-APPS.md).

## Previous handoff — native console execution checkpoint, 2026-10-09

Issue [#52](https://github.com/salvogendut/UDEKS/issues/52), branch
`tasking-native-console`, worktree `build/native-console`, based on merged
PR #51 (`15eddb4`). Root main's uncommitted roadmap/handover/proposal notes
remain untouched. The [current plan](docs/NATIVE-CONSOLE-APPS.md) advances that
saved proposal after the first disk-loaded service was completed.

`make native-console` independently builds TICKER.BIN (1,602 file bytes,
1,338 image + 8 BSS, fits all four allocations). Its private runtime copies
stdout/stderr through UTRQ WRITE and uses owned SLEEP responses. No kernel,
shell, loader or public ABI change; ordinary boot disks are unchanged.
`make native-console-probe` runs disposable D64/D81 VICE proofs: no implicit
VIC/window, output, private state, sleep/resume, retirement/reuse, unknown-name
PULSE, peer clock scheduling and injected pointer dragging during execution.
Host tests cover streams, bounds, short writes, error/ownership rejection and
sequence wrap. `make check` passes 1,561 tests; actual-build placement,
graphics and service-layout gates pass. Preserve the evidence, not just PASS labels.

**Next:** bounded task-private arguments and shell completion status, then
terminal ownership/Ctrl+C/`&`, then utility migration. This checkpoint passes
argc=0/argv=NULL; native return 37 is not yet reported by the shell. Never call
bank-0 pointer veneers from bank 1. Raw YIELD does not restore an owned reply;
the new checked SDK deliberately exposes only sleep. Console/graphics share
the existing four slots. No stdin/filesystem wrapper or extra capacity here.

Resident space is only 2 bytes; loader CODE/RELOC/ACCESS have 25/18/4 bytes.
Measure placement before adding argument delivery; preserve C-stack guards and
the EXIT tail. Tests do not establish new 1986/native-input/physical-C128
qualification. Do not merge the broader feature as complete on this proof.

## Previous handoff — default disk-time boot, 2026-10-09

Issue [#49](https://github.com/salvogendut/UDEKS/issues/49), completion branch
`services-0.1-default-boot`, worktree `build/default-service`, based on merged
PR #50 (`9eda8ba`). User authorized all three steps, testing and merge on success.
Unrelated edits in the root main worktree were left untouched.

1. Normal `make boot` now links the time-slot manager/read wrapper, not `time.o`.
   Both configs reserve `SERVICEBOOT`; `/etc/rc` runs `svc load /TIME.SVC`.
   `service-boot` aliases normal boot; obsolete `DISK_TIME=0/1` is rejected.
   Registry, request gate and IEC router depend explicitly on `mk/services.mk`
   so upgrades recompile every flag-sensitive object.
2. `service-layout-check` audits both actual maps and emitted vectors;
   `service-rebuild-check` proves fresh-copy determinism;
   `service-migration-check` builds resident-time `9eda8ba`, copies only changed
   source inputs over its existing outputs, upgrades without clean, and checks
   exact three-disk parity plus a no-op next build. No frozen memory bounds move.
3. Normal D64/D71/D81 are published under `build/udeks.*`, with current README,
   checksums and [evidence](bench/results/2026-10-09-default-time/README.md).

VICE qualifies all formats (RC, exact module bytes, date/clock, stop/reload,
duplicate refusal and disk-only revision replacement); missing/corrupt TIME.SVC
and missing/corrupt disk ush remain recoverable. Native 1986 qualifies D64/1571
keyboard/1351 drag, service lifecycle and console input. CPU lifecycle/request
proofs pass again. No new physical-C128 or arbitrary timer-NMI stress claim.

The broader regression caught a prior app-size bug: offline checks made xclock
six bytes too large for slot 4. A constant-base title copy saves eight code
bytes; both offline checks remain and no system reservation changes. The
actual-build graphics gate now verifies coexistence in all 24 launch orders.
Full D81 four-app move/resize, unknown-app admission/reuse and cleanup pass.

Recovery skips RC and unmounts the failed system root: use `mount 8 /mnt`, then
explicit `/mnt/svc.bin load /mnt/TIME.SVC`, `/mnt/date.bin`, etc. Bare `svc`
does not resolve there; the recovery mount is deliberately read-only.

The original layout budgets still hold: live BSS through `$93CD` (2 bytes
spare), startup `$93D0-$95D5`, module 710 emitted + 7 BSS of 728 reserved.
Do not grow resident code without a placement decision. The first fixed-slot
extraction is complete; next work is a bounded task/service feature from the
roadmap, not open-ended optimization. Historical candidate notes below describe
the pre-cutover build and must not be mistaken for current boot instructions.

## Previous handoff — disk-loaded time service, 2026-10-08

Issue [#49](https://github.com/salvogendut/UDEKS/issues/49), branch
`services-0.1-disk-module`, worktree `build/disk-service`, based on PR #48's
merged `672110d`. Root main's unrelated edits are untouched. The user selected
time-of-day service extraction, not scheduler timing, then authorized work.

**Committed and pushed:** `2ff8c01` (standalone module), `ed7a1f7`
(permanent startup latch and CPU-tested lifecycle), `9e56af5` (actual
normal/panic overlay links, placement fit), and `0e31b82` (bounded request,
ownership bridge and standalone loader). The 21-byte production
startup guard caches success/failure permanently and rejects recursive entry;
the resident time implementation remains installed by normal boot.

**Accepted for merge:** coherent boot integration and emulator gates. The user
confirmed "all is well" and requested PR/merge; the test platform was not
specified, so this is not a new physical-C128 qualification claim.
`make service-boot` builds fresh isolated source copies, regenerating EVERY
map-bound import, router, split output and disk file through the normal Make
dependency graph. Candidate media are `build/services/boot/udeks.d64`, `.d71`,
`.d81`; `latest.json` identifies their exact source/maps and hashes. The normal
`build/boot` path remains resident-clock, not disk-clock. `DISK_TIME=1` is
rejected outside the generated sandbox to prevent mixed stale objects.
The updated actual normal/panic links still fit, not merely object arithmetic.
`make time-overlay-check` independently relinks those variants under
`build/services/time/overlay/`, redirects every split output there, and checks
all protected memory boundaries against the baseline maps. Do NOT run these
raw kernel links: map-bound boot imports/delivery are not rebuilt for them.

- Live resident BSS ends at `$93CD`; `$93CE-$93CF` gives **2 bytes** before
  the provisional slot `$93D0-$96A7`. The request adapter consumed 48 of the
  previously qualified 50 bytes. Do not silently grow this reservation.
- `SERVICEBOOT` is actually linked at `$93D0-$95D5` (518 bytes). It may be
  replaced only after the private startup latch reports returned-success.
- The module is **710 emitted + 7 BSS = 717 bytes**, leaving 11 bytes in its
  728-byte slot. No private kernel-map bridge; runtime ZP remains UAPP 0.1.
- The manager is **500 bytes** (479 CODE, 20 RODATA, 1 BSS). The retained
  C clock-read wrapper is another **57 bytes**, now explicitly charged.
- `$CF40` targets the guarded setter; `$CF60` still uses the original C
  calling convention. An actual one-byte-overflow negative link fails the
  new resident-bound assertion. No app, stack, VIC, VDC or common area moved.

The candidate adds UTRQ 0.19 operation 28 behind CF30, with a 3-byte payload
(action, actual received length LE), reserved descriptor/flags zero and a
one-byte state reply. `src/services/module/request.inc` shares the exact
instructions between the actual gate and CPU proof. The internal abort/reply
leaves fit existing CF33/CF43 padding; these are NOT new public call gates.
The C880 router is 101/128 bytes, derives foreground ownership from trusted
current-task/state records, rejects native callers including malformed IDs,
and aborts a partial lease on tag-9 retirement. Published services survive
the loader's exit; other task retirements do not affect the lease.

`make service-command` produces `build/services/command/SVC.BIN`: 2,198 bytes
(2,182 payload + 69 BSS, leaving 309 bytes in the fixed console allocation).
Commands: `svc status`, `svc stop`, `svc load [FILE]`, default `/TIME.SVC`.
It probes support before any slot writes, opens read-only, bounds chunks,
requires clean EOF and successful CLOSE before commit, and preserves the first
error during close/abort. It cannot overwrite an already published module.
The independent SDK saves/restores private ZP $02-$1F (never CPU ports $00/01),
temporarily binds the foreground software stack to module sp=$06, normalizes D,
and validates reply sequence/result/state. No kernel-map imports in command/module.

The former 174-byte deficit was at the old `$9300` base with a 548-byte
manager and a 797+10-byte module, before charging the legacy read wrapper.
The new fit comes from compact checked 16-bit comparisons and candidate-only
C simplifications (fixed-field counters, byte BCD lookup, fewer raw copies),
not omitted validation. Normal time code is unchanged. Checksums, complete
received length, BSS bounds, unpublished start and cached post-start callbacks
remain required. The old candidate address is not an accepted load ABI.

Qualification: `time-module-check` executes 174,459 calls, all 86,400 times,
1,024 raw TOD encodings, counter rollover and the existing TI/lifecycle/guard
checks. `time-slot-check` executes 436 independent validation cases, all 256
startup results, failure/abort/reload and the actual retained C read wrapper
(2,142 protected calls). Both negative controls still fail as intended.
The new `service-request-check` runs the actual CF30 gate, C880 router, bootfs
finish handlers, manager, console SDK and sealed module together: **1,832 calls**.
It checks malformed requests, wrong callers, retirement, reload, poisoned ZP,
stack balance and D preservation. Removing the stack bridge must fail its
negative control (the wrong but writable simulator stack is explicitly guarded).
Host tests execute the real `svc.c` against fake filesystem/request endpoints
through 17 success/error/close/overflow/unsupported-kernel scenarios.
These are real 6502 execution tests with RAM-backed CIA registers, **not** TOD
latching, disk-loading or new physical-C128 qualification. `make check` has
1,537 host tests; normal and candidate boot/graphics/placement gates pass.

`make boot` remains the production path and does **not** enable the overlay.
The candidate must never be loaded at `$93D0` into that baseline's live RAM.
Normal DATE/XCLOCK binaries now also refuse an unavailable snapshot. This
changes normal disk hashes; it does not enable service loading there.

The candidate's bounded `RC.ETC` runs `svc load /TIME.SVC` after startup returns.
`date` reports unavailable and exits 1 while offline; `xclock` exits 5 and
normal native retirement removes its window. Neither consumes stale time.
All three formats pass VICE cold boot, actual file loading, set/read, clock,
stop/reload, duplicate-load busy refusal, missing-file error, disk-only revision-2
replacement (no kernel relink), and console input afterward. Missing/corrupt
boot-module fixtures leave the shell usable and recover by loading a good file.
These runs use disposable media and the ordinary shell keyboard-event path;
the monitor only observes records, never installs or calls the module.

D64 still omits only `xsprdef`: **19 blocks free**, no further removal needed.
D71 now explicitly allocates both sides using its standard second BAM;
D64 is rebuilt separately on side one, never truncated from a two-sided chain.
D71/D81 keep all apps. Two fresh parallel candidate builds have identical
disk hashes. The final checksum-only negative preserves the module header.

Host `make service-start-probe` passes on a disposable D71 in Flatpak VICE:
date set/read, background xclock, cat, clock shutdown, and re-entry after SREG
corruption plus JAM poisoning of retired startup. Evidence/report lives under
`build/services/time/vice/startup-969d9a6i`; CPU and size reports are adjacent.
The test must corrupt and call atomically: ordinary registry polling can
legitimately change SREG between separate monitor sessions. The final monitor
payload is bounded to 34 bytes. These fixture issues were fixed before the
passing run; they were not production boot failures. No VICE process remains.

Native 1986 D64/1571 now passes RC loading, date, clock creation, a real 1351
drag, stop/removal, reload, busy refusal, clock restart and console input.
The user accepted this opt-in integration for merge. Next: normal-boot cutover
with a clean-build/migration gate; issue #49 stays open for that remaining work.
Physical C128/Pi1541 testing remains unrecorded for this change.
The native probe's first attempt clicked at unadjusted bitmap coordinates;
its corrected version includes the VIC pointer bias (12,40). Do not count the
failed first attempt as a passed drag gate. Candidate build/probe provenance
is recorded under `bench/results/2026-10-08-disk-service`.
Do not turn CPU RAM-backed evidence into a claim about real disk transport,
arbitrary IRQ interleavings or physical TOD latching. The separate periodic
CIA2 timer-NMI loader failure remains unresolved.
Keep the loader/policy out of the kernel where possible; do not expand app or
stack reservations. Candidate layout/contract and remaining lifecycle gates:
[abi/services.md](abi/services.md#disk-time-candidate--issue-49-2026-10-08).
Manual acceptance is recorded above; no new identified hardware result. This is one provisional
time-module slot, not a generic arbitrary-service allocator or Unix daemon.

## Previous handoff — writable root and file commands, 2026-10-08

Merged PR #48 as `672110d`; issue #47 is closed.

**Latest state (supersedes the historical checkpoints below):** full UTRQ 0.18
service and independent `cp`/`mv`/`rm` now fit and are installed by `make boot`.
The former failed-link evidence remains historical, not overwritten. Compact
`mutation_6502.s` and the writer status parser match their independent C
references over 35,320 + 6,193 sim6502 cases. The SDK checks 24 scenarios.
Policy stays in C; only the bounded low-level encoding/status path is assembly.
Current service slack: CODE 3, POLICY 5, DRIVER 0, HIDDEN 3 code bytes, BSS 26;
the original application and stack reservations are unchanged. Do not grow a
service region just to make the next feature link.

DOS listener busy uses a held initial TALK handshake and same-owner/op status
polls, not reissuing a command or spinning 255 rounds in the service. Every
pending return restores speed and leaves the common-RAM/IRQ lease. Explicit
CLOSE and trusted retirement release pending ownership; no rollback is claimed.
The legacy console allocation remains synchronous (no unsafe native YIELD).

Fresh images: `build/storage-file-commands/build/boot/udeks.{d64,d71,d81}` from
the repository root. D64 is rebuilt without `xsprdef` (31 free blocks); full
D71/D81 retain it. SDK archive members are split so commands link only their
needed functions. CP/MV are 1,747 bytes; RM is 1,674 bytes.

VICE public command/reboot gates pass on all three drive types. Additional
binary/graphics checks run through `storage_public_probe.py --mutations`.
Native 1986 ordinary D64/1571 testing also passes, including actual keyboard,
CP/MV/RM, empty/binary copies, clock dragging, RESTORE and reboot persistence.
Exact images, reports and known failures are preserved in
`bench/{artifacts,results}/2026-10-08-file-commands` with checksums.
Native 1986's periodic CIA2 timer-NMI stress found `save: loader error`; the
old harness incorrectly accepted stale success text and exit status, then
failed reboot readback of `/nmitest`. The harness now checks loader state and
the submitted command too. `--skip-write-timer-stress` explicitly isolates
ordinary file/input/RESTORE testing; its report must never claim timer-NMI
qualification. Preserve this as an unresolved regression, not a passing gate.
One earlier VICE D64 run also returned EIO after a scratch had taken effect;
subsequent runs passed. This is why error paths promise no rollback or retry;
retain the observation for hardware acceptance.

The user accepted the delivered images on 2026-10-08 and requested commit,
push, PR and merge. The test platform was unspecified; this does not establish
new physical-C128 or periodic timer-NMI qualification. The next architectural
feature is the first disk-loaded non-kernel service, not further storage tuning.

For a separately recorded hardware check, on a **disposable** image run `cp /hello
/COPY`, `cat /COPY`, `mv /COPY /MOVED`, `cat /MOVED`, `rm /MOVED`, and confirm
`cat /MOVED` reports ENOENT. Check collision rejection, RO remount rejection,
empty copies, and a copied file after reboot. Do not remove system commands.

### Historical checkpoints (not the current availability statement)

The sprite-editor checkpoint merged via PR #46 as `1a45100` after 1,366 host
tests and the container build/graphics/placement gates passed. The user now
requests a read/write default for device-8 `/`, plus standalone `mv`, `cp`
and `rm`, and explicitly requested an issue/branch.

Track [issue #47](https://github.com/salvogendut/UDEKS/issues/47) on
`storage-0.4-file-commands`, worktree `build/storage-file-commands`, based on
that merged main. Scope is at the top of the [roadmap](docs/ROADMAP.md).
Keep root main's unrelated edits and all original media untouched.

First resolve the generic service contract and measured placement. The current
bank-1 storage service has one open descriptor, so bounded copying requires an
explicit mechanism, not an assumed second stream. Preserve SEQ/PRG bytes/types,
RO enforcement, namespace resolution and owner cleanup. Initial destination
collisions fail rather than overwrite; rename is same-filesystem only, and
remove acts on an explicitly named regular file without wildcards. Qualify
only disposable disk copies. Do not claim hardware acceptance of these new
operations from the earlier create-only tests.

### First implementation increment

The user accepted this checkpoint on 2026-10-08 (test platform unspecified)
and requested commit/push followed by service integration. Committed/pushed
as `e853885`. Automated gates:
1,382 host tests, normal boot/graphics/placement builds and the probes below.

Normal disk bootstrap explicitly uses MOUNT 0.14/RW and clears the flags before
OPEN or recovery UMOUNT. This changes the default, not unqualified MOUNT's
semantics: device 9 `/mnt` remains RO unless requested RW; recovery bootfs stays
RO. A runtime RO remount resets to the boot default on reboot. Published
download images have not been replaced by this worktree's candidates.

`build/storage-file-commands/build/boot/udeks.{d64,d71,d81}` (relative to the
repository root) contains the candidate. On a **disposable copy**, boot, run
`df` (RW), `save /RWTEST 24`, `mount -o remount,ro 8 /`, then
`save /ROTEST 1` (Read-only filesystem). Reboot and run `save -c /RWTEST 24`.
At this first checkpoint the three new commands were not yet in these images.

Qualification in the worktree:

- VICE true-drive 1541/1571/1581: `storage_public_probe.py` creates BOOTRW
  before any remount, checks RO rejection, binary/empty writes and cold-boot
  persistence, preserving all original files. Native 1986 rev `19386ef` uses
  its ROM-backed 1571 with D64 and passes RW default, explicit RO rejection,
  later writes, RESTORE/recurring CIA2 NMI, clock/input and reboot readback.
- Missing-shell recovery boots bootfs, executes a program on independently
  mounted device 9, unmounts and keeps console/IEC code intact. Its integrity
  check now excludes only the five declared lease-state bytes and twelve
  generation/error bytes, resolving the latter from the live build's map.
  Every remaining code byte is still compared; negative tests cover corruption.
- `storage-mutate-backend` builds an isolated PRG, not a production service.
  `storage_mutate_probe.py` generates blank disposable media; its VICE
  1541/1571/1581 runs validate nonempty SEQ/PRG copy, same-disk rename, exact
  scratch counts, collisions, missing sources, write protection, both 16-byte
  names (38-byte command), original/source survival and final byte/type equality.
  The known-empty SEQ fixture takes the existing create/checked-close path;
  stock DOS COPY would add CR. Real source-emptiness preflight is still due.

Private implementation: `cbm_mutate.c` accepts exact padded physical names,
never arbitrary DOS strings. It parses full DOS status, distinguishes zero/one
scratched file and never retries a mutating command. Error track/sector values
need not be zero (1581 write-protect reports 40/03). The conditional IEC
command-only entry saves/restores the caller's CPU speed and serial/VIC bank
bits, does not open/close data channel 2, and never CLOSEs command channel 15.
DOS COPY can hold DATA low while doing disk work before accepting TALK 15:
only this command-only build gets a larger bounded listener-busy wait (about
150 seconds worst-case at 1 MHz). Bit/EOI/frame-edge waits remain unchanged.
All mutation instrumentation/extensions are conditional and absent from the
production transport. No public ABI version or operation is added yet.
The long busy wait is a standalone electrical/protocol proof, **not** a
production responsiveness qualification. Integration must define bounded
service occupancy/completion (and lease ownership while DOS is busy); do not
hold the live cooperative system inside that worst-case wait without a gate.

**Remaining delivery:** service-owned source/destination namespace validation,
RO/handle/generation checks, verified-empty detection, generic request/SDK
contract, safe placement and disk-loaded `mv`/`cp`/`rm`, then public acceptance.
Initial copy/rename stay on one mounted filesystem; destination collisions
reject, removal is exact and nonrecursive. Partial files may remain after an
error; no rollback, atomic-replacement or power-failure claim.

That checkpoint's production map had CODE 20 + STORAGECODE 71 + IECCODE 43 +
STORAGEHIGH 41 = **175 spare code bytes**, BSS **384/384**. The new private
backend alone is about 1.2 KiB of C code before service policy/SDK work. It
could not simply be appended to that link. Do not borrow native app
allocations, the live shell/software stacks, graphics memory or recovery
bootfs without an explicit measured ownership/delivery design. The following
increment addresses that prerequisite without changing any memory reservation.

Evidence: `bench/artifacts/2026-10-08-storage-files` holds the exact D64,
private mutation PRG/map and production storage map; corresponding
`bench/results/2026-10-08-storage-files` holds public/recovery/native reports,
all three private-mutation reports and their final disposable media. Both
directories have checked SHA256SUMS. The D64 hash starts `6a6afcdd3556`;
the qualified private PRG starts `4ff4c77210ff`. `test_storage_file_checkpoint.py`
audits those records and actual media, including all source/KEEP bytes and
the zero-length destination. Reports distinguish private mechanism tests
from unavailable public commands.

Reproduce inside this worktree (build through `distrobox-enter my-distrobox`):
`make -j8 boot graphics-apps-check placement-check storage-mutate-backend`.
On the host run `python3 tools/storage_mutate_probe.py --drive all`; it creates
its own disposable disks and never accepts an existing disk. Public boot
qualification uses `tools/storage_public_probe.py` on copied boot media;
`tools/root_namespace_probe.py --recovery` checks fallback. Native regression
uses container `tools/1986_storage_smoke_build.py --storage-write` with sibling
emulator/ROM paths and the candidate D64. No physical acceptance is claimed.

### Service-capacity increment — 2026-10-08

Committed/pushed as `7389ccf` on the user's instruction before the next increment.

`cp`, `mv` and `rm` remain **standalone disk programs**, not ush builtins.
Filesystem validation belongs to the storage service; putting command parsing
in ush would not solve the service's capacity limit.

The five namespace functions now use compact `namespace_6502.s` inside the
same serialized service. No new ZP, app memory or stack space is taken. The
unchanged `fs_namespace.c` stays as the executable C reference. Container
`make storage-namespace-check` compares 36,532 cases on sim65, using actual
cc65 argument marshalling, output guards and rejection checks. A deliberately
wrong success return fails at the first case; both executables/logs are saved.
Keep the assembly basename distinct from the C file: cl65 generates/deletes
the sibling `.s` intermediate when building the reference.

Production now has **1,850 code bytes and 54 BSS bytes free** (1,675/54
recovered). `make storage-mutation-layout` separately links the private backend
with the real service and unaltered region bounds: **563 code / 19 BSS bytes
remain**. This is a fit proof only, **not** public handlers or live mutation
qualification. The shipping transport still has no mutation/long-wait flag.
The audit rejects changed/missing regions, overflow and uncounted DATA.

Gates: 1,392 host tests; container boot/graphics/placement checks; fresh VICE
1541/1571/1581 write/RO/collision/reboot/source-preservation runs; native 1986
write/input/graphics/NMI/reboot regression; missing-shell recovery. Exact D64
(`8f141fb06fd2`), maps and sim65 programs are in
`bench/artifacts/2026-10-08-storage-namespace`; reports, source/toolchain
provenance and checksums are in the matching results directory. No additional
hardware acceptance is claimed. The previous evidence is unchanged.

**Next:** service-owned preflight and request/SDK wiring, bounded DOS completion,
then ship and test the three commands together. The 563-byte remaining budget
still has to cover integration; it is not a promise that unmeasured handlers fit.
`mv`/`cp`/`rm` are not yet present in the rebuilt candidate images.

### File-operation policy, SDK and command candidates — 2026-10-08

Implemented behind **`UDEKS_STORAGE_MUTATIONS`**, not enabled in production:
service RENAME/COPY/UNLINK checks plus standalone C `mv`, `cp`, `rm` and SDK.
The candidate wire/descriptor-consumption contract is at the top of
`abi/task-request.md`; released UTRQ remains **0.17**, candidate is 0.18.
Ownership uses the trusted instance/generation. Wire/path/RO/type rejection
retains the handle; after that it is consumed even if IO fails. The SDK always
cleans up and preserves the primary error, without retry. Destination lookup
must finish before mutation, including folded and BIN/SH collisions. Source
identity comes from the held descriptor, not query/device scratch that another
rejected request could have changed. Empty copy is proved from byte zero and
uses checked exclusive create with the original SEQ/PRG type.

`make file-commands-candidate` produces independent CP.BIN/MV.BIN (2,157 bytes
each) and RM.BIN (2,026), all within the existing foreground allocation, with
quiet success, stderr errors, exact operands and `--`. These are **not added
to boot disks**. `make file-mutation-sdk-check` executes 21 scenarios using the
actual cc65 C/ASM client and a simulated CF30 gate: versions, counts, sequence
wrap, malformed responses, primary-error preservation, cleanup and guards.
Host service/SDK tests use the real namespace and sector reader with a captured
mutation backend; 82 cases (including inherited compatibility) pass, plus four
CLI tests. No live mutation-service or hardware acceptance is claimed.

**Placement gate fails honestly:** `make storage-mutation-policy` compiles the
full candidate, keeping all production reservations. With service `-Os`, the
handler is 955 code bytes; HIDDEN overflows by **586 bytes**, with CODE 123 +
POLICY 139 + DRIVER 19 spare elsewhere: at least **305 additional code bytes**
must be recovered, plus redistribution. BSS uses 374/384 (10 free). No region
was expanded; no failed output is installed. The layout tool writes an explicit
`link_passed: false` report and still exits nonzero. This measurement does not
include the bounded/asynchronous DOS completion work that remains necessary.

Gates: 1,482 host tests; three standalone command builds; real-6502 SDK and
namespace checks; normal boot/graphics/placement gates pass. Production
D64/D71/D81 are byte-identical to the capacity checkpoint, so its emulator
evidence remains applicable. Exact candidate executables/maps, simulated SDK
image/log, **failed** policy map/log/budget and source hashes are preserved in
`bench/{artifacts,results}/2026-10-08-file-command-policy` with checked manifests.

**Next delivery work:** recover the remaining bytes in the private DOS
encoding/status path, implement bounded service completion/ownership while
DOS is busy, then enable the requests and add the commands to all three disk
formats for end-to-end acceptance. Do not enable the existing private
150-second busy-spin in the cooperative system. No new manual test is due yet.

## Earlier handoff — sprite number and held painting, 2026-10-08

The user accepts the visible sprite number and held-button painting, following
acceptance of fast pixel updates, larger-app capacity, Save/Load and BASIC
export (latest manual-test platform unspecified). On 2026-10-08 they requested
commit, PR and merge of the accumulated `graphics-xspr-pixel-update` branch
in `build/graphics-xspr-pixel-update`.
Root main's unrelated edits, sibling 1986 source and published disks are untouched.

The editor shows **1–8 beside the preview**, also during editor dialogs.
A primary CLICK in the grid chooses draw/erase from the toggled first cell.
HELD samples extend that ink, without toggling again when stationary/retracing.
Bresenham interpolation lives entirely in the app. It commits **one changed
cell per PRESENT_DELTA**, yielding between steps; long strokes do not fall
back to full-window repaint. The first full-repaint prototype delayed pointer
updates in the native mouse test and was replaced. Release, outside-grid input
or focus loss ends a stroke. Held input cannot activate toolbar/dialog buttons;
title-bar dragging remains the WM's gesture. A bounded segment already sampled
may finish before the next pointer poll. This is coalesced input, not a lossless
motion queue; unobserved excursions cannot be reconstructed.

Generic UTRQ **0.17** adds GRAPHICS `INPUT` (7). Old EVENT stays click-only.
INPUT preserves geometry/click ordering and adds state 4 HELD, signed relative
X and Y (`P[3]` low / `P[7]` high). Live replies are eight bytes; CLOSED keeps
the existing seven-byte reply with only state valid. The owner/focus/busy checks
precede the held snapshot; IRQ masking covers only the short pointer read and
coordinate arithmetic. The earlier minor rejects INPUT with EINVAL.

The existing graphics reservations were full: `graphics_event.s` replaces the
old EVENT marshalling and two equivalent shared adapters (geometry arguments
and eight-byte retained read), without moving reservations or adding state.
Normal/panic maps pass: GRAPHICSCODE `$0C00-$12FF` (**full**), GRAPHICSHELP ends
`$A1D9`, MODULECODE `$E5E8`, MODULERODATA `$E633`, resident BSS `$96A4` (three
bytes before VDC assets). Do not silently grow these areas. A new sim65 gate
executes the actual assembly against an independent C oracle: 2,048 cases,
including legacy EVENT, resize/click ordering, signed outside coordinates,
focus/busy/buttons, geometry/copy calling conventions and request guards.

Editor: **6,920 file / 6,458 image+BSS bytes**, 50 scene commands, still the
same joined task-3/task-4 allocation with two compatible peers available.
S/L/BSV formats and create-exclusive policy are unchanged. Host tests include
all eight labels, modal visibility, stroke retracing/erase, interpolation in
every direction, held-control isolation and retry behavior.

Current checks/evidence: **1,366 host tests**, container `boot graphics-apps-check placement-check`,
VICE `build/sprite-paint/vice-d64` (pixel deltas, move, uncover, coexistence,
console/close), and `build/sprite-paint/files/files-1541-_jjg0ts6` (persistence
plus stock BASIC BLOAD/BSAVE) pass. Native 1986 `19386ef8` D64 held-input
qualification passes under `build/sprite-paint/1986-d64-final`: ten exact
single-cell edits (13–15 PAL frames including release), held paint/erase,
stationary/retrace, diagonal, toolbar isolation, title drag, console and close.
It requires zero full compositions throughout stroke editing. The harness now
waits for each relative mouse movement to be sampled before sending another:
the former four-frame controller queued duplicate corrections while drawing
and overshot the grid (trace: X 196, 196, 196, 220 for a target of 212).
Earlier r0/r1/r2/r3/trace runs are diagnostic, not passing qualifications.
Final D64 hash `6fba5c94…50ef50` matches both VICE and native probe inputs;
all three formats rebuild. See XSPRDEF for repeatable commands. Do not claim a
new physical-C128 result.

Next: finish the authorized PR/merge, then return to the roadmap's disk-loaded
service milestone. No further sprite feature is required for this accepted
checkpoint. Overwrite, thumbnails, keyboard editing, undo and multicolor remain
deferred. The earlier unrelated four-native wave-resize timing caveat still
applies. The historical handoffs below describe their then-current status;
this accepted checkpoint supersedes their pending-test/no-merge notes.

## Earlier handoff — BASIC-compatible sprite export, 2026-10-08

The user accepted Save/Load (platform unspecified) and requested compatibility
with C128 BASIC's `BSAVE ...,B0,P3584 TO P4096`. Added list-screen **E**, with
Y/N confirmation, exporting all eight session sprites to `/SPRITES.BSV`.
From the pixel editor use B → E → Y; B retains the current edit. These are
mouse buttons. S/L still use the original 504-byte `SPRITES.SPR`; L does not
import BSV. Both saves remain create-exclusive and require an explicit RW
mount. No overwrite, delete, automatic remount or retry was added.

The export is a genuine Commodore PRG: `$00,$0E` load header plus eight
63-byte sprites, each padded with one zero byte (514 file bytes). A streaming
encoder uses the existing 24-byte request buffer, not another sprite bank.
BASIC loads it using `BLOAD "SPRITES.BSV",B0,P3584`, or just
`BLOAD "SPRITES.BSV",B0`. Loading alone does not display sprites.

Important qualification finding: the initial SEQ-file experiment with `,S`
loaded on the 1541 but failed with stock 1571/1581 burst BLOAD. It is superseded
by generic UTRQ **0.16**, adding opt-in OPEN mode 4, CREATE_PRG, through the
existing file path. Ordinary CREATE stays SEQ; all ownership, root/path,
read-only and collision checks remain unchanged. The client supplies the
header; the filesystem never adds one or handles app names specially.
Backend create takes an explicit SEQ/PRG type; empty-file finalization supports
both exact closed types, still rejecting locked or unclosed entries.

No memory reservations moved. Two existing pure helpers (`lower` and
`dos_errno`) moved to IECCODE within the same bank-1 storage mapping to fit:
STORAGECODE ends `$C5B8`, IECCODE `$E8D4`, STORAGEHIGH `$FED6`; BSS remains
`$E000-$E17F`. The editor is **5,877 file / 5,687 image+BSS bytes**, using
joined task 3/4 capacity; two compatible peers remain possible.

Qualification: **1,360 host tests**, boot D64/D71/D81, graphics-apps-check and
placement-check pass. Fresh VICE 1541/1571/1581 runs pass Save/Load/export,
cancel, RO/existing-file errors, console, uncover, guards and cold reboot.
Each independently decodes the output and uses a separate stock BASIC boot
to test both BLOAD forms, all 512 RAM bytes plus adjacent guards, and a
byte-identical BSAVE round trip. No monitor LOAD substitutes for BASIC.
Native 1986 `19386ef8` D64/1571 passes actual keyboard/1351 file dialogs,
export, console and cold-reboot Load. Ordinary public SEQ write/reboot
regression passes on VICE 1541 too. Physical C128 export acceptance is pending.

Final evidence is under `build/sprite-prg/`: `files-1541-5dc_eqer`,
`files-1571-4_3e6wzs`, `files-1581-hq94fj9a` (each has `basic/result.json`),
`1986-d64/sprite-bd4m5nu1`, and
`storage-regression/public-1541-jf_jlexv`. Earlier `build/sprite-basic/`
experiments are superseded, not the release qualification. Reproduce with
`make xsprdef-files-probe` and the native command in [XSPRDEF](docs/XSPRDEF.md).

Work remains uncommitted on `graphics-xspr-pixel-update`; no commit/push/merge
was requested. Root main's unrelated edits, sibling 1986 source and original
disk images are untouched. Next: user tests E export and BASIC BLOAD on a
disposable fresh image, then branch review when requested. Preserve the
earlier wave-resize timing caveat; this is not a complete WM performance
qualification. Return to the roadmap's disk-loaded service milestone after
acceptance rather than expanding sprite scope.

## Earlier handoff — sprite Save/Load integration, 2026-10-07

The user accepted the generic capacity increment (platform unspecified) and
asked to continue. Integrated the previously requested S confirmation, L Load
and `SPRITES.SPR` in the production editor on `graphics-xspr-pixel-update`.
No commit/push/merge requested. Root main's unrelated changes, sibling 1986
source and original disk images are untouched.

Click S/L, then Y/N. B now keeps the current edit in the session bank before
returning to the list, which also has S/L buttons. These are mouse controls,
not keyboard shortcuts. The file is exactly 504 raw bytes: eight 63-byte,
MSB-first sprites, no header. Save includes the current edit; Load stages in
the private command-buffer union and commits only after exact length, EOF and
successful CLOSE. No presentation uses that union during I/O. Errors display
read-only, missing file, existing file, bad size, busy, full or generic error.

Saving remains **create-exclusive**, explicitly announced before work. No
overwrite, delete, automatic RW remount or retry. Failed writes may leave a
partial file; duplicate save returns EEXIST. Boot mounts remain read-only.
The reusable `user/include/udeks/native_file.h` / assembly helper uses the
existing UTRQ 0.14 FF16 path and preserves descriptor/count, unlike the graphics
helper. Native clients must not import the transient CF30 file helper.

Production image: **5,367 file / 5,284 image+BSS bytes**, joined task 3/4;
two compatible-sized peers remain possible. Disk-packager validation now
accepts joined-capacity images too (the earlier capacity fixtures bypassed
this normal-image check); exact limits and overflow rejection are host-tested.
No extra kernel service or ABI version. Fast pixel deltas remain intact.

Qualification: **1,353 host tests**, boot D64/D71/D81, graphics-apps-check and
placement-check pass. Host tests include short reads, malformed lengths,
partial/failed writes, transfer/CLOSE errors and unchanged state on failed
Load. VICE 1541, 1571 and 1581 pass Save/Load, Y/N cancellation, RO/ENOENT/EEXIST,
console, uncover, guards and cold reboot. Independent DOS decoding confirms
exact 504-byte contents and every pre-existing file unchanged. Native 1986
`19386ef8` D64/1571 passes the same mouse-dialog/reboot path with actual
keyboard/1351 input; no app/event/request injection. The VICE pixel probe
passes exact dense two-region updates, move/uncover and three-app coexistence.
The final native pixel regression also passes: ten real 1351 on/off edits,
13–15 PAL frames each including release, with zero full compositions, followed
by console input and close (`build/sprite-files/1986-pixel`).

Reproduction: `make xsprdef-files-probe` (host VICE), and container
`tools/1986_storage_smoke_build.py --xsprdef-files` as shown in
[XSPRDEF](docs/XSPRDEF.md). Fresh copies and result JSON/hashes live under
`build/sprite-files/`: `files-1541-r21lp63g`, `files-1571-x3u24snw`,
`files-1581-oktgsy01`, `1986-d64/sprite-q9f7lda0`, `pixel-d64-r1`.
These are local development artifacts, not published release downloads.
Final rebuilt D64/D71/D81 hashes match the corresponding qualified probe
inputs; the repeated full check remains green. Probe emulator processes exited.

Next: user tests a fresh disposable worktree image, explicitly remounting RW
for Save, then cold-boots and Loads. Physical C128 acceptance is not claimed.
Review/commit this accumulated branch only when requested. The earlier
four-native wave-resize timing caveat below remains separate; do not claim a
complete WM performance regression pass. After acceptance, return to the
roadmap's first disk-loaded service rather than expanding sprite scope.

## Earlier handoff — generic larger-app capacity, 2026-10-07

The user chose generic capacity first, before integrating the sprite file UI.
Work remains on `graphics-xspr-pixel-update`, preserving the accepted pixel
fix and isolated Save/Load prototype. No commit/push/merge requested; root
main's unrelated edits and sibling 1986 sources remain untouched.

The loader may tentatively join native task 3/4 memory (`$2300-$3FFF`) only
when both are FREE and unowned. Ceiling: **7,168 image+BSS / 7,424 file bytes**.
Private ownership value 3 reserves the donor without creating a task. Its
load/activate/release/reap calls return EBUSY; query still reports its actual
FREE lifecycle state. Failed loads undo the loan. Successful small installed
images give it back even if the relocation tail needed extra staging space.
Otherwise release/reap returns it. Activation publishes the effective stack
page to bank-0 source validation and cc65 setup before RUNNABLE. No new ABI,
app names, task slots or runtime reservations. Four small apps still work;
a larger one plus two compatible peers works. Existing live apps never move.

Measured loader CODE: `$D900-$DFE6`, 1,767/1,792 bytes (+109); page initializer
adds three bytes to MODULECODE. Resident BSS unchanged (`$96A3`). The layout
gate checks joined and ordinary alternatives, keeping the idle donor CPU
pages reserved. The independent SDK rejects both runtime and file overflow.
The normal argc/argv synchronous console pool is unchanged; the larger
allocation also works for separately scheduled native windowless clients.

`make check`: 1,347 tests; container boot, graphics-apps-check (including
1,028 real-cc65 rectangle cases) and placement-check pass. VICE 1541/D64,
1571/D71 and 1581/D81 pass public large graphical/console clients, capacity
rejection, four-small reuse and normal exit. D81 additionally tests exact
7,168-byte image/BSS and 7,424-byte file edges, one-byte overflow, malformed
relocations, failed open, unowned/owned donor rejection and request preservation.
Probes read physical bank 1 using verified VICE `bank ram01`, not the aliased
CPU view (the first probe version exposed that sampling mistake).

Independent fixtures: LARGE is 5,467 file / 5,343 image+BSS bytes; BIGCON is
402 file / 4,950 image+BSS bytes. Neither fits an ordinary allocation. LARGE
submits drawing data beyond `$3500` and checks rejection at the new stack
boundary. Native 1986 `19386ef8` D64/1571 passes real keyboard/1351 drags,
guards, three-client capacity, reuse, ordinary four-client coexistence,
windowless natural return and graphical Ctrl+C. No new physical-HW result.
Results/reproduction: `tools/native_capacity_probe.py`,
`tools/1986_native_capacity_smoke.inc`, `build/native-capacity/vice-*` and
`build/native-capacity/1986-d64-final`; see the SDK for the manual sequence.

Important existing limit: closing is cooperative, not forced cancellation.
An infinite windowless fixture that only slept kept running after Ctrl+C;
the console capacity fixture now performs bounded work and returns normally.
Do not claim that general native console cancellation/stdin/argv was added.
Next: user capacity test, then integrate and qualify S/L and `SPRITES.SPR`.
Create-exclusive versus overwrite remains a separate storage/UI decision.

## Earlier handoff — sprite files need a capacity decision, 2026-10-07

The user reports the pixel-update build works well (platform unspecified),
then requests an explicit S Save confirmation, an L Load control and default
filename `SPRITES.SPR`. The first Save/Load prototype is preserved under
[`experiments/xsprdef-files`](experiments/xsprdef-files/README.md), **not shipped**.
Measured after app-local C compaction: **5,373 file bytes / 5,290 image+BSS**,
against the largest native slot's **4,608 / 4,352** ceilings. The accepted
editor and production build rules are restored; all three disk hashes remain
identical to the pixel candidate below. All 1,342 tests, boot, placement and
graphics-app checks still pass. No app limits or kernel policy were changed.

Ask before expanding scope: generic larger-app capacity vs a dedicated compact
implementation; create-exclusive Save/Load first vs adding overwrite support.
The latter question was also sent asynchronously. The prototype proposes one
504-byte raw bank (eight 63-byte sprites), failure-atomic load via private
staging, and B keeping session edits so a full bank can be built before saving.
These choices are not frozen APIs; the prototype is compile-measured only.
No commit/push/merge requested. Root main and unrelated worktrees untouched.

## Earlier handoff — sprite pixel-click fix, 2026-10-07

At the user's request, resumed the sprite editor before its disk-persistence
work. Branch `graphics-xspr-pixel-update`, worktree
`build/graphics-xspr-pixel-update`, starts from merged Storage 0.3 (`ea25eff`).
Root main's unrelated documentation edits and written storage-test media are
untouched. No commit/push/merge was requested for this increment.

UTRQ 0.15 GRAPHICS `PRESENT_DELTA` accepts a full retained command list plus
two clipped fills. Topmost pixel edits update the 8×8 cell and 1× preview;
background updates use the compositor. Drag/cache activity returns EAGAIN
before mutation; the editor yields/retries without toggling twice. Clear,
Invert, selection, move and uncover retain their complete-scene path. This is
a generic service operation, not app-name routing or a BASIC ROM call.

The existing assembly span writer was already efficient; full-window replay
dominated the delay. A compact assembly rectangle wrapper, serialized private
display scratch and shared geometry marshalling fund the change without
moving reservations. The editor's exact 46-command private buffer keeps
image+BSS at 3,835 bytes, fitting task 5 as well as task 3; this preserves
coexistence with clock, calculator and drawing. Resident BSS ends at `$96A3`
(four bytes before fixed VDC assets), GRAPHICSCODE at `$12F9` (six bytes free).
Keep the existing link/layout gates: both budgets are tight.

VICE D64: ten dense on/off clicks change exactly the intended two regions,
no full compositions, shadow equals VIC; aligned/unaligned drag, retained
replay, session save/discard, four apps, console and close/uncover pass.
Verified `warp off`: median click-to-verified-bitmap wall time is 0.154 s vs
3.014 s on the merged baseline (ten clicks each). This includes monitor and
polling overhead; it is not isolated CPU timing or real-hardware latency.
Results are under `build/xsprdef-delta/normal-{d64,baseline-d64}` within the
worktree. Earlier timing attempts left warp on (obsolete resource name) and
are not performance evidence. Earlier submission timeouts were probe errors:
plain monitor reads saw KERNAL ROM over `$F3D8` (opcode `$E0`), but captured
console/RAM proves the command completed (actual counter `$0A`). All status
reads now use the kernel profile. Fresh D71/D81 editor sequences pass too.
Native 1986 `--xsprdef` passes ten exact edits with real keyboard/1351 APIs,
no state injection, at 13–16 PAL frames including input/release; console and
close pass. Results: `build/xsprdef-delta/1986-sprite-r1`.

Verification: 1,342 host tests; all three images; placement and graphics-app
layout checks; 1,028 sim65 rectangle argument/stack checks pass.
**Do not claim every regression gate is green:** the separate 1986 four-native
wave timing gate fails in the candidate's four-app resize: projection 450 PAL
frames (limit 400), total 811 (limit 700), input-poll gap 216. The unchanged
baseline passes at 233/595, gap 7. Diagnostic run shows the candidate crosses
5:59 -> 6:00 during projection, gains a full composition, and pauses for the
clock minute repaint. Identical app binaries and unchanged wave code; scheduling
phase is a likely confound, not proof of equivalent worst-case timing. Baseline
minute-edge-delay experiments did not reproduce it (the drag itself passed the
minute edge); their optional timing hook was removed. Do not relax the limits
or mark this as qualified. Preserve logs in `build/xsprdef-delta/1986-four-native`
and `1986-four-native-diagnostic`; baseline default results are in the storage
worktree's `build/xsprdef-delta-baseline/1986-four-native`. Review before merge;
do not roll a wave/WM scheduling fix into the editor pixel patch silently.

See [XSPRDEF.md](docs/XSPRDEF.md) for tests and image paths. Next: user checks
pixel-click response on 1986/C128, then define sprite persistence/export using
the merged create-only file API. Do not expand this fix into wave/whole-WM
optimization. The first disk-loaded non-kernel service remains the next
architectural milestone, after this explicitly requested editor work.

## Earlier handoff — Storage 0.3 accepted for merge, 2026-10-07

Step 3 was committed/pushed as `451fdcf`. The follow-up below closes the
VICE-blocked 1581 coverage gap under sibling 1986; the user explicitly approved
merging [PR #45](https://github.com/salvogendut/UDEKS/pull/45). This checkpoint
includes the probe/docs/evidence; production UDEKS images and sibling emulator
source remain unchanged. Preserve the written local D81 and root main's
unrelated edits. Earlier handoffs below are historical, not current blockers.

`1986_storage_smoke_build.py --storage-eject --drive 1581` uses two ROM-backed
1581s, system on unit 8 and generated data on 9. The existing WHOLD fixture
writes 24 bytes, yields with its file open, then the normal UI media API ejects
unit 9 without disconnecting/resetting it. Subsequent WRITE/CLOSE both return
EIO, zero new bytes accepted, owner generation advances 1 -> 2, cleanup zero.
Console CAT works; reinsertion, new SAVE, same native-slot reuse, EXIT cleanup
and fresh-process readback all pass. Only client control flags are poked.

Evidence: `bench/results/2026-10-07-storage-eject-1986`, emulator revision
`19386ef`, tracked tree clean. Host audit preserves KEEP and system media;
RECOVER/OWNER4 contain exact bytes 0..23. Aborted OWNER2 has no entry (allowed).
Both emulator phases succeeded; the first postprocessor incorrectly demanded
OWNER2 exist. The corrected independent collector re-audits the same logs and
media; original postprocessing failure is preserved, with a regression test.
No runtime or emulator fix was needed. ROM snapshots are not archived.
Final host validation passes **1,337 tests**, including archived media decoding,
hash verification and re-collection of the ejection report; diff checks pass.

**Next roadmap feature:** the first disk-loaded non-kernel service; define its
load/start/stop and dependency contract before extracting it. Further storage
operations and sprite-editor integration remain separate work.
The UDEKS 1581 ejection/recovery coverage gap is closed under 1986; VICE's process
loss is still undiagnosed and its historical test remains failed. No new
physical 1581 fault-injection claim or general power-loss guarantee. Earlier
C128/PI1541 functional acceptance remains valid; PR #45 records merge status.

## Earlier handoff — storage physical functional acceptance, 2026-10-07

Step 2 was committed and pushed as **5fb989b** on `storage-0.3-disk-write` (#44).
Step-3 changes in `build/storage-disk-write` are being committed and pushed for
PR review at the user's request. Root main's unrelated edits/worktrees remain
untouched. Merge itself is not authorized by this preparation request.

The user confirmed all manual checklist tests in 1986, then reported **all
tests passed on REAL C128 with Pi1541**. This covers binary/empty creation,
duplicate rejection, clock dragging, RESTORE and console input, RO remount,
cold-boot readback and RO boot defaults. The supplied D64 candidate is the
archived `1e29e08f…`; no independent tested-media checksum/dump was supplied.
Record this as physical functional acceptance, not as physical fault injection
or a resolution of the VICE 1581 mid-write-ejection gap.

- `storage-failure-fixtures` builds WLEAK (foreground return), WHOLD (native
  EXIT/reuse), and PARENT/CHILD (real CANCEL/WAITPID, foreign CLOSE). Independent
  public clients only; test clients are never shipped on normal disks. The
  disposable fixture disk adds CHILD to recovery bootfs because legacy SPAWN
  still resolves there. `name -q` is an advisory GRAPHICS event, not generic
  lifecycle cancellation; the pure writer fixture does not poll graphics.
- `tools/storage_failure_probe.py` uses drive 8 for copied system media and
  drive 9 for generated data disks. Full media uses real allocated file chains,
  not fabricated BAM counts. VICE 1541/1571 pass protection, absent unit, full/
  partial-full writes, return/EXIT/CANCEL cleanup, mid-write eject, disconnected
  CLOSE, recovery and a background-clock save. Independent decoding proves
  preexisting file contents unchanged and exact successful new files.
- Full-disk OPEN returned DOS 67 on VICE. Production fix: free-block preflight
  after the complete collision scan, before create. Known full -> ENOSPC;
  malformed geometry/transport errors are not relabeled. EEXIST precedence
  stays intact. +40 bank-1 policy bytes, 54 remain; no BSS/allocation changes.
- VICE 1581 mid-write `detach 9` repeatedly loses the emulator process. Failed
  transcript retained. `--skip-media-removal` explicitly records that gap and
  all remaining D81 cases pass, including CLOSE after actual drive disconnect.
  Resource commands must quote both strings and verify readback. Runtime
  write-protect toggling also isn't reliable; RO/RW phases use fresh processes.
- `1986_storage_smoke_build.py --storage-write` uses unmodified sibling 1986
  revision `19386ef`, real keyboard/1351 input and device-register NMI stress.
  Fresh D64/1571 and D81/1581 runs both pass exact binary/empty saves, duplicate
  rejection, RESTORE, CIA2 NMI during SAVE, clock drag and post-boot readback.
- Exact candidates, fixtures, failed VICE transcript and passing results live
  in `bench/{artifacts,results}/2026-10-07-storage-acceptance`; tests verify hashes
  and decode preserved media. ROM-bearing snapshots stay out of the archive.
  Final verification: **1,332 host tests**; container boot, placement-check and
  graphics-apps-check pass. No VICE processes remain. Fresh normal disk SHA-256:
  D64 `1e29e08f…`, D71 `80b74654…`, D81 `89c6cad9…`.

Pre-merge validation found the local `build/boot/udeks.d81` contains WRTEST,
EMPTY and LIVE from testing, with original files unchanged. Preserve that
written image. A separately generated `build/storage/pre-merge-udeks.d81`
matches the pristine archived candidate; D64/D71 build outputs match too.

**Next:** review the step-3 commit and PR. Keep the unqualified 1581
mid-write-ejection gate explicit before
milestone completion/merge; the requested C128/PI1541 checklist no longer needs
repeating for this candidate. No append/delete/redirection,
multi-open, rollback or automatic RW boot. On errors, partial/splat files are
expected and must not be silently retried. Do not start another feature here.

## Earlier handoff — public disk writes, step 2 complete, 2026-10-07

User requested commit/push, then step 2 of three. Step 1/private lease committed
and pushed as **160c591** on `storage-0.3-disk-write` (#44). Step-2 changes are
in the same `build/storage-disk-write` worktree, **uncommitted**. Preserve root
main's unrelated roadmap/console-plan edits and other active worktrees.

- Public UTRQ minor 14; request gate routes non-console WRITE to `$C880`.
  Existing operations/gates and native/foreground owner-generation mechanism
  unchanged. Request gateway fits exactly 265/265 bytes; no allocation growth.
- Disk-only `mount_rw.c` + request assembly expose explicit RW/remount flags.
  Original mount.c remains the small RO recovery program under a separate
  `mount-recovery.udx` build target. Normal boot/remount defaults stay RO.
- Transient file SDK supplies OPEN/READ/counted WRITE/CLOSE plus optional
  metadata/error-string archive members. It calls CF30, never native FF16.
  `--filesystem` enables this in the independent console builder; optional
  `--static-locals` is for nonrecursive programs. No kernel imports.
- SAVE.BIN is disk-loaded, create-only, byte-pattern/readback/check-only, with
  checked CLOSE and no short-write retries. Default 515 bytes, range 0–4096.
  It fits the unchanged $0200–$0BFF console allocation; df uses STATFS flags.
- `tools/storage_public_probe.py` makes fresh disposable disk copies, enters
  commands through the keyboard queue, and reboots each written disk in a
  new emulator process. True 1541/D64, 1571/D71 and 1581/D81 pass. Exact normal
  and written images, binaries, maps and command records are in
  `bench/{artifacts,results}/2026-10-07-storage-public`. Host tests decode all
  existing/new files independently and verify hashes; earlier archives unchanged.
- Current owner fixture's future-version rejection moves from minor 14 to 15.
  The archived step-1 LEAK binary/evidence intentionally still tests old 14.
- Final verification: 1,324 host tests pass; container boot/user-programs,
  placement-check and graphics-apps-check pass. Rebuilt disks are byte-identical
  to the archived candidates. No VICE processes were left running.

Next is **step 3**, not another API increment: qualify public write failures,
real write-owner cleanup, RESTORE, native 1986 and disposable physical hardware,
then PR/merge. Current live proof covers successful public writes and reboot,
not those failure/platform gates. User instructions:
`mount -o remount,rw 8 /`, `save /WRTEST 515`, `save /EMPTY 0`, repeated create
must fail, `mount -o remount,ro 8 /`; reboot then `save -c /WRTEST 515` and
`save -c /EMPTY 0`. Use fresh build/boot images; old download snapshots lack SAVE.

## Earlier handoff — boot storage ownership, step 1 complete, 2026-10-07

User requested **step 1 of three**, not public writes or another application.
Implemented in `build/storage-disk-write`, branch `storage-0.3-disk-write`
(#44). HEAD remains `5a43574`; this and the preceding private-lease increment
are uncommitted. Preserve unrelated root-main edits/worktrees.

- Normal boot now installs UIEC 0.3, including hidden bank-1 code/constants.
  The one-shot `$3200` installer consumes `$2300–$31FF` source bytes before
  the stage-1 Z80 container copy, then initializes the NMI mirror/state.
  Test A explicitly after initialization: that entry preserves P.
- Permanent common transport is `$FE20–$FE51`; loader ends `$FE11` and has a
  link assertion against `$FE20`. Storage no longer overwrites `$F68A` or the
  transient C stack. Filesystem policy remains a bank-1 C service.
- Bank-0 router `$C880` derives tags from the real current-task binding;
  native tags 1–8, synchronous invocation 9, bootstrap/root loader 10.
  Private bank-1 generations form a 16-bit instance ID. `$C883` retirement
  preserves registers/status/request, closes/releases before incrementing,
  and records cleanup errno without replacing the program's exit status.
  Native EXIT/CANCEL and synchronous return call it before memory reuse.
- Actual remaining bytes: module 15, policy 94, driver 163, hidden 2, BSS 0.
  Keep the `$E180–$E1FF` C stack and all four app allocations intact.
- Public UTRQ stays **0.13**; mounts remain RO. Independent clients prove a
  0.14 request and create-mode request are rejected. Do not claim users can
  save files yet.

`storage-owner-fixtures` builds independent console/native test clients.
`tools/storage_owner_probe.py` qualifies leaked foreground return, native
EXIT, parent CANCEL/WAITPID, foreign CLOSE rejection and slot reuse through
the real gates. All VICE 1541/1571/1581 cases pass. Bootfs recovery passes;
the full four-native-client suite passes on 1571 (drag/resize, worker,
disk commands, close/reload, unknown names and rejected loads).
Evidence: `bench/{artifacts,results}/2026-10-07-storage-ownership`.
Final gates: **1,302 host tests**, `make boot`, `placement-check` and
`graphics-apps-check` pass; rebuilt disks match the preserved hashes.
No new physical C128/1986 or integrated RESTORE result is claimed.

Fixture lessons: legacy native SPAWN still resolves bootfs, so the probe
adds its tiny child to bootfs on a disposable image, keeping recovery entries.
SPAWN returns result=1, child ID in payload, not result=task ID. cc65 `-Os`
can retain a stale ptr1 after an indexed clear loop; the parent fixture uses
`memset` before rebuilding the next payload. No runtime kernel test hooks.

**Next: step 2**, public version/routing + explicit RW mount/remount + SDK +
independent save/readback command. Step 3 is end-to-end failure qualification,
1986/C128 acceptance and merge. Follow [the roadmap](docs/ROADMAP.md), not the
older “boot delivery still due” notes below.

## Previous handoff — actual guarded storage service, 2026-10-07

User requested commit/push and next step. Placement proof committed/pushed as
`5a43574` on `storage-0.3-disk-write` (#44). The following service-entry increment
is implemented in the worktree, not committed yet. Use
`build/storage-disk-write`; preserve unrelated root-main edits/worktrees.

`src/services/filesystem/iec_lease.s` + the private lease linker target run the
actual C policy/writer, with low request/cwd/boot snapshots, trusted AX caller
identity, a banked cleanup entry and deferred NMI forwarding after restoring
common. Initialization clears state and installs the hidden NMI mirror once;
boot must install the hidden image first, before CIA2/input ownership. Actual
free bytes: module 21, policy 141, driver 175, hidden 2, state **0**. Do not
spend the `$E180–$E1FF` stack or another app's allocation.

`make storage-lease-probe` and `tools/storage_lease_probe.py` exercise these
exact binaries on newly generated disposable media. All three true-drive VICE
formats pass, both VIC-bank settings: 27 requests, 3 cleanup calls, binary
readback, exact-empty finalization, ownership and RO rejection, snapshot/cwd,
stack/common preservation, hidden NMI forwarding. A one-instruction negative
control detects missing forwarding before any write. Preserved evidence:
`bench/{artifacts,results}/2026-10-07-storage-lease`. Production disk/storage
hashes are unchanged; **1,291 host tests** and container boot/placement/graphics
gates pass. All probe-owned VICE sessions are terminated.

**Next concrete work:** install the new service and hidden image in the real
boot delivery, then supply per-invocation identity and cleanup on scheduler
exit/cancel and foreground-loader return. Keep the public UTRQ minor at 0.13
until the complete path is qualified. Add the versioned mount/SDK route and
independent console save/readback fixture as the next user-testable feature.
This standalone service probe is VICE-only and uses bank-0 CPU pages; it does
not demonstrate live scheduler cleanup, 1986, physical hardware or integrated
RESTORE recovery. See [Storage 0.3](docs/STORAGE-0.3.md#actual-guarded-service-entry--2026-10-07).

## Previous handoff — storage placement candidate, 2026-10-07

The exact-empty backend (`5e0aa88`) and gated service policy (`c674c97`) are
committed/pushed. This placement checkpoint measures the complete
write-enabled service in `cfg/8502-storage-write-candidate.cfg` and qualifies
a separate guarded-RAM-window proof. Normal boot images and the public ABI
remain unchanged; do not install the link-candidate blobs as a live service.

The candidate adds physical bank-1 `$F000–$FEFF`, exposed only while upper
common is disabled in a synchronous IRQ-masked lease; `$FF00–$FFFF` is reserved
for MMU mirrors and NMI handling. Actual linked free bytes: module 12, policy
94, driver 346, state 42, hidden 2. Entry/snapshot/cleanup code must fit the
remaining low-memory space; no app slot, recovery, cache or stack is borrowed.
`make storage-window` builds the candidate and standalone ASM proof. Both VICE
and 1986 pass both VIC-bank settings, 128 rounds / 384 NMIs each, including
128 boundary-window arrivals, common-byte preservation and a failing negative
control. Evidence is in `bench/{artifacts,results}/2026-10-07-storage-window`.
Full suite **1,283 tests**, container boot and placement/graphics gates pass.
Production storage blobs/D64/D71/D81 hashes are unchanged; no VICE remains.

The private `udeks_storage_caller()` provider is **not implemented**; the
cleanup function is **not called by real task exit/cancel or loader return**
yet. No public ABI bump, console save command or write-enabled image is
claimed. Next implement the bounded low-memory lease entry and private
request/cwd/boot/caller snapshots, plus one-time boot delivery/mirror install
before input starts. Hidden NMI pending MUST live below `$F000`; restore common
before forwarding it to `$FFF5` to avoid the return-boundary race. Qualify the
actual C service, stack/CPU-page context and RESTORE path before enabling
public routing. The proof does not run the filesystem/scheduler/Z80 or qualify
physical hardware/cartridge NMI. See [Storage 0.3](docs/STORAGE-0.3.md#placement-candidate--guarded-top-ram-window-2026-10-07)
for scope, measurements and remaining gates.

## Exact-empty backend checkpoint — 2026-10-07

The user selected disk writes as the next feature and requested an issue and
branch. [Issue #44](https://github.com/salvogendut/UDEKS/issues/44) tracks
`storage-0.3-disk-write`, based on merged main `ba0ba97`; use the dedicated
`build/storage-disk-write` worktree. Root main's unrelated console-plan edits
and the earlier sprite-editor experiment remain untouched.

Implementation has begun in an isolated backend and standalone drive probe;
see [Storage 0.3](docs/STORAGE-0.3.md) for code, reproduction and the remaining
public-API gates. The production filesystem still has one serialized
IEC stream, read-only open/read/close and no file-data WRITE dispatch; stdout/
stderr WRITE is not a disk-write API. The new C writer and optional IEC output
path are not linked into boot images. The current storage reservations have
only 327 free code bytes; the writer, transport and new empty-file finalizer
add 2,118 code/data bytes before service policy and compiler helpers. Keep the
working boot layout intact; don't spend app slots or stack/recovery space.
Implement the proposed versioned contract, permissions and owner cleanup
in the C storage service, with no overwriting of existing files. Prefer DOS
file channels; explicitly settle mount permissions, ownership, error/partial-
file semantics and cleanup before implementation. Keep all tests on disposable
image copies. Exact empty-file creation is now implemented: after a successful
zero-data CREATE/CLOSE, validate the fresh one-block closed SEQ and correct
only its sector count through standard B-P/U2. No allocator, directory/BAM
rewrite, ROM patch or reader special case. Failed operations and non-empty
writes never enter this correction. Follow the [current roadmap](docs/ROADMAP.md#active-storage-03--create-only-disk-writes-44).

Service extraction follows this write milestone. Sprite persistence, general
shell redirection, multi-open, overwrite/append and rendering work are not
prerequisites and remain deferred. No public-API, 1986 or physical-machine
disk-write qualification is claimed yet.

Initial checkpoint `ad01c45` is committed/pushed, with **1,196 host tests**, reference-container boot and
placement/graphics gates, and isolated VICE 1541/D64, 1571/D71, 1581/D81 runs.
Each drive passed non-empty binary readback, restart persistence, duplicate
rejection and write protection; exact empty files were then unsupported. Normal
boot images are byte-identical to the pre-change baseline. Probe artifacts and
results are preserved under `bench/{artifacts,results}/2026-10-07-iec-write`.
The new follow-up passes the same three VICE drives with twelve exact files
(empty, binary boundaries and an ordinary CR), reboot persistence, write
protection and 16-byte empty filenames. Exact probe/results are preserved in
`bench/{artifacts,results}/2026-10-07-iec-write-r1`; do not replace the first
diagnostic evidence. The host finalizer tests prove a one-byte-only change and
fail-closed handling of malformed targets/transfers. Public writes are still
disabled. Placement, mount permissions, task ownership and cancellation/media
failure qualification remain the next service-integration work. This follow-up
is the exact-empty backend checkpoint. Final checks: **1,215 host tests**, container boot,
placement/graphics checks; normal D64/D71/D81 and storage blobs still match
the pre-change hashes. All private VICE sessions exited.

## Sprite-editor checkpoint — accepted and parked, 2026-10-07

The user accepted the reviewed editor, authorized commit/push/PR/merge, and
asked to put further sprite-editor work aside. The review supersedes the early
experiment (#41 / PR #42). Work is isolated on `graphics-xspr-review`, based on `8ef5c25`, leaving
`build/graphics-xspr` and its uncommitted partial-repaint work unchanged. Root
main's unrelated console-plan documents are also untouched.

See [XSPRDEF](docs/XSPRDEF.md) for controls, scope, tests and test images. The
lossy four-run rectangle algorithm is replaced by bounded generic bitmap tiles;
button bounds and confirmation are fixed, with Clear/Invert added. ABI 0.13
means tiles here, **not** the old dirty worktree's experimental damage payload.
Do not blindly merge that draft onto this branch. Saving is still session-only.
Further editor work is parked: persistence/export, thumbnails, richer input,
multicolor and partial repaint are not the next task. This accepted checkpoint
does not replace the roadmap's loadable-service milestone. The user's latest
manual-test platform was not specified; do not infer hardware qualification.

Review gates: 1,176 host tests; container placement/graphics gates; VICE editor
checks on D64/1541, D71/1571 and D81/1581; existing four-native-app D64 probe.
All pass. Fresh test media are under this worktree's `build/boot/`; no published
images were overwritten and no 1986/physical-machine qualification is claimed.

## Previous handoff — user acceptance, 2026-10-05

The user accepted the resize improvement and explicitly requested commit,
push, PR and merge. [PR #37](https://github.com/salvogendut/UDEKS/pull/37)
delivers the four-native-slot follow-up to #35/PR #36, including the app-local
resize correction. The latest manual-test platform was not specified: do not
turn that acceptance into a new physical-C128 qualification claim.

Current verification: **1,162 host tests**, D64/D71/D81 builds, both placement
checks, VICE on all three formats and unmodified 1986 native keyboard/1351
input. Preserve both dated evidence sets below. README downloads now point to
the exact `2026-10-05-wave-resize` test artifacts; the older `build/udeks.*`
published snapshots are unchanged.

Next work is the **first disk-loaded non-kernel service**, on its own issue and
branch: choose one service, inventory dependencies and boot/recovery ownership,
then define and implement its bounded load/start/stop contract. Keep missing or
invalid service images recoverable. Do not reopen app-name routing or add
preemption, filesystem writes, scripting or xwave optimization as prerequisites.
Dense repaint remains synchronous and slow; native background-console
arguments/stdin and larger task allocations remain separate work.

## Four-native-slot cutover — 2026-10-05

Implemented on `graphics-native-clients`: **all four shipped graphical apps are
ordinary relocatable disk programs**, with no app-name routing in ush, the
resident session, loader or running panel. `name &` picks the smallest FREE
compatible allocation; `name` owns the foreground and Ctrl+C closes only that
instance. `name -q` cooperatively stops the first matching live instance.
Repeated names are permitted. The retired named CONTROL app operations now
return ENOSYS; the old managed loader entry rejects flag-2 loads.

| Task | Bank-1 allocation | Image + BSS maximum | ZP / hardware-stack pages |
| --- | --- | ---: | --- |
| 3 | $2300–$34FF | 4,352 bytes | $D5 / $D6 |
| 4 | $3500–$3FFF | 2,560 bytes | $D7 / $D8 |
| 5 | $8000–$8FFF | 3,840 bytes | $D0 / $E2 |
| 6 | $C600–$CFFF | 2,304 bytes | $00 / $01 |

Admission order is 6, 4, 5, 3, based only on capacity. The complete file,
including relocation metadata, must fit the allocation. Its final page is
reserved after installation: 16-byte lower guard, **160-byte private C stack**,
16-byte upper guard and private exit trampoline. Image+BSS and graphics source
pointers may not enter that page. Stack depth is a real SDK limit, not hardware
protection. All four contexts use the accepted scheduler and frozen gates;
the MMU initializer preserves the 8502 port at $00/$01.

Removing the legacy callbacks frees the bank-1 foreground backup and old
external C stacks. Both graphical service modules are copied out of bank-1
$C600–$D0EF before *any* native client is admitted; their installed flag is
never reset. Only then may task 6 and task 5's zero page reuse that delivery
area. The temporary bootstrap context at $E2E2 has already been retired by
scheduler activation before task 5 uses its hardware-stack page. Bank-1
physical pages $00/$01 are otherwise unused after boot; foreground task 2
still starts at $0200 and uses its separate relocated CPU pages.

Retained images now share **2,304 bytes in bank 0 at $1300–$1BFF**, packed in
slot order. Replacement/close compacts the pool; malformed or over-capacity
updates leave all live images unchanged. PRESENT stays at most 384 bytes;
PATHS stays at most 1,280 bytes per image, but four maximum-sized path images
cannot coexist. Pool exhaustion returns ENOMEM. The normal four-app set fits.
The base graphics service occupies $0C00–$12FF; the existing 1,008-byte retired
VDC glyph-source overlay is unchanged. Console commands, recovery bootfs,
filesystem, cache, VIC bitmap and Z80 code retain distinct ownership.

Wave resize now waits for outline release and projects sixteen table-scaled
vertices per cooperative yield. The app caches all 525 heights and retains all 524 edges:
moves/raises replay service data; resize never resubmits the Z80 height job.
Dense geometry repaint is still synchronous, not a new pixel-blit guarantee.

VICE D64/1541, D71/1571 and D81/1581 pass the bundled four apps, calculator
arithmetic, drawing input, clock/time oracle, full wave path/sample oracle,
held-outline/no-duplicate resize, exact worker leases, console use, fifth-app
rejection, shutdown and reload. Four renamed copies of the same independently
built HELLO binary also run simultaneously, each with independent input,
guarded stacks and names; malformed loads preserve peers and freed slots
accept another name. These are injected VICE WM events; native mouse and
physical-C128 confirmation are separate gates. Unmodified 1986 revision
`81485cc7` also passes raw-IEC D64/1571 boot, actual keyboard/1351 drag and
resize, calculator/drawing input, held-outline/worker reuse, independent reload,
foreground Ctrl+C, canvas equality and all four private stack guards.
Physical-C128 confirmation remains due. Test the fresh
`build/boot/udeks.d64`, `.d71` or `.d81`; published `build/udeks.*` snapshots
remain unchanged. Reproduce with `make four-native-probe` after the container
build and `make graphical-example`.

Original cutover qualification: 1,158 host tests; actual-map placement gates;
byte-identical isolated parallel build; VICE all three formats and 1986 native
input. Preserved evidence: `bench/{artifacts,results}/2026-10-05-four-native`.
The current acceptance and next milestone are recorded in the handoff above.
No new physical test or published-snapshot refresh is implied.

Resize follow-up: the user noticed updates apparently depending on later focus
changes. No-input native-mouse tests instead measured excessive projection and
paint latency: 755/1,399 PAL frames with two/four clients. App-local exact scale
tables and 16-vertex slices reduce that to 418/594 frames, with the same paths
and no additional worker leases. The dense synchronous repaint remains slow;
do not describe this as instantaneous or as a window-manager event fix.
The expanded probes test four-client resize without subsequent input and check
actual visible wave pixels. See the [follow-up](docs/GENERIC-GRAPHICS-APPS.md#resize-latency-follow-up--2026-10-05)
and `bench/{artifacts,results}/2026-10-05-wave-resize`; old evidence is unchanged.

## Previous feature handover — 2026-10-04

Native-wave checkpoint follows pushed worker commit `885ca87`. UTRQ 0.12
adds generic, owner-checked packed polylines; all 524 legacy grid edges fit
1,128 bytes. Independent NWAVE.BIN uses 21 bounded Z80 row requests per load,
private cached heights, app-owned projection on resize, and no app/worker
recomputation on moves or stacking. File/image/BSS: 2,221/1,741/1,681 bytes;
it fits the larger native allocation. NCLOCK still fits either allocation.

Placement: bank-0 boot glyph source `$96B8-$9AA7` retires after upload to VDC;
only those 1,008 bytes are overlaid, never the live header/maps. The extension
emits **separate PATHSTATE and GRAPHICSPATHS segments** (60+938 bytes). Using
the same segment for cc65 static locals/code made entry labels point at data;
the VICE clock regression exposed this and the corrected link/entry gates
reject it. Base service remains `$0C00-$11FF` (1,535 bytes), BSS ends `$9693`
(20 spare bytes). Bank-1 `$C600-$CFFF` first delivers both modules, then becomes
two 1,280-byte retained images; never reinstall after close/shutdown. Storage
ends `$C50C`, bounded below `$C600`. Task allocations/CPU pages/stacks unchanged.

VICE D64/D81 wave proofs: full path/sample/code oracles, move/resize/stacking,
exact worker leases, real VDC glyph and live asset metadata preservation,
stepped console-reentry guard, clock coexistence, four apps, cleanup/reload.
D71 full clock/resize/Ctrl+C regression passes. Fresh parallel source copy
reproduces all three disks, both modules and both candidate apps. Probe prompt
fences must read bank-0 task state and require WAITING **on READ**, not just
WAITING (a command-completion POLL is not ready for typing). Test copies are
`build/native-clients/native-wave-demo.{d64,d71,d81}`; details/evidence in
`docs/GENERIC-GRAPHICS-APPS.md` and `bench/{artifacts,results}/2026-10-04-native-wave`.

**Next:** measure/implement four compatible native allocations, then switch
the default apps and remove named compatibility routing. Do not claim four
interchangeable slots yet, replace defaults prematurely, or mix in wave math
or rendering optimization. Retained paths replay geometry, not cached pixels;
repaint latency remains open. New 1986/physical-hardware confirmation is due.
Published `build/udeks.*` snapshots are unchanged.

### Previous worker checkpoint

Resize checkpoint committed/pushed as `378c033`. Following it, UTRQ 0.11
WORKER (op 24) now lets an ordinary native program use the bounded Z80 without
UAPP or graphical initialization. Result bytes are read-only borrowed common
RAM at $F300, copied privately BEFORE any request/yield. Four-byte inputs,
three-byte reply; per-kernel operand checks remain in the worker. No app-slot
or common-gate placement changed. Worker-service code is compiled for size
with private static locals (serialized, no IRQ entry); boot status uses a
constant image and a tiny assembly counter transport replaces pointer-heavy C.
The new handler remains C. Resident BSS ends $9AF7 (eight bytes spare).

`make native-worker-probe-app` and `tools/native_worker_probe.py` exercise
the real task API with two independently relocated console clients: all 525
surface samples, the quantized 64-sample waveform, bounded errors, preserved
request sequences, exact lease counts, private copies surviving legacy xwave,
reap/reload, console input and stack guards. VICE D64/D81 passes; clock resize
and four-window compatibility passes on VICE D71. The native worker API has
not yet been separately tested on 1986 or physical hardware. Default clock/wave
remain legacy; next is generic retained paths, NOT math tuning or removal of
working four-app support. Evidence: `bench/{artifacts,results}/2026-10-04-native-worker`.

Resize checkpoint: prior native-clock/panel/D81 work committed and pushed as
`9f2e994`. User authorizes the resize work AND subsequent native-wave/four-slot
cutover sequence on this branch. UTRQ 0.10 is now implemented: explicit sizing
flags and seven-byte EVENT (client-acknowledged dimensions, pending-click
preservation). Version 0.9 remains byte-compatible. Native NCLOCK is 2,770 file /
2,180 image / 369 BSS and fits both allocations. Pure C scaling is app-owned.
Graphics uses an absolute common-record array binding to fit its old segment;
no reservation moves. Foreground native fallback also handles the legacy
staging-size rejection before the native loader's independent validation.

Fresh `build/native-clients/resize-demo.{d64,d71,d81}`: grow/shrink/regrow both
native clocks, date, drag, targeted Ctrl+C, close/reload and legacy coexistence.
VICE three-format drawing oracle and code equality pass; unmodified 1986
D64/1571 and D81/1581 native mouse/input pass. Exact evidence is preserved in
`bench/{artifacts,results}/2026-10-04-native-resize`. Physical resize feedback
remains due. Next: bounded generic retained paths and task-safe worker requests
for native wave, then measured four-native allocations and default cutover.
Do not remove old four-app support or call this entire migration complete.

Panel/D81 follow-up: user reports the native clock works in 1986, but the app
panel repeats each row's first character and D81 does not boot. Fixed the
panel's anonymous backward branch (it jumped into case conversion instead of
loading the next character) with a named loop target; zero code-size growth.
Old image reproduces `RRRRRRRRR`; actual VDC bytes/attributes now pass on VICE
and 1986, including startup, both clocks, cancellation, four apps and shutdown.
1986's saved drive was 1571; explicit ROM-backed 1581 cold boot and native input
pass without sibling source/config changes. See `docs/D81.md` for selection and
restart instructions. Fresh `build/native-clients/native-clock-demo.*` include
the panel fix; default `build/boot/udeks.*` also rebuilt. Prior immutable clock
evidence below predates this fix; its byte-identical-boot claim applies only
to that checkpoint. New evidence: `bench/{artifacts,results}/2026-10-04-app-panel`.
Published root release snapshots remain unchanged. Physical 1581 acceptance
is not claimed, and native-clock feedback does not complete legacy migration.

Latest follow-up: PR #36 merged as `c704250`, then the user selected removing
the clock/wave legacy slots. Branch `graphics-native-clients`, existing issue
#35. Migration plan is in `docs/GENERIC-GRAPHICS-APPS.md`. First runnable gate:
`make native-clock` builds NCLOCK.BIN (2,463 file / 2,039 image / 351 BSS bytes),
an independent UDEX 0.2 client that fits both native allocations. Its retained
clock model stays in user space; no kernel, callback table or memory-map change.
Builder now supports custom filenames and multiple C sources without edits.

VICE D64/D71/D81: both slots, independent retained-command oracle, time changes,
drag, foreground Ctrl+C, reload, console and legacy coexistence. Unmodified
1986 `81485cc7` D64: native keyboard/1351 drag/close, time, Ctrl+C/reuse, four
windows, guards and bitmap equality. Exact artifacts/results:
`bench/{artifacts,results}/2026-10-04-native-clock`. All normal boot images and
HELLO.BIN remain byte-identical to PR #36; independent fresh-output clock build
is deterministic. `make check` passes 1,103 tests and preserved checksums;
both actual-build placement gates pass. Test copies:
`build/native-clients/native-clock-demo.*`.

**Not a completed migration:** NCLOCK/CLOCK2 are temporary test names and use
the fixed-size GFX API. Default xclock/xwave remain legacy so the accepted
four-app/resizing paths are not removed. Next: generic geometry/resize events,
bounded retained representation for wave (524 edges exceed 48 commands), a
task-safe Z80 request, and a measured four-native-slot layout before default
cutover/removing compatibility glue. Keep xwave algorithm/optimization separate.
Physical C128 confirmation of the new clock remains pending.

### Merged generic-loading checkpoint (PR #36)

User exploratory work exposed the limitation behind the four named apps:
launch/control/panel paths are app-specific, and UDEX images use fixed link
addresses. The new priority is generic graphical apps that select a free fitting
slot without OS edits. Issue #35 and branch `graphics-generic-apps` start from
merged main `9af159b` (PR #31). Plan: `docs/GENERIC-GRAPHICS-APPS.md`;
roadmap now puts this before service extraction. Step 1 now implements bounded
UDEX 0.2 page relocation from ld65 o65 records (not address scanning). A single
real C image executes in both native bank-1 slots on VICE D64/D71, with pointer,
BSS, private recursive stack, yield/sleep, exit/reap/reload and rejection tests.
Independent flat links match both installed images. Evidence is preserved in
`bench/{artifacts,results}/2026-10-04-relocatable-apps`.

Placement at that checkpoint: loader CODE `$D900-$DFFA`; RELOC `$1880-$19ED`; ACCESS
`$1F00-$1F69`. Storage/lookup reservations shrink to `$1880`/`$1F00`, enforced
by link/build/map gates. Never use `$D100-$D4FF`: root/task-2 CPU pages own it.
No core, public gate, runtime stack or app-slot relocation was required.
Normal four-app VICE D64 and unmodified 1986 native-input regression pass;
1986 has not separately qualified the new relocatable C fixture. Clean parallel copied-source build
reproduces both disks and the new executable. Published root snapshots unchanged.

`additional-apps` / issue #32 remains a separate worktree with `.CBM` container
and image conversion work (`6b61f5c`); do not overwrite or absorb it incidentally.
Other active worktrees include console-sleep and fix/cowsay-output. The current
root worktree was clean before creating this branch. The relocation probe uses
the private loader, not a user-facing launch path. Do not claim name-table removal makes four heterogeneous
native/managed slots interchangeable. Remeasure tight budgets before coding.

### Generic background-launch checkpoint

Following `fbdc72d`, this checkpoint implements unknown `name &` using
private selector 0 for free-fitting native
load/activation (task 3 then 4). The graphics service owns names and selected
instance; the running panel reads bounded names. Legacy CONTROL stops verify
the occupant's name, so `xcalc -q` cannot kill HELLO. Ordinary disk commands
and clock/wave callbacks remain unchanged. New independent sample, installer
and guide: `user/examples/xhello.c`, `tools/add_disk_apps.py`,
`docs/GRAPHICAL-APPS-SDK.md`. Test `build/generic-apps/generic-demo.d64`/`.d71`.

VICE D64/D71 ordinary-shell generic tests and old four-app VICE/native-1986
input tests pass. Captures use WM injection for VICE, not native mouse input;
1986 covers the old four apps, not yet HELLO. Physical confirmation pending.
Exact artifacts/results: `bench/{artifacts,results}/2026-10-04-generic-launch`.
1,081 host tests pass; an isolated clean parallel build reproduces nine outputs
including both disks and HELLO.BIN. All test-owned VICE sessions are closed.
Loader now `$D900-$DFFE`, ACCESS `$1F00-$1FEB`; GRAPHICSCODE through `$11F4`,
GRAPHICSHELP through `$A1D7`, resident BSS through `$9AFE` (**one byte spare**),
high module through `$E640` (three spare). No ownership boundaries moved.
The VICE pointer harness now uses measured helper/shadow padding, never BSS.

The checkpoint below supersedes the background-only restriction. Name-based
control/native-client migration, followed by clock/wave compatibility, remain.
Two generic native slots are an intermediate result. Further resident growth
needs a placement decision. The user authorized merging the checkpoint below;
keep issue #35 open and leave published root snapshots unchanged.

### Foreground, console SDK and third disk format

Follow-up to `1699e82`: bare one-word UDEX 0.2 launch falls back
from the compatibility loader's BAD_VERSION to automatic native admission;
the selected instance owns foreground/Ctrl+C. `name &` stays background-only.
VIC initialization moved to the graphics service's CREATE path. The independent
`user/examples/args.c` and `tools/build_console_example.py` prove arbitrary
fixed console filenames, argc/argv, fd 1/2 output, return 37 and BSS reset,
including with clock/wave and two generic windows. Console execution remains
synchronous and bounded: no background console/stdin or `$?` expansion claim.

`make boot` builds `.d64`, `.d71`, **`.d81`**; `publish-boot` explicitly publishes
all three but has not been run. D81 has rebuilt standard 1581 BAM/directory/file
chains. Native BOOT still uses 21 sectors per track: preserve T/S addresses,
not a linear D81 copy. The filesystem detects geometry each open, supports
296 directory slots (16-bit enumeration cursor), and reads both BAMs for df.
No sibling 1986 sources or existing release snapshots were changed.

Memory: resident BSS ends `$9AFA` (5 bytes spare); GRAPHICSCODE ends `$11FD`.
Storage low module ends `$1831`; policy `$B000-$C50C`; driver `$E300-$E8F9`;
BSS through `$E112`. All existing reservations, app slots and guards stay put.
Read-only storage no longer ships the unused outgoing filename encoder;
the full encoder contract remains host-tested. Size-oriented cc65 compilation
of the root bridge/CBM reader fits the additions. Keep volatile output store
`P[n] = value; ++n` separate: `-Os` plus static locals miscompiled `P[n++]` into
increment-before-store, caught by target file-header tests. Host tests alone
did not expose it.

Qualification: 1,095 host tests; VICE 3.10 D64/1541, D71/1571, D81/1581 independent-console and
foreground tests; unknown-name rejection/drag/reuse VICE regression; unmodified
1986 D64 native mouse/keyboard four-app regression; typed D81 BASIC BOOT and
c1541 directory validation. Clean parallel copied-source build and both
placement gates pass. Evidence: `bench/{artifacts,results}/2026-10-04-console-d81`.
Physical 1581 and new generic-app hardware feedback remain pending. Test the
`build/generic-apps/apps-demo.d64` / `.d71` / `.d81` candidates via the SDK guide.

## Four-app checkpoint — 2026-10-01 (merged as PR #31)

**Latest working-tree checkpoint: four independent graphical apps.** Clock,
wave, banked calculator and new `XDRAW.BIN` now coexist on `graphics-four-apps`.
Xdraw is a task-4 C executable at `$3500` (1,477 image + 354 BSS bytes) with
its own 6×4 toggle grid, clear button, runtime, stack and retained command image.
Shell control target 6 / foreground bit 8, both banked lifecycle indices,
four-job accounting, and the desktop-plus-four-app running panel are integrated.
Use fresh `build/boot/udeks.d64` / `.d71`, or the exact preserved candidates in
`bench/artifacts/2026-10-01-four-apps`. Next gate: user/physical-C128 acceptance;
service extraction follows #30. The user authorized committing and pushing this
checkpoint; physical-hardware acceptance remains pending.

Placement stays inside existing bounds: graphics CODE `$0C00-$11B8`, helper
`$A100-$A1CE`, resident BSS through `$9AD2` (45 spare bytes), high module through
`$E633` (16 spare bytes). Banked lifecycle state uses direct indexed byte arrays;
stop/running helpers live in GRAPHICSHELP and constants in MODULERODATA.
The loader/access module remains full at `$D900-$DFFF`. No stack or common-gate
boundary changed. The shell has 53 bytes beyond its reserved image+BSS.

Qualification: 1,056 host tests; both placement gates; VICE true-drive D64/1541
and D71/1571 four-app drawing/arithmetic, independent close/reload, panel,
console, targeted Ctrl+C, shutdown, guards and completed bitmap/shadow equality.
Missing/malformed fourth images and a distinct `XEXTRA.BIN` fifth candidate
are rejected without changing the live code/retained images. The rejection
probe uses map-checked unused graphics padding plus the BSS/LOWBSS gap for a
self-restoring poll hook, never the live `$0C00` module entry.

Unmodified 1986 `81485cc7` passes D64 raw-IEC/native mouse and keyboard input.
Fixed 150-frame button delays dropped clicks during synchronous repaint;
the native harness now waits for WM sampled edges and a client sleep boundary.
This remains slow graphics, not a responsiveness optimization. A clean copied
source build (`build/four-apps/clean-four.153qmm91`) reproduces both disks,
both banked clients, shell and service outputs byte-for-byte. Evidence:
`bench/results/2026-10-01-four-apps`. Published root snapshots are unchanged.

### Three-app checkpoint (superseded by the four-app candidate above)

**Latest working-tree checkpoint: banked graphics bridge + independent calculator.**
`graphics-four-apps` now has a three-app user-test candidate: clock, wave and
calculator coexist. The next feature is a separate fourth graphical client
with shell/panel/close/capacity-rejection qualification—not xwave tuning.
Use fresh `build/boot/udeks.d64` / `.d71`; published root snapshots are unchanged.
These changes and the preceding load/native-execution increments remain
uncommitted. No merge or new physical-hardware acceptance is implied.

UTRQ 0.9 op 23 marshals create/present/event/close, checks the registered task
owner, copies titles and retains up to 48 generic eight-byte drawing commands
per client. The compositor replays them under its existing clip with no foreign
callbacks or cross-task paint leases. Arithmetic/layout/glyphs stay in the disk
calculator. Close marks the client closing, destroys the window, then waits for
cooperative EXIT before reap/release; a live task cannot be forcibly freed.
Clock/wave remain legacy managed apps. Task 4 execution and a second retained
buffer exist, but the fourth graphical launch path is not implemented yet.

Actual placement: bank-0 graphics CODE `$0C00-$11C4`, helper `$A100-$A191`,
resident BSS ends `$9AEC` (**19 bytes headroom**). Graphics output is 1,536
bytes, delivered at bank-1 `$C700-$CCFF`, lazily installed after boot's `$0C00`
scratch is dead. Retained images use `$CD00-$CFFF`; filesystem policy is bounded
below `$C700`. Loader/access module fills `$D900-$DFFF` (**no headroom**).
Calculator: native flag-0 UDEX, image 3,912 + BSS 412 bytes at `$2300`, leaving
284 bytes in its 4,608-byte allocation; private stack/pages unchanged.
UTSK diagnostic 0.2 byte 15 publishes task-2 state so `free` no longer mistakes
a live graphical task for foreground-pool occupancy.

The title marshal deliberately uses `memcpy`: an explicit loop compiled with
cc65 `-Ors` left a cached `ptr1` used for subsequent payload reads. The live
CREATE test caught invalid geometry; do not restore that loop without rechecking
generated assembly and a boot test. `banked_loader_probe.py` now uses the **not
yet installed** `$0C00` module region for its one-shot hook; every call checks
the installation flag. Never use the old `$9900` scratch—it is live resident RAM.

Qualification: host service ownership/atomicity/retained replay tests; VICE
true-drive D64/1541 and D71/1571 three-window arithmetic, drag, close/reload,
console, targeted Ctrl+C, shutdown, stack guards and bitmap/shadow equality.
The VICE harness injects WM clicks/getters, not native mouse packets. A clean
parallel build reproduces both disks, service output and calculator exactly.
Evidence: `bench/{artifacts,results}/2026-10-01-banked-calculator`.
Native 1986/physical-C128 feedback is the next user gate for this candidate.

### Earlier checkpoints (superseded where noted above)

**2026-10-01:** calculator committed/pushed as `5cd34f9` on `app-xcalc` after
user acceptance; not merged. Current branch is `graphics-four-apps`, based
on that commit, issue #30. The user explicitly prioritizes four graphical
applications before the next service extraction. The plan is in
docs/DISK-GRAPHICS.md and docs/ROADMAP.md. Do not count four window descriptors
as four loaded apps: the runtime still has the accepted two-slot limit.
The first increment adds an actual-build placement gate and tests four owner
descriptors in both manager variants. A private owner query supports the next
banked router, and create rejects wrapping horizontal geometry. No public
UAPP version or vector changes.
Qualification for this first increment: 1,024 host tests, container
graphics-apps-check + placement-check, and a fresh VICE D64 calculator/clock/
wave/console regression pass. The geometry fix/owner query use 57 resident
bytes; 651 remain before LOWBSS. Proposed bank-1 calculator allocation has
581 bytes beyond the old calculator image+BSS, not a promise that the new
client library will fit. Live regression records are in
build/four-apps/vice-regression; measured layout with input hashes is
build/four-apps/layout.json. This is not a four-app manual-test candidate;
the next implementation was the bounded banked loader/request/event path.

Delivery checkpoint (superseded by native execution below): bank-1 load-only module at `$D900-$DD07`,
private kernel gate `$F91C`, two separately owned allocations at `$2300/$3500`.
No resident C growth or public ABI change. Full-image validation precedes
ownership publication; failed loads may dirty only the FREE target. Disk
requests and kernel mapping survive. The 42-byte boot activation backup is
now boot-only bank-0 `$0C00` scratch; TASKLOADER has 3 bytes and BOOTINIT 2 bytes
left. Do not extend either without measuring/revising placement.
`make banked-apps-probe` (host, after container build) exercises actual loading
on D64/1541 and D71/1571. The test's large monitor writes exposed a VICE parser
failure, even with an inert hook; `write_kernel_blocks` now splits byte lists
into at most 32 bytes without resuming between chunks. The actual loader
passes with that corrected harness. Current user app limit remains two:
banked task contexts, marshalled owner-safe graphics/events, a relinked xcalc
and fourth executable are the next implementation, not performance work.
Qualification: 1,032 host tests, both placement gates, D64/1541 and D71/1571
live loader tests, and the normal VICE calculator regression pass. A clean
parallel build reproduces both disks exactly. Evidence and exact images are
in bench/{artifacts,results}/2026-10-01-banked-loader. No new 1986 or physical
hardware claim; all probe-owned VICE sessions are closed. Changes are not yet
committed, and the published build/ root disk snapshots remain unchanged.

Latest checkpoint (working tree): real C execution in bank-1 tasks 3/4.
Loader now 1,635 bytes at `$D900-$DF62`, with unchanged resident C/headroom.
Common TASKLOADER/BOOTINIT use 1,389/124 bytes. `gen_banked_bindings.py` derives
the private lifecycle/context/wait addresses and common byte accessor from
real maps; no new public ABI. `$43/$44` activates flags-0 images; `$C3/$C4`
reaps only root-owned zombies. Release also clears context/wait snapshots,
including after a public WAITPID. RUNNABLE is published last. Managed flags-2
images remain load-only; do NOT invoke old UAPP pointers from bank 1.

Each compiled client uses its own cc65 ZP/runtime, CPU pages, 672-byte usable
software stack, guards and private return-to-EXIT trampoline. Both clients
pass recursive C-local/stack preservation across YIELD/SLEEP, independent
state, exit status, rejection, reap and fresh reload tests on VICE D64/1541
and D71/1571 while legacy clock/wave and console commands remain usable.
1,038 host tests pass. Clean parallel builds reproduce both disks and client UDEX images; both
placement gates and the calculator arithmetic/window regression pass.
Evidence: bench/{artifacts,results}/2026-10-01-banked-native. Reproduce via
container `make -j8 boot graphics-apps-check placement-check banked-native-fixtures`,
then host `make banked-native-probe`. Changes remain uncommitted. No new
1986/C128 claim or published snapshot refresh.

At that checkpoint the next work was owner-checked graphics requests/events, then relink calculator and a
fourth client with shell/panel/close/Ctrl+C integration. This is still NOT the
four-window user-test candidate. Before public integration fix `free`'s
task-count heuristic: tasks 3/4 being live does not mean task 2 owns its pool.
Live native cancellation/window retirement is not implemented by the private
reaper (EBUSY intentionally); do not release a live task's resources. Probe
guards do not imply an automatic runtime stack-overflow trap.

Calculator checkpoint: branch `app-xcalc`, created from main `debf430` at the
user's request for the next graphical app. Mouse-only standalone calculator:
pure C fixed-point model + VIC UI, UAPP 0.4 bounded client-click pointer,
fixed-size window opt-out, control target 5 and shared managed slot ownership.
Bank-0 LOWBSS relocated from $0C00 to $9B00 (1,533 bytes in 1,536 reservation)
so xcalc can occupy $0200-$11FF; xclock and xcalc are mutually exclusive.
Bank-1 native APP1/stack and fixed shadow/gates are unchanged. Calculator
image is 3,993 bytes + 34 BSS; all arithmetic runtime is in that disk image.
Use build/boot images for testing; do not republish the accepted main snapshots
until publication is explicitly refreshed. Service extraction follows #30.
Do not mistake the namespace checkpoint below for the current branch.

Qualification: VICE true-drive D64/1541 and D71/1571 pass disk loading,
arithmetic through the client-click queue, reciprocal slot conflicts,
xwave coexistence, console commands, restart and shadow/bitmap equality.
Unmodified 1986 revision 81485cc7 passes native mouse/keyboard arithmetic,
dragging, error recovery and foreground Ctrl+C. The root-namespace regression
also passes; a separate clean parallel build reproduces both disks exactly.
Evidence and exact candidates are in bench/{artifacts,results}/2026-09-30-xcalc.
User acceptance: "looks good" (platform unspecified); no new physical-C128
claim is made. 1,016 host tests and preserved checksums pass. The published build/ root snapshots
are intentionally unchanged. Three-app concurrency is a documented loader
capacity follow-up, not implemented here.

Issue [#26](https://github.com/salvogendut/UDEKS/issues/26), branch
`storage-root-namespace`, worktree `build/root-filesystem`, based on merged
PR #25 (`d13a5c2`). Root-namespace runtime integration is implemented.
Main and historical release images are unchanged. The user reports
"everything runs beautifully"; the namespace implementation is committed and
pushed as `95aa2cc`; PR #28 merged as `b138b61` after recording the decision
to defer scripting. Published D64/D71 snapshots and checksums now live at
`build/udeks.d64`, `build/udeks.d71`, and `build/SHA256SUMS`. Fresh builds stay
under `build/boot/`; `make publish-boot` explicitly refreshes the snapshots.
README links to the categorized `docs/README.md` index instead of a flat
historical document list. This is functional acceptance;
the latest feedback does not identify the test platform.

The system disk (default device 8; bootstrap honors a valid boot-device byte)
now backs `/`. Physical `USH.BIN` -> `/bin/ush`, `RC.ETC` -> `/etc/rc`,
and program `NAME.BIN` -> `/bin/name`. Startup no longer mounts `/mnt`.
`mount 9 /mnt` attaches independent raw data media; unmounting it leaves
system commands available. No fallback search for commands on data media.
Missing/bad disk shell releases bootstrap root and enters bootfs recovery.

`fs_namespace.c` is linked into the bank-1 C service. UTRQ 0.8 adds CHDIR,
GETCWD, and OPEN descriptor 2 (UDEX candidate; reject script/config). Cwd is
still shared root-session state, not isolated per process. Paths accept
relative names, dot/dotdot, and repeated slash. Full-directory scans detect
folded-name/BIN-vs-SH ambiguity; no first-entry winner or persistent index.
.SH files are listable/readable, but not executable yet. Only designated
/etc/rc auto-runs, through the existing bounded startup interpreter.

Placement: recovery bootfs now $A000-$AFFF (4 KiB), filesystem policy
$B000-$CFFF (8 KiB), service state $E000-$E17F. Old $8A00 policy hole stays
unused. At least 128 bytes remain below service C stack top $E200; driver
$E300-$E8FF and shell stack $E900-$EFF0 stay put. Link/packer/bootfs lookup
limits agree. Do not reuse the old bootfs capacity for fixture programs:
EXIT/WAITPID fixture bootfs now contains just its actual probe shell.
Public gateway addresses, UAPP runtime, and window/cache placements unchanged.

Qualification tooling: `tools/root_namespace_probe.py` checks real ush on
true-drive VICE D64/1541 and D71/1571 with a separate device-9 disk and a
missing-shell recovery variant. `tools/startup_probe.py` accepts RC.ETC and
checks valid/invalid/missing startup. `tools/1986_storage_smoke_build.py
--root-namespace` checks native keyboard paths plus 12 clock drags and a wave
drag; that single-drive harness uses a device-8 alias, so independent device-9
coverage belongs to VICE. Preserve exact images/results under
`bench/{artifacts,results}/2026-09-30-root-namespace`.

Final checkpoint: 997 host tests and all preserved checksums pass;
container placement-check passes. Both VICE formats, separate device 9,
missing-shell recovery, all three RC variants, typed BASIC BOOT, compiled-C
SPAWN/EXIT/WAITPID, shadow/VIC equality, and native 1986 input/dragging pass.
A fresh parallel build reproduces D64/D71 byte-for-byte. D64 SHA-256 starts
`e959e62f`, D71 `5985e1d3`. No VICE processes remain. Preserved images and
evidence are unchanged by the subsequent documentation-only priority update.

Latest decision: reserve `.SH` and defer general script execution in issue #27.
The existing RC command runner stays; no scripting implementation was added.
Branch `shell-bounded-scripts` / worktree `build/shell-scripts` is a clean,
unused branch at `95aa2cc`, not active work. Do not resume it automatically.

Next: select one existing non-kernel service, define its disk image,
load/start/stop/dependency contract, and extract it without breaking the minimal
boot/read recovery path. This is independent of general scripting, four-task
scheduling, preemption, storage writes and graphics optimization. Keep the
accepted namespace PR focused; service extraction gets its own work branch.
The visible [roadmap](docs/ROADMAP.md) remains the priority authority.
Build/use gh in my-distrobox. Never clean root build: it contains worktrees.

## Previous feature: command extraction (#24, merged as PR #25)

Final issue #24 review: the user accepted the default-mount image and explicitly
authorized fixing the remaining presentation errors and merging. The banner
now uses stage-1 measurements of the actual bank-1 UIEC/UBFS 0.1 headers,
published at boot-chain offsets 21/22 (1 match, 0 mismatch). It says HEADER,
not operational/mounted: these checks do not validate the whole service image.
Successful runtime mount prints `mount: /mnt ready (read-only)` only after
reading media. No writable filesystem or automatic drive enumeration is claimed.
Normal boot now uses SETMSG $FF, matching the hardware-accepted diagnostic
setting. The earlier hang remains unexplained; do not claim a proven timing fix.
The app wrapper preserves loader errors; ush distinguishes absent/unmounted
program, busy slot, bad image, I/O failure, not-ready and already-running.
Only an actual loader failure reads TASK_ERROR; native-child busy returns
directly without trusting that child's stale launcher. Presentation stays in ush.
Final shell is 3,723 bytes + 368 BSS reservation (360 used), 5 bytes spare in
its 4 KiB slot. Link/UDEX/storage checks agree. Bootfs is 3,906 bytes.
Boot-console remains exactly 1,450 bytes (939 CODE + 511 RODATA); high-module
and all fixed gateway/shadow/cache placements remain unchanged. Start wrappers
use ordinary service CODE with their old high-module footprint reserved.
Release evidence is in `bench/{artifacts,results}/2026-09-30-command-release`.
The checkpoint paragraphs below retain their old sizes/error TODOs and quiet
boot setting; they no longer describe the release. Next roadmap feature: load
the first independent non-kernel service from disk, not graphics optimization.

Current worktree: `build/disk-commands`, branch `boot-disk-commands`, issue #24.
The user authorized three steps in sequence: merge graphics (#23, now merged
as `2c88e07`), move everyday utilities to disk (checkpoint `d42073c`), remove
resident command policy (current slice). See [command extraction](docs/COMMAND-EXTRACTION.md).
The resident catalog is gone. Eight names are handled by disk ush, including
numeric graphics launch/control; thirteen program names are disk-backed.
Normal bootfs has only mount/umount and recovery ush. UTRQ 0.7 op 20 queues
numeric service work; the bank-0 poll executes it after the request stack unwinds.
Its ASM wrapper MUST clear carry on synchronous return (set carry suspends the
native caller). ush owns completion text and prompts; generic EXEC/job ownership
remains a compatibility mechanism, not a command registry.

VICSHADOW is pinned at the previously qualified `$A1E0-$C11F` with exactly
8,000 bytes. Extraction leaves 3,071 unused bytes before it, not a new heap.
Full ush image is 3,685 bytes plus 384 reserved BSS (27 bytes left in its 4 KiB
reservation); recovery bootfs is 3,797 bytes. Do not grow shell features without
measuring its image+BSS bound. All old fixed gateways and UAPP zero-page entries
remain asserted. Build in my-distrobox; use gh there. Never run `make clean`
at the root because build contains active worktrees. Use an isolated copied
source directory for clean-build proof. Do not modify the sibling emulator.
Manual acceptance initially FAILED for the preserved command-extraction candidate:
the user reports clock drags becoming unusable / wave chrome missing in 1986,
and a cold typed BOOT on C128 + Pi1541 stopping at BOOTING UDEKS (reported
around 22 blocks). Both used the exact archived disk, not an older root build.
The boot bank probe destructively wrote `$A0` to bank-0 `$8000`,
now an operand in `udeks_vic_bitmap_set_clip` (linked `$06`). The fix moves
the destructive probe to boot-only `$1000` scratch in both banks. An enhanced
native 1986 test reproduces 294 missing clock-border pixels after one drag
on the old image; the fixed image passes 12 drags, wave launch/drag and cowsay,
including 14 pixel-exact border checks. Keep this visual assertion: the older
movement-counter-only test falsely passed the damaged image.
Exact fixed disks/results: `bench/{artifacts,results}/2026-09-30-bank-probe-fix`.
The user subsequently confirms the diagnostic D64 boots in 1986 and on real
C128 + Pi1541 (around 23 tracks, not blocks). The later app launch error was
a forgotten mount; after mounting, the user confirms the apps/windows work.
That completes the requested functional retest, not an explanation of the
earlier hardware hang: the accepted diagnostic D64 enables SETMSG messages,
whereas normal D64 stays quiet. Preserve both variants and this distinction.

The user now explicitly requests device 8 mounted at `/mnt` by default.
`user/etc/rc` enables that line; no kernel/shell/application binary changes.
Current normal disks differ from the bank-probe-fix disks only in RC's one
sector (62 changed bytes). Recovery still skips RC and requires manual mount.
New tests must prove direct app launches without manual mount and retain
explicit unmount setup for negative tests. Missing-mount `request failed`
wording remains a separate pre-merge polish item, not fixed by this policy.
No new commit/push/merge authorization was given with this change.
VICE D64/D71 + recovery, native 1986 input/windows, disk-exec rejection,
managed-app failures, disk-shell replacement, RC startup, compiled SPAWN and
shadow checks pass. Isolated clean parallel builds reproduce all disks exactly.
Exact bytes/results live in `bench/{artifacts,results}/2026-09-30-disk-commands`.
The original candidate remains preserved as failing evidence; current test
disks are in `bench/artifacts/2026-09-30-default-mount`, including a diagnostic
variant retaining the boot messages from the user's successful hardware test.

The paragraphs below are earlier checkpoints, not the active worktree.

Active worktree: `build/disk-graphics`, branch `storage-disk-graphics`,
issue [#22](https://github.com/salvogendut/UDEKS/issues/22), based on merged
PR #21 (`ea14666`). Disk-only managed `xclock`/`xwave` is implemented;
normal bootfs contains neither image. Use `mount 8 /mnt` before first launch;
stopping retains loaded code until reboot. The existing fixed slots and
rendering are unchanged. The shared validator locks the requested slot and
six JMP callbacks, rejects live-child staging conflicts before touching its
launcher, and fixes a pre-existing error-return Z-flag bug exposed by missing
files. VICE D64/D71, native 1986 raw-IEC mouse/keyboard, disk-exec, RC-startup,
compiled SPAWN and clean-parallel-build regressions pass. The shadow gate is
updated to mount before launching the disk clock. See [Disk graphics](docs/DISK-GRAPHICS.md)
and the exact `2026-09-30-disk-graphics` artifacts/results. Manual acceptance
is unrecorded; do not infer hardware qualification. The user now explicitly
authorizes the sequence: review/merge this slice, move everyday utilities to
disk, then retire the resident command dispatcher. Continue on a fresh issue
and branch after merge. No rendering optimization. Earlier exact test images
are untouched.

Previous accepted worktree: `build/disk-shell-startup`, branch
`boot-disk-shell-startup`, issue #20. PR #19 merged disk execution as `9ab1efd`
after the user's 1986 and real-C128/PI1541 acceptance. The next candidate boots
ordinary disk `USH` with bootfs recovery; see [Boot 0.2](docs/BOOT-STARTUP.md).
The accepted disk-shell checkpoint is `4b9bed5`. The new slice adds the C
startup reader (`RC`, 255 bytes / 54-byte lines), full/recovery shell variants,
bare-name disk fallback and standalone `free`/`df` using STATFS 0.6. The
persistent allocation is now `$9000-$9FFF`; the IEC driver/BAM reader moved
to bank-1 `$E300-$E8FF`, below the shell's `$E900-$EFF0` stack. Resident and
graphics placements stay fixed. See [Boot 0.2](docs/BOOT-STARTUP.md) for limits
and test commands. 913 host/evidence tests, VICE D64/D71, native 1986,
recovery/compiled-SPAWN/shadow checks and clean parallel reproducibility pass;
the exact candidate is in `bench/artifacts/2026-09-30-startup-sysinfo`.
The user now reports "looks ok to me" for this startup/sysinfo candidate.
Record positive manual acceptance; the platform and individual checks were
not specified, so physical-C128 qualification of this slice remains unrecorded.
Do not repeat the same generic test request. The user has authorized committing,
pushing and opening the issue #20 PR, then explicitly authorized merging.
PR #21 is merged; main is at `ea14666`.
The bootstrap must preserve the still-live 42-byte scheduler activator at
`$F68A` across storage calls. Kernel/shadow placements are unchanged.

The previous accepted worktree is `build/storage-disk-exec`, branch
`storage-0.2-disk-exec`, issue #18. PR #17 was merged by user authorization
(`92a2e36`); physical Storage 0.1 results are still unrecorded. Foreground
`/mnt/DISKCOW hello` now runs from disk, with failure/ownership checks and
bootfs retained. Build the user-test disks with `make disk-exec-image`.
See [Storage 0.2](docs/STORAGE-0.2.md) for placement, test coverage and limits.
The user now reports all suggested tests passed under 1986 after checkpoint
`f0a9065`, followed by successful testing on real C128 + PI1541 and permission
to continue. The requested manual hardware gate is complete; do not ask for
the same acceptance again or infer exhaustive device/error-path coverage.
This slice is now merged; continue disk-loaded shell/startup scripts, not
optimization.
The older hardware candidate is unchanged.

The unchanged hardware candidate remains in `build/storage-iec-read-only`, branch
`storage-0.1-iec-read-only`, issue #15. Storage 0.2 is now the priority in
[the roadmap](docs/ROADMAP.md). The native IEC C service links separately,
boots through secondary delivery, and serves mount/directory/file-read/unmount requests.
See [STORAGE-0.1.md](docs/STORAGE-0.1.md) for placements and live probes.
`mount 8 /mnt`, `ls /mnt`, `cat /mnt/HELLO`, and `umount /mnt` pass through the normal
shell on VICE true-drive 1541/D64 and 1571/D71, including error returns,
remount, bootfs fallback, and xclock/xwave-active listings. The shell probe
feeds keyboard events including Return: directly seeding the submitted-line
record skips the terminal newline and falsely breaks silent commands.

Bootfs now arrives directly in bank 1 through `SCHEDOVR`, not the old
11,708-byte staging container. `ls`/`cat`/`mount`/`umount` share one immutable multicall
UDEX extent; all previous programs remain. Runtime bootfs is still bounded
to `$A000-$D0FF`: 12,307 of 12,544 bytes used. The recovered bank-0 staging space is not extra
runtime bootfs space. Keep resident and graphics allocations fixed.

The previous 1986 failure was a backend-selection issue: `real_disk_drive=1`
requires a full quit/reopen in sibling revision `3979786`, not just reset.
The user confirmed mount/list after restarting. The new raw-IEC harness also
passes native boot, keyboard mount/list/cat/missing-file/unmount without
modifying emulator sources. Runtime storage does not use KERNAL disk traps.

Physical C128/PI1541 qualification of the preserved test disk remains open
after the authorized merge. `cbm_file.c` replaces the runtime formatted-directory/DOS-file
stream with read-only U1 sector reads: exact byte counts now pass for 0, 1, 2,
24, 255 and 515 bytes, including a one-byte final sector. The old failure also
reproduces with stock KERNAL; the isolated reference remains in the suite.
VICE 1541/D64 and 1571/D71 pass removal mid-read, sticky EIO, absent-media
failure, replacement media, caller context and unchanged bitmap. Immediate
remount requires one retry in the debugger test; keyboard tests recover with
graphics active. 1986 passes empty/one-byte/error/eject/reinsert keyboard tests.
885 host tests pass; placement, panic build and shadow gates pass. Exact test
disks/results are in `bench/{artifacts,results}/2026-09-30-storage-0.1`.
Always unmount before swapping media; no automatic media-generation detector
or physical-device qualification is claimed. Storage 0.2 is based on the
authorized merge while the hardware record remains pending.
Do not expand benchmarks or optimize IEC before completing this feature.

## Historical Tasking 0.1 decision

The next milestone is **Tasking 0.1**. Do not add another application or grow
the resident compatibility dispatcher before this milestone is complete.
UDEKS already proves native boot, independent displays, loader-managed UDEX
programs, a persistent `/bin/ush`, overlapping VIC-IIe windows, responsive
pointer input, and bounded Z80 work. Its present limitation is that init still
polls special lifecycle entries and the two graphical programs still occupy
special retained slots rather than ordinary scheduled tasks.

Tasking 0.1 will replace that special-case control flow with a bounded
cooperative 8502 scheduler. Timer-driven preemption is explicitly deferred
until context switching, stack ownership, task exit, and slot reuse are
qualified.

## Constraints that must not change

- The 8502 remains the resident executive. The Z80 remains a synchronous,
  bounded worker; the CPUs share the bus and are not presented as concurrent.
- Kernel mechanisms are primarily assembly. Scheduling policy, task tables,
  validation, and later services should be C where timing permits.
- UDEX programs depend only on published fixed gates and public headers, never
  resident C symbols.
- The initial scheduler is bounded and allocation-free in interrupt context.
- Fixed-address UDEX 0.1 remains supported during this milestone. Relocatable
  executables are a later storage milestone.
- Existing VDC console, VIC-IIe graphics, mouse, joystick, window management,
  shell, `date`, `ls`, `cowsay`, `xclock`, and `xwave` behavior must remain
  usable after every migration step.
- Z80 leases must stay short enough for input and cancellation to remain
  responsive. A task may logically wait for a lease, but the design must not
  claim that the 8502 executes while the Z80 owns the bus.

## Current transitional mechanisms

- `/bin/ush` is a persistent bank-1 program entered through the returning
  `$FF13` common-RAM gate. Its cc65 zero-page context is saved at
  `$E2E2-$E2FF`, and its software stack begins at `$EFF0`.
- Bank-1 task requests use the shared record at `$F359-$F37E` and the `$FF16`
  request gate. ABI 0.3 adds lifecycle operations to the original synchronous
  console/filesystem operations; blocking `WAITPID` now snapshots ownership
  privately while the shared record is released.
- Transient UDEX commands run synchronously in a saved loader slot.
- `xclock` and `xwave` are standalone UDEX images, but flag bit 1 still selects
  a six-vector managed-application lifecycle and two fixed retained slots.
- Init and the static service registry cooperatively call poll vectors. This
  is useful scaffolding but is not the final scheduler or IPC model.
- Foreground/background ownership and `Ctrl+C` still cross the compatibility
  shell path instead of targeting a general task or process-group object.

Do not delete these paths in one rewrite. Put each existing participant behind
the task model, validate it, and only then remove the replaced special case.

## Current implementation status (2026-09-27)

- Step 1 has a versioned lifecycle ABI, host-tested lifecycle state module,
  and diagnostic/validation seam. The installed scheduler now resets the
  resident task table, registers persistent `/bin/ush` as running task 1, and
  publishes the resulting `UTSK` record before entering the retained poll
  path. A bounded C round-robin selector is linked into the scheduler page and
  host-tested across empty, sparse, wrapped, and yielded run queues; the
  installed context-save/resume tail calls it between cooperative task runs.
- Step 2 is qualified in `1986`, VICE, and physical C128 hardware; ADR 0008
  freezes relocated page-zero/page-one ownership and the bounded copy
  fallback. The follow-on `UCCS` spike now also switches two real cc65 tasks
  64 times with live C frames and distinct software stacks, byte-identically
  in `1986` and VICE at 1/2 MHz. Its physical-C128 run remains outstanding.
- Step 3 has Task Request ABI 0.3 operations for `YIELD`, `EXIT`, `WAITPID`,
  `SLEEP`, `CANCEL`, and `SPAWN`, plus a pure host-tested policy layer.
  Production `YIELD`, non-returning `EXIT`, and immediate, nonblocking, and
  blocking `WAITPID`, bounded `SLEEP`, child-only `CANCEL`, plus task-2
  `SPAWN`, are implemented.
- The placement prerequisite for steps 3 and 4 is qualified. Stage 1 can
  deliver a scheduler image to `$1C00-$1FFF`; crt0 and probe are split boot
  outputs; the boot-only capability service is linked at `$0200`, installed
  before crt0, and safely overwritten by applications after startup. ADR 0009
  records the accepted capability relocation. These placements now support
  the installed scheduler and lifecycle handlers described below.
- `boot_console.o` is now a split boot image at `$1600`, and VICE proves it is
  safely overwritten by `xwave`; ADR 0010 remains proposed until the
  independent `1986` pass. The final boot-only gather is also split and runs
  in place at `$A1E0`, leaving the complete `$C120-$CEFF` tail available for
  lifecycle/scheduler integration.
- Lifecycle placement is active: `SCHEDOVR` carries the zero-padded 1 KiB
  scheduler page and the installed lifecycle tail at `$C120-$CDBC`. Stage 0
  loads it into bank 1 with KERNAL `SETBNK`/`LOAD`; a 192-byte one-shot
  common-RAM installer validates and copies it, clears its BSS, and the
  scheduler entry replaces that installer with the permanent task gate.
  D71/D64 cold boot,
  exact page/tail installation, VIC repaint, and application-slot reuse pass
  in VICE. ADR 0012 remains proposed pending `1986` and physical C128 runs.
- The production-shaped save/select/restore tail now fits behind the frozen
  `$FF10/$FF13/$FF16` entries: its separate link occupies `$FF05-$FFC3`, 191
  of the exact 192 reserved bytes. It captures A/X/Y/P/SP and the continuation
  before remapping, preserves the resident kernel stack, and restores the
  selected task's relocated page zero/page one and CPU context. The boot image
  installs it after startup. Eight 11-byte records plus reset/save/select
  callbacks occupy the exact `$CDBD-$CEFF` 323-byte window, while fixed
  callback vectors consume the page's final six bytes at `$1FFA-$1FFF`.
  `SCHEDOVR` ABI 0.3 appends the exact, build-locked 234-byte context image and
  192-byte gate; its checksummed bank-0 tail also installs the 1,163-byte
  lifecycle handler at `$C900-$CDBC`, outside both application slots. The
  normal checksum covers the
  six fixed page vectors, and the boot-console installer checksums and installs a
  42-byte post-startup activator at `$1BAA` and copies it directly to its
  `$F68A` common-RAM run address. Persistent `/bin/ush` now polls, yields, and
  resumes through the `$CF30` carry contract. D71 and D64 VICE probes observe
  repeated context switches and accept `xinit`; the xwave slot-reuse probe
  also remains green. Task 1 owns bank-1 pages `$D1/$D2`, above bootfs and
  outside the loader's `$8000-$8A00` backup. Dedicated D71/D64 tasks also
  prove that `EXIT(37)` becomes a zombie, releases the request record, and
  cannot resume. D71/D64 probes also prove live-child `WAITPID|NOHANG` returns
  zero, zombie status 37 is reaped with result one, the complete child slot is
  cleared, and a repeated wait returns `ECHILD`. The two-task D71/D64 probe
  additionally proves that blocking `WAITPID` releases the shared request,
  the child can issue `EXIT(37)`, and the parent resumes with result one and
  its original sequence `$44`.
- The first `SPAWN` increment is qualified: the common loader exposes a
  scheduler-private `$F919` load-only entry, validates a flag-zero bootfs UDEX,
  and copies its image/BSS into bank-1 APP1 without entering it. The loader is
  exactly 1,520 bytes in its frozen `$F910-$FEFF` reservation. D71 and D64
  probes load `/bin/cowsay` byte-exactly and clear a pre-seeded 32-byte BSS;
  lifecycle allocation and context admission are now layered on this seam.
- Full `SPAWN` is qualified on D71 and D64. The handler validates the request
  before loading, initializes task 2's `$D3/$D4` relocated pages and private
  context, and publishes its `RUNNABLE` slot last. A common `$F280` launcher
  converts the child's normal return into `EXIT(A)`. A persistent parent runs
  a compiled cc65 child through two spawn, blocking-wait, status-37 reap
  cycles with original sequences `$44/$66`, proving the real compiler stack,
  task-slot, and APP1 reuse.
- Bounded `SLEEP` is qualified on D71 and D64. The raster IRQ advances an
  overlay-owned 16-bit clock at 60 logical ticks/s on PAL and NTSC; the
  resident service pass wakes expired TIMER waiters. Zero and 601 ticks are
  rejected, while the maximum 600-tick request blocks and resumes with its
  original sequence after at least 600 logical ticks.
- Child-only `CANCEL` is qualified on D71 and D64. Zero, self, free,
  unrelated, already-zombie, and full-width out-of-table targets are rejected
  without mutating the target. The resident regression covers `$0100`, `$0101`,
  `$0102`, and `$FFFF`, preventing low-byte aliasing of zero/self/live-child
  IDs. Cancelling a blocked child clears its private wait snapshot, preserves
  status 130 in a
  zombie, and lets the parent reap that status through `WAITPID`.

## Implementation plan

### 0. Preserve a known-good baseline

Before changing context or task code, record a short repeatable smoke sequence:

1. boot to the `/bin/ush` prompt;
2. exercise mixed-case input, history, `date`, `ls`, `cd`, and `cowsay`;
3. run `xinit`, then `xclock &` and `xwave &`;
4. move, resize, focus, and close both windows with mouse and joystick;
5. confirm console input remains clean and `Ctrl+C` stops only the foreground
   graphical job;
6. stop graphics with `xinit -q` and launch the programs again.

Automate the portions supported by `1986`, retain VICE as the independent
oracle, and keep a concise real-hardware checklist. Record failures before
changing scheduler code so input or display regressions are not mistaken for
tasking defects.

### 1. Freeze the task ABI and task control block

Add a compiler-neutral task ABI document before exposing new gates. Define a
bounded task table whose minimum fields are:

- task ID, parent task ID, state, flags, and exit status;
- executable CPU, bank/MMU profile, validated image/BSS/allocation bounds, and
  entry address;
- saved 8502 registers, program counter, processor status, hardware stack
  state, cc65 software-stack pointer, and compiler-owned zero-page bytes;
- standard descriptors, current working-directory handle, controlling
  terminal/session owner, and foreground/background ownership;
- wait reason and bounded wake data for child exit, input, timer, or Z80 work;
- stack bounds plus canary state.

Initial states should cover `FREE`, `NEW`, `RUNNABLE`, `RUNNING`, blocked wait
states, `STOPPED`, and `ZOMBIE`. Exact numeric values and the table size must be
chosen only after a current linker-map/common-RAM audit. Publish a small
diagnostic record so emulator tests can observe current task, runnable count,
switch count, rejected transitions, and canary failures.

### 2. Qualify one real context switch

**Qualified 2026-09-26.** `bench/context-switch` implements the spike, and
[ADR 0008](docs/decisions/0008-context-switch-placement.md) records the chosen
relocated page-zero/page-one ownership with a bounded save/copy fallback. The
r5 image passes in `1986`, VICE 3.10, and on a physical C128. Canaries and
validation are in-image; integration with the kernel panic path arrives with
the scheduler.

Implement the smallest assembly spike that switches between two synthetic
8502 tasks and proves that all of the following survive independently:

- A, X, Y, P, PC, and hardware SP;
- the live page-one stack contents or a qualified per-task relocated page one;
- cc65 zero-page `$02-$1F` and the software-stack pointer;
- the selected MMU profile and task-visible bank;
- interrupts arriving immediately before and after a switch.

Use the spike to choose between relocated page-zero/page-one ownership and a
bounded save/copy strategy. Record that decision before integrating it into
the kernel. Add canaries and fail through the existing panic path on corruption.
The old `$FF13` returning gate remains available until `/bin/ush` passes through
the new switch path.

### 3. Add cooperative lifecycle operations

Extend the public syscall/request boundary with versioned operations for:

- task creation or loader-backed `exec`;
- `yield`;
- `exit(status)`;
- `wait`/`waitpid` with a nonblocking option;
- bounded sleep against monotonic kernel time;
- task-directed cancellation sufficient for the first `Ctrl+C` path.

Use Linux-compatible descriptor and errno conventions where they fit. Reject
invalid task IDs, illegal state transitions, overlapping allocations, bad
stacks, and unsupported CPU/format combinations without altering scheduler
state. Returning from a normal UDEX entry is equivalent to `exit`.

### 4. Introduce the cooperative scheduler

Implement a deterministic round-robin runnable queue. Scheduling occurs only
at explicit safe points in Tasking 0.1: `yield`, a blocking syscall, task exit,
or return from a bounded service pass. IRQ code may mark work ready but must
not preempt a task yet.

The idle path must continue polling the minimum transitional service registry
until those services become task endpoints. Sleeping or blocked tasks must not
consume runnable turns. A Z80 request is admitted only through the existing
bounded worker policy; completion or failure returns the owning task to the
appropriate state.

### 5. Migrate programs without a flag day

Migrate in this order:

1. represent init and the existing `/bin/ush` poller in the task table while
   retaining the old entry gate;
2. run `/bin/ush` through the qualified task context path and retire its manual
   init poll;
3. represent synchronous utilities (`date`, `ls`, and `cowsay`) as child tasks,
   publish exit status, and reclaim their allocation after `wait`;
4. replace the special `xclock` and `xwave` dispatcher slots with ordinary
   retained tasks using their existing application/window lifecycle adapters;
5. remove the obsolete compatibility paths only after equivalent behavior is
   covered by emulator smoke tests.

UDEX 0.1 lifecycle flags may remain as loader hints during migration; task
identity and scheduling state must not remain encoded as application-specific
global variables.

### 6. Move shell job ownership onto tasks

Make `/bin/ush` launch programs through the general loader/task interface.
A foreground child owns the controlling VDC terminal until it exits, stops, or
is cancelled. A trailing `&` leaves the child runnable and returns the prompt
immediately. `Ctrl+C` targets the foreground task rather than a command name or
window. Preserve the conventional exit result of 128 plus the interrupt number
where practical.

After the underlying operations are stable, add small Bash-like `jobs`, `fg`,
`kill`, and `ps` commands. Do not add them as resident kernel builtins.

### 7. Replace global session state

Move descriptors and the working directory into the task/session model.
Implement public `chdir` and `getcwd` operations, inherit descriptors and cwd
on child creation, and remove the transitional root-session directory token.
This step should preserve the existing behavior of native `cd`/`pwd` and the
standalone `ls .` program while eliminating their private coordination state.

## Tasking 0.1 acceptance gate

The milestone is complete only when:

- `/bin/ush`, `xclock`, and `xwave` are represented and dispatched as ordinary
  tasks rather than manually polled special cases;
- foreground and background launches behave consistently, `Ctrl+C` affects
  only the foreground task, and exited children are waitable and reclaimed;
- repeated utility and graphical-program launch/exit cycles reuse their slots
  without stack, zero-page, MMU, window, or display corruption;
- the VDC console remains responsive while VIC-IIe windows are moved and while
  `xwave` performs bounded Z80 computation;
- invalid lifecycle requests return stable errors and do not corrupt the task
  table;
- host scheduler-policy tests pass, context/canary diagnostics remain clean,
  and the smoke sequence passes in `1986`, VICE, and on a physical C128;
- documentation and diagnostic records describe the implementation actually
  shipped in the boot images.

Timer-driven preemption is not part of this gate. It becomes the next tasking
revision only after a cooperative soak test demonstrates safe context, stack,
and bank ownership.

## Work immediately after Tasking 0.1

1. Complete per-process VFS semantics and implement baseline IEC serial device
   discovery and read operations; do not start with 1571 burst mode.
2. Resolve `/bin` from a storage-backed filesystem while retaining bootfs as a
   recovery source.
3. Add message queues/endpoints and extract input, terminal, display, window,
   time, and engine policy from the resident image in the ADR 0007 order.
4. Implement timer-driven preemption and the longer interrupt/task soak gate.
5. Build `xmandel` as a tiled Z80-compute/8502-present scheduler, cancellation,
   and storage-load stress test rather than as another privileged demo.

## First concrete change for the next session

PR #3 merged the lifecycle foundation as `00060f4`; PR #5 merged the event-wait
implementation as `1b7a6e0`; PR #7 merged bounded xwave rendering as `6aadcf3`.
Work continues on `graphics-raster-integration` (issue #10),
tracked by [issue #6](https://github.com/salvogendut/UDEKS/issues/6);
issue #4 retains its manual and hardware qualification gates.
[the event-wait proposal](docs/EVENT-WAITS.md)
defines the initial stdin-readiness scope, private request ownership,
placement constraints, and regression gates. ABI 0.4 `POLL` is now installed,
and idle native ush blocks on INPUT rather than repeatedly reading/yielding.
The pure C policy remains compile-only; its bounded assembly equivalent
reuses the WAITPID/SLEEP snapshots without extra BSS. Remaining space is
141 core bytes and 50 handler bytes; the resident/VIC-shadow boundary and
published task/runtime addresses are unchanged.

The compiled-C POLL probe passes on D71/D64: validation, finite wrap, infinite
wake, chunked/empty reads, stopped wake/continue, sequence restoration and live
stack locals. Seeded subscriptions qualify multiple waiters and ready/expiry
precedence. INPUT cancellation clears its snapshot. The shell/graphics smoke
checks stable idle suspensions and xinit/xclock/xwave plus console utilities.
Native ownership suppresses the resident compatibility shell's competing
input read, while preserving deferred EXEC and foreground job handling.

Independent 1986 machine-input smoke now passes on D71/D64: exact submitted
text, backspace/history, 1351 outline dragging, foreground Ctrl+C, background
clock survival and subsequent console input. The tracked emulator sources are
unchanged. The smoke exposed an inherited `$D02F` selector/arbitration bug;
the scanner now leaves extended columns idle with the resident layout unchanged.
See [the input report](bench/results/2026-09-27-event-waits-1986/README.md).
Initial xwave painting delayed a release scan by 689 frames in the baseline.
The [bounded-rendering increment](docs/XWAVE-RESPONSIVENESS.md) now permits
Ctrl+C during row 0 and completes with 21 cached row leases. Cached compositor
replay and closing-window redraw remain synchronous; issue #6 stays open.
The user reported the manual 1986 interaction check looked good. The next
[raster audit](docs/GRAPHICS-RASTER-AUDIT.md) confirms 49-byte whole-link savings
and approximately 12% lower line/24% lower fill timer counts in isolated 1986
and VICE probes. All pixels/dirty flags match an independent reference. Current
cooperative/IRQ paths do not reenter scratch, but future preemption needs
serialization. The historical candidate link moved the shadow to `$A1AF`;
production was unchanged at that checkpoint. Preserve the `$A1E0` staging
contract explicitly, regenerate import
bridges and qualify the integrated image before consuming the savings. Raw
CIA counts differ by about one per 65,536 events across the emulators; the
evidence retains that discrepancy and makes no physical-cycle claim.
Complete physical-C128 and manual SDL/host input and
performance gates for issue #4. Then generalize
task allocation and migrate shell jobs/graphical applications to ordinary
lifecycle tasks. Do not claim Tasking 0.1 complete or discharge the older
ADR 0010/0012 and integrated-context hardware gates from these VICE results.

## xwave drag-freeze correction (issue #8)

On `fix/xwave-drag-freeze`, repeated native dragging reproduces the reported
freeze on the PR #7 disk. The reference cc65 outline-mask expression stores
outside its record and overwrites the lifecycle dispatcher at `$F415`.
An equivalent complement/right-shift expression fixes the generated store;
eight saved CODE bytes are reserved to preserve the frozen `$A1E0` shadow
placement. No 1986 source changes are required. D71/D64 partial/cached drag
stress, Ctrl+C and subsequent console input pass; VICE boot/scheduler/shadow
smokes pass. See the [regression report](bench/results/2026-09-27-xwave-drag-freeze/README.md).
PR #9 is merged as `5d089a4`. The user subsequently reported the real-hardware
checklist passed: "all good on real hardware" (2026-09-27). This closes the
drag-freeze functional hardware gate, not unrelated tasking gates or timing
qualification. Manual SDL confirmation remains outstanding. Rebase and
requalify `graphics-raster-audit` on this fix before integrating its scratch
optimization; its earlier checkpoint is not a qualification of this revision.

## Raster integration continuation (issue #10)

The scratch-only line/fill optimization is integrated atop PR #9. It removes
81 CODE bytes and adds 32 BSS bytes; a named 49-byte CODE reserve preserves
the frozen `$A1E0` shadow boundary. Normal private bridges are regenerated;
no common-RAM gate, UAPP runtime address or legacy row reservation changes.
The audit and standalone builders retain an automatic-local reference even
though production now uses static locals. Drawing remains cooperative,
non-yielding and non-reentrant; preemption needs service serialization.

Clean parallel builds are deterministic. Native D71/D64 drag stress, console
recovery and clock survival pass, as do VICE scheduler/app smoke and complete
bank-0/bank-1 bitmap equality. Primitive timer counts improve about 12% for
lines and 24% for fills. The same active-display native script reduces worst
partial/cached drag-release latency 348/619 → 290/541 PAL frames. Cached
repaint is still much too slow, so issue #6 remains open; this does not finish
Tasking 0.1. Exact evidence is in
`bench/results/2026-09-28-graphics-raster-integration/`.

Next: review/test this integrated disk on physical C128, then design a bounded
cached-compositor continuation with explicit ownership and cancellation.
Consume the 49-byte reserve only under placement gates; if it cannot cover
the state, make the service-placement decision explicitly. Do not introduce
recursive service polls into raster loops. General task allocation, per-task
VFS/descriptors/CWD, older tasking hardware gates and preemption remain pending.

## Focused cached replay (issue #6 continuation)

The `graphics-bounded-replay` branch builds on the unmerged raster-integration
branch. The focused xwave damage callback resets its draw cursor and returns;
normal application polls replay up to four cached vertices each without more
Z80 rows. An obscured wave still replays synchronously under the manager's
damage clip to respect windows above it. Host wireframe equivalence, D71/D64
native drag/cancel/console gates, VICE graphics/app smoke and bitmap equality
qualify this narrow increment. Last native drag waits for replay completion,
then checks the worker still recorded exactly 21 leases. Worst tested cached
drag release falls from 541 to 266 PAL frames, but the image takes additional
polls to fill: 674 PAL frames after the last release in the saved native
run. This trades complete-image time for interleaved input. Issue #6 and
real-hardware qualification remain open. See
[the bounded-replay note](docs/BOUNDED-REPLAY.md). The next design decision is
an occlusion-aware, cancellable compositor that bounds damage/chrome/obscured
client work too; do not treat this focused optimization as that compositor.

## Pixel-preserving move-cache spike (issue #6)

`graphics-window-cache-spike` records the next implementation seam in
[WINDOW-MOVE-CACHE.md](docs/WINDOW-MOVE-CACHE.md). A 6,656-byte candidate
bank-1 VIC-window lease at `$4200-$5BFF` can hold xwave's default packed
168×104 image (2,184 bytes) and a tested 220×160 resize (4,480 bytes).
The host-only capture/paste model checks all
source/destination bit alignments, edge masks, VIC row interleave, background
preservation and oversize refusal. This is **not** wired into production;
current boot images still use bounded vertex replay. A full 320×200 surface
does not fit. The standalone machine transfer prototype now passes eleven
cases in each of 1986 and VICE, comparing every pixel, dirty flag, cache guard,
service-page restore and MMU mapping. IRQs are masked and display disabled;
bank ownership under tasks/worker activity and compositor integration remain
unqualified. Its 99-byte common gateway fits the existing workspace, but
the C implementation + gateway source + state need 1,273 bytes against a
49-byte resident reserve, before manager/ABI bindings. Default paste takes
roughly 2–3 seconds at nominal 1 MHz, so do not ship it as a speed fix.
Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-transfer/`.
The measured assembly increment now passes the same eleven bank-transfer
cases plus all 64 alignment pairs/full-width/right-edge row checks in both
emulators. Default paste changes 1.94–2.76 M → 0.325–0.593 M CIA ticks
(4.56–6.87× by paired case), before screen commits. Wrapper + ASM + state
is 1,023 bytes, down 250 but still 974 beyond the resident reserve before
bindings. Its gateway/staging lease spans the complete operation and does not
yield; IRQs remain masked, so this is not a live-input acceptance result.
Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-asm/`.
The runtime placement audit is complete: `make graphics-cache-placement` in
the reference container reconstructs the scheduler payload and measures real
listings/objects. All 3,552 post-shadow bytes have an owner, including 141
packaged padding bytes and 50 unfilled handler-reservation bytes. MODULE is
full; its extra contract byte, guard and stacks are not free. The probe page
overlaps APP1. Evidence: `bench/artifacts/2026-09-28-graphics-cache-placement`.
Next: measure compact in-place ASM display-service raster replacements while
retaining public C entry points and exact semantics. Five routines use 2,023
live CODE bytes; no savings are claimed until replacement/state/helper costs
are measured. Keep savings padded to freeze the shadow/private bindings until
cache + bindings + bounded continuation fit. See
[GRAPHICS-CACHE-PLACEMENT.md](docs/GRAPHICS-CACHE-PLACEMENT.md). Then bounded
lease integration and active-IRQ/input/compositor gates follow.
The first compact fill candidate is now standalone-qualified in 1986/VICE:
clipping stays C; a 102-byte ASM span merges edge masks and marks logical dirty
pages. Full experimental link saves 86 bytes (83 CODE + 3 BSS), with unchanged
helper membership. Bulk fills improve 3.55–3.57×, small-fill matrix 1.29×;
display is off and IRQs masked. Eight PRGs/16 positive records include a fresh
dirty-map crossing, and two deliberate missing-flag records are rejected even
with correct pixels. Evidence: `bench/{artifacts,results}/2026-09-28-graphics-span`.
The unpadded experimental shadow at `$A18A` must never be booted.
The follow-on public pixel entry is also standalone-qualified: 190 ASM CODE,
zero BSS, signed clipping and exact cc65 stack cleanup, saving 87 linked bytes.
Its SP diagnostic was corrected to read into variables before comparisons;
the inline comparison itself pushed a cc65 temporary and falsely failed the
C reference. Sixteen full pixel/dirty/guard/stack records pass both emulators.
Evidence: `bench/{artifacts,results}/2026-09-28-graphics-pixel`.

Both mechanisms are now **installed in the display service**. All 173 net
saved bytes remain named resident padding; the shadow, UAPP, common gateways,
module/stack and scheduler allocations are unchanged. Private bridges regenerate
normally. Cache reserve now totals 222 bytes, leaving at least 801 more before
binding/continuation costs. No pixel move-cache is installed.
Clean parallel build is deterministic. Native D71/D64 pass 32 wave drags each
with a background clock and console cancellation; normal input and VICE
D71/D64 app/scheduler smokes plus complete shadow/VIC equality pass.
The same harness on the saved no-replacement D71 measures maximum partial
release 279→171 frames, complete release 266→167, cancellation 174→140;
remaining replay after the last release is 674→970, not an overall repaint
improvement. Physical C128 and visual resize/overlap tests are pending.
Exact testable disks and evidence:
`bench/{artifacts,results}/2026-09-28-graphics-primitives-integration`.
See [GRAPHICS-PRIMITIVES.md](docs/GRAPHICS-PRIMITIVES.md) for the user test.
The user reports the span/pixel build looks good; that checkpoint is committed
and pushed as `0406805`. This does not identify a physical-HW qualification.

The follow-on shared-raster step is now installed and emulator-qualified:
line stepping remains C but shares the ASM pixel entry; rectangles use four
fill spans; clear is 52-byte ASM. Twelve standalone PRGs/24 records compare
all pixels, dirty flags, stack balance and guards; host geometry oracle passes
1,000 randomized trials. The complete link saves another 294 bytes, held as
named padding; helper membership and frozen placements/ABIs remain unchanged.
Line primitives improve 6–8%, rectangle matrix 4.14×, clear about 10×.
Native D71/D64 32-drag and normal input/clock/console gates, VICE both-format
app/scheduler and full bitmap-equality gates, and deterministic clean build
pass. Same-harness maximum releases are 171/167→107/103 frames; cancellation
is **140→161**, not an improvement; remaining post-release replay is 970→655.
Physical/visual resize and overlap tests remain pending. Exact new test images
and evidence: `bench/{artifacts,results}/2026-09-28-graphics-shared-integration`;
standalone suite: `...-graphics-shared`. See
[GRAPHICS-SHARED.md](docs/GRAPHICS-SHARED.md).

Current cache reserves total 516; **at least 507 more bytes** are needed before
binding/continuation state. Cache remains uninstalled. Next: explicit
service-placement/shared-raster budget investigation with measured alternatives.
Do not promise more optimization can cover the deficit, shrink stacks, move
the shadow, remove commands or claim moves avoid redraw before integration.

The next placement/IRQ increment is now qualified as a **standalone private
bank-1 row overlay**, not a production cache: 213 bytes at bank-1 $4200 inside
a candidate 512-byte lease, packed image $4400-$5BFF (6144), measured/tested
resident binding194 including gateway source, zero resident BSS. That leaves
322 of the 516 reserve before policy, state, delivery and whole-link effects.
Common parameters/staging stay in the existing VIC gateway workspace; neither
$F400 nor shell/filesystem scratch is borrowed (outline tag invalidation is
explicit). Every row restores the kernel map and caller I/D flags; both
emulators pass 66 alignment/edge images plus a 220x160 snapshot, all pixels,
dirty flags and guards, stack balance and active IRQs. Removing only the live
SEI in a negative-control PRG is detected and rejected on both emulators.
Exact evidence: `bench/{artifacts,results}/2026-09-28-window-cache-overlay`.
See [WINDOW-CACHE-OVERLAY.md](docs/WINDOW-CACHE-OVERLAY.md) for reproduce/limits.
Next: measured bank-1 delivery/lifetime ownership, then explicit completed-image
notification and generation-owned bounded cache continuations in the window
service. Do not cache partial or newly raised obscured windows, infer completion
from end-paint, or claim production input/NMI/GUI/HW qualification from this proof.
No new user boot image or cache-enabled move path is available yet.

The subsequent delivery/lifetime increment is now experimental-qualified:
prefix the secondary payload at bank-1 $4200 with the exact 213-byte core;
USOV and activation bytes remain at $5000+, same end $6229, one stage-1 LOAD
address byte changes. The 512-byte core/identity slot survives both-format
VICE boot/xinit/clock/wave/console/shutdown/restart and native 32-drag gates
with background clock and console cancellation. No new resident bytes or
extra LOAD; ordinary disks are unchanged. Delivered core is not invoked.
Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-delivery`.

Pure C cache lease/generation/row policy is host-tested, not production-linked.
Actual cc65 record sizes are lease13/row9; measured bank-1 link is
213 core + 1828 policy + 526 helpers = 2567 bytes, unexecuted. Bank-1
$E700-$EFF0 is the shell's live stack, not scratch. Candidate code4200-4CFF,
private C stack4D00-4DEF, identity4DF0-4DFF, packed image4E00-5BFF (3584)
needs dispatcher/state/stack gates before freezing; default168x104 fits,
220x160 would redraw. Do not confuse it with the delivered 512-byte core
or earlier row-only 6144-byte image candidate.
Next: private C runtime/stack machine proof and measured dispatcher, then
explicit completed-image notification (UAPP ends at CFFF; no D000 append),
generation-owned bounded window-service continuations and whole-link/input/
compositor/HW gates. Current normal build still replays moved windows.
See [WINDOW-CACHE-DELIVERY.md](docs/WINDOW-CACHE-DELIVERY.md).

The private C runtime proof is now standalone-qualified in 1986 and VICE.
Real C policy/helpers execute from bank 1 behind a 118-byte dispatcher:
module2685 code at4200-4C7C, state28 at4CD0-4CEB, private C stack4D00-4DEF,
image4E00-5BFF3584. C gateway59/common source binding83 + row binding194 =277,
leaving239 of516 before marshalling/completion/delivery/NMI/continuation costs.
All26 published ZP bytes are saved/restored, twelve addresses link-asserted;
caller uses bank0EFF0, while bank1E700-EFFF remains independently protected.
547 dispatcher calls/132 rows/66 images and439 calls/208 rows/default168x104 pass full
shadow/dirty/runtime/stack/guard oracles. Three exact one-byte negative controls
detect unsafe IRQ mapping, shifted ZP restoration and using the shell stack,
even with correct pixels. Diagnostic repair is outside the candidate binding.
Lowest observed changed private stack byte4DDE is not a hard depth bound;
do not shrink the240-byte stack. IRQ counter is32bit, allfour I/D modes tested.
Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-c-runtime`.
No production binding, completion notification or cached move is installed.
Next: measure versioned UAPP completion + C manager marshalling/continuation
cost, qualify production delivery/validation and NMI ownership/deferral before
enablement. Preserve53 vectors throughCFFF; do not append atD000, cache partial
or newly raised obscured windows, borrowUSHstack or claim live input/task/Z80/
GUI/HW qualification. See [WINDOW-CACHE-C-RUNTIME.md](docs/WINDOW-CACHE-C-RUNTIME.md).

### Latest graphics checkpoint — 2026-09-28

This supersedes the earlier candidate budgets above. A bounded C command now
combines policy, one row transfer and acknowledgement in one private-runtime
lease. Both emulators pass alignment/edge cases and one capture reused for two
pastes after erasing the source, all pixel/dirty/runtime/stack guards and three
one-byte live fault controls. Candidate module: 3,116 bytes at bank-1
$4200-$4E2B; state 22 at $4EE0-$4EF5; private stack $4F00-$4FEF; packed image
$5000-$5BFF (3,072). Combined resident binding: 241 bytes, not installed.
Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-command`.

The explicit completion seam IS installed: UAPP 0.3 optional header pointer
$CF58, unchanged 53 vectors/ZP, version-gated xwave-only helper. Actual C host
tests and both-format VICE/native boot/input/drag/Ctrl+C/background-clock and
post-drag completion gates pass. Shadow/scheduler and bitmap-equality gates
pass. It spends 158 CODE bytes and no BSS from shared padding (294 → 136);
all primary placements remain frozen. Bootfs is exactly 11,708 bytes: no
application growth without a capacity decision.
Evidence: `bench/{artifacts,results}/2026-09-28-window-completion`.

Remaining padding is 358; the combined binding would leave 117 BEFORE manager,
NMI and delivery integration. Do not claim complete cache fit or skipped plotting.
Next: production-shaped manager continuation/marshalling budget, NMI ownership
and deferral, and exact C-module delivery validation. Preserve existing memory,
stack, service and scheduler contracts and redraw fallback. There is no new
user-visible cached-move build yet; this checkpoint needs no new manual test.
See [WINDOW-CACHE-COMMAND.md](docs/WINDOW-CACHE-COMMAND.md).

Final gate: 736 host tests pass; complete clean parallel `boot all` rebuild and
`placement-check` pass. Both rebuilt disk hashes match the qualified completion
images exactly. Evidence includes the shadow/install/layout blocks in
`bench/results/2026-09-28-window-completion-layout`. No VICE sessions remain.

### Latest graphics checkpoint — deferred NMI, 2026-09-28

This supersedes the 358/117-byte budget immediately above. The production
8502 NMI service is installed: exact eight-byte common stub at FFE2-FFE9,
pending FFF5 and wrapping/coalesced drains FFF6-FFF7. No I/O, MMU writes,
compiler ZP or C in the stub; the pointer IRQ drains only after mapping kernel
I/O and saving registers. Z80 return/bootstrap bytes remain unchanged.
Installation is boot-only before input readiness; RESTORE during boot is not
qualified, nor is RESTORE a reset/cancel command. Physical confirmation remains.

Standalone combined-C NMI stress passes in both emulators, with independently
counted arrivals in worker-flat leases and outside them, exact arrival/drain
totals and complete pixel/dirty/runtime/stack guards. One live STA→BIT opcode
fault retains correct pixels but fails the drain proof. Diagnostic observer
FF20 is NEVER production-linked; that address belongs to TASKGATE in the OS.
Evidence: `bench/{artifacts,results}/2026-09-28-window-cache-nmi`.

Both normal disk formats pass VICE/native boot and continuous CIA2 NMI across
Z80 wave/clock/completion gates. Native additionally uses the real RESTORE
keyboard API and tests typing/history, mouse dragging, foreground Ctrl+C,
console recovery and background-clock survival. Evidence:
`bench/{artifacts,results}/2026-09-28-nmi-integration`, plus the independently
bound `bench/results/2026-09-28-nmi-integration-layout` clear/install/bitmap/
placement gate. Docs and reproduction/manual steps: `docs/WINDOW-CACHE-NMI.md`.

NMI object71 CODE + two JSRs6 =77, no BSS/ZP. Shared padding136→59; remaining
total281. Candidate binding241 leaves only40 BEFORE manager continuation/
marshalling and delivery validation. Actual-link tests prove unchanged primary
segments, all unchanged module footprints except the charged transport/pointer
changes, normal/panic agreement and actual linked call sites. Placement audit
rejects one-byte NMI/pointer growth. Bootfs is still full at11,708 bytes.

Final gate:745 host tests, complete clean parallel `boot all`, placement-check,
and rebuilt-image/input hash equality pass. D71 SHA256:
`afc0f96179c33babb732471596c2ff8006ffdfb4574778c0f6bee570d1ace8b0`;
D64: `06892e171b443af308adcf794979d621ba109559142a7677e942ac9168062786`.
No VICE sessions remain. Changes are uncommitted on graphics-window-cache-spike;
latest user said continue, not commit/push.

Manual test now useful: xinit → xclock & → xwave &, RESTORE during plotting
and after drag, verify mouse/console remain alive; foreground xwave → Ctrl+C
must still leave the background clock alive. RESTORE should not cancel wave.
This is resilience, NOT faster moves: cached GUI moves remain disabled.

Next: measure the production-shaped C manager continuation/marshalling and
identify service-local code savings or a reviewed relocation BEFORE enabling
the combined binding. Completion eligibility alone is not a generation-owned
cache; preserve explicit completion, reject partial/obscured images, bound rows,
handle damage/clock/resize/cancellation and retain redraw fallback. No borrowing
USH/private stacks, common gateways, module guards, app slots or scheduler
padding. Physical NMI confirmation can proceed while the budget work continues.

### Latest graphics checkpoint — manager budget, 2026-09-28

User reports the preceding build looks good; the test platform was not named,
so do not convert that into a platform-identified physical NMI qualification.
This section supersedes the 281/40-byte budget above.

Private C manager savings ARE installed: reset sharing58, chrome geometry
reuse145, intersection arithmetic18 =221. Manager7679 CODE,130 RODATA,88 HIGHBSS;
all other module footprints and primary segment bounds unchanged except the
compensating transport padding59→280. No added helper modules. Explicit private
fastcall annotations saved0 and were NOT applied; public calling conventions
remain unchanged. Host tests compare complete binary drawing/state traces
against the prior C source for geometry/flags/lifecycle/move/resize/close paths.

Remaining total padding502. Combined binding241 leaves261 BEFORE controller,
hooks, source/destination locks and delivery validation. A real isolated bank-0
link of the flow992 CODE+4 RODATA, caller state4 and binding241 is739 bytes
short even after spending ALL502. No new library helpers. Its shadow moves;
it is deliberately UNBOOTABLE and never packaged. Every split ld65 output was
retargeted, and source/provider/object/map/hash evidence is preserved in
`bench/artifacts/2026-09-28-window-manager-budget`. Do not mistake this sizing
map for the normal installed map or repurpose scheduler/app/stack/common space.

The four-byte C continuation (`move_cache_flow.c`/`window_cache_flow.h`) is
host-tested but NOT normal-linked: capture, same-content-generation repeated
pastes, stale/wrong-ticket rejection before touching the shared request, at
most one row per STEP, cancellation/handle reuse/generation wrap, bad geometry
and exhaustive unexpected result tags. It calls the actual C command/policy
in host tests. The original variable-mask result comparison crashed the
reference cc65 optimizer; explicit scalar comparisons compile with full-Oirs.
This is not yet a complete compositor integration: no locks, hooks, private
placement, delivery or live continuation machine qualification.

Both normal formats pass native typing/history/mouse drag/Ctrl+C/background
clock/completion/RESTORE/CIA2-NMI gates and VICE boot/Z80/clock/completion/NMI.
Independent clear/install/tail/bitmap equality gates pass; new audit rejects
manager footprint drift. Evidence: `bench/{artifacts,results}/2026-09-28-window-manager-integration`
and `bench/results/2026-09-28-window-manager-integration-layout`.
Final750 host tests, clean parallel boot/all, placement-check and rebuilt
disk/map/kernel/bootfs hash equality pass. D71:
`5dc9c2bfc00e5c221e77ebcc1737587f2681337841316a2a24f80f2cf1d35db0`;
D64: `1fae55695a76d5e69eb641ed7910f81d3cb88a8c1f31b4cf5aa8a6ca6a24ada6`.
No VICE processes remain. Changes remain uncommitted; user said continue.

Next: measure a direct IN-BANK C controller under the existing SINGLE private
C runtime lease, with only bounded marshalling/hooks resident. Do NOT move the
current flow unchanged: its call to the resident binding would nest/reset its
own MMU/runtime/software stack. Refactor the backend to direct in-bank C calls,
measure the complete module/helper/dispatcher closure, persistent flow/lease
state, guarded240-byte private stack and packed-image capacity. No new layout
is frozen; keep the default168x104 image (2184 bytes) viable and oversize redraw
fallback. Repeat full pixel/dirty/ZP/stack/I/D/IRQ/NMI and real fault controls
for any new placement before delivery and live GUI enablement. Kernel hooks
must freeze capture/paste geometry and invalidate before damage, repaint,
restacking, resize, destruction/reuse or shutdown. Same-generation reuse is a
content ticket, NOT a per-paste nonce; no queued/reentrant continuation calls.

Cached GUI moves remain disabled; no new manual test is needed here. Docs:
`docs/WINDOW-MANAGER-BUDGET.md`. New qualifier invocation uses
`tools/nmi_integration_probe.py --checkpoint 2026-09-28-window-manager-integration --work build/window-manager-integration`
with build/1986/vice actions. `make clean` removed generated work directories,
not the preserved evidence; rebuild before rerunning those tools.

### Latest graphics checkpoint — direct bank-1 controller, 2026-09-28

Standalone controller now FITS and is emulator-qualified; production pixel
cache remains disabled. Read `docs/WINDOW-CACHE-CONTROLLER.md` for layout,
private protocol, evidence and remaining gates. No new manual test yet.

`move_cache_flow.c` has an opt-in IN_BANK direct backend and a private fixed
single-owner STATE specialization; default caller-owned prototype unchanged.
It must not re-enter the resident binding from banked C. Generic and fixed
flows pass the same exhaustive host contract/fault tests; actual fixed C
dispatcher+flow+command+policy is separately host-tested. Address/capacity
parameters default to the older command proof unless explicitly overridden.

First generic full link overflowed CODE by202. Fixed-state flow637 CODE+4 RO
(generic994 CODE), controller209; entire core/helpers closure3977 at4200-5188.
151 code slack; lease13/row9/flow4 at5220-5239; state guard22 at523A-524F;
private C stack240 at5250-533F and16 top guard5340-534F; image5350-5BFF2224,
default2184 leaves40. This layout is qualified only for the standalone proof.
Do not shrink the stack or claim its observed offsetCC is a maximum depth.
The unchanged213-byte row core is verified byte-identical. Gateway217 and
uninstalled binding241 leave261 of502 resident padding before hooks/delivery.
No ordinary kernel-linked module or frozen primary allocation changed.

Private protocol0.1: OP F790 init/invalidate/capture/paste/step0..4;
owner/window handleF792, content ticketF793word, eligibleF795, geometryF7A1;
success result0 publishes phaseF791 and ticketF793, INVALID1/BUSY2 otherwise.
This is NOT the prior raw command phase-tag result protocol. Stale/wrong-owner
STEP must leave request and state unchanged; other rejection scratch is not
promised unchanged. Capture/paste use the module epoch; repeated same-epoch
pastes are deliberate, calls serialized, no queued/reentrant operations.

VICE3.10/1986: alignment132rows476calls66images, repeated capture+two
pastes312rows333calls after destroying original source. Full independent
8000pixel+32dirty oracle, original ticket rejection, cancellation/oversize
fallback checks, all26ZP, hardware stack, caller/worker/USH software stacks,
all I/D modes and IRQ/MMU checks. Actual CIA2NMI reaches worker+kernel and
exact drains=total: 1986alignment8906(worker128), repeated15194(worker104);
VICE8785(worker147),15096(worker109). Four exact live single-byte faults
(SEI/ZP restore/USH-stack/NMI-pending) are detected without pixel corruption.
Diagnostics FF20/FF80 observer/IRQ are NEVER production addresses.
Physical RESTORE/Z80 NMI routing still unqualified; no new hardware claim.

Evidence `bench/{artifacts,results}/2026-09-28-window-cache-controller` with
exact inputs/generated assembly/maps/PRGs/raw/provenance/hash verification.
Tool `tools/window_cache_controller.py` build/run(--engine1986|vice)/preserve.
ca65 source-directory lookup must not consume the older template layout:
copied gateway/core assembly now uses the new include and build asserts C/ASM
address agreement. Preserve refuses overwrite. Changes remain uncommitted.

Next: measure full normal/panic integration delivery of the WHOLE C module
and bounded resident marshalling/hooks/locks within remaining261, then live
GUI/input/task/Z80/completion/cancellation/pixel gates before enabling moves.
Freeze capture source/destination per continuation; invalidate before damage,
clock overlap, repaint, resize, restack, destroy/reuse, shutdown and cancellation.
No borrowing common gateway/stack/module guards, app slots, USH or scheduler
reservations. Bootfs remains exactly full. Normal disks should remain byte-
identical to the manager-integration checkpoint. Final754 host tests and full
clean parallel boot/all + placement-check pass. D71/D64/kernel/maps/bootfs
hashes exactly match the prior checkpoint. The regenerated standalone build
report (all linked/program/source hashes) is byte-identical to the preserved
report after clean. New evidence is safe; transient emulator result directories
were removed by make clean, but the controller build was regenerated. No VICE
sessions remain.

### Latest graphics checkpoint — whole controller delivery, 2026-09-28

Whole controller now cold-boots and survives lifetimes in ISOLATED test disks;
still UNINVOKED there. Ordinary production disks remain unchanged and cached
GUI dragging remains disabled. No new manual test needed. Read
`docs/WINDOW-CACHE-CONTROLLER-DELIVERY.md` before next work.

The complete3977-byte archived machine-qualified module4200-5188 overlaps the
canonical scheduler source5000. New experimental secondary envelope LOAD4200:
module bytes, zero slack5189-520F, VCC2identity0.1 at5210-521F, zero to5FFF,
EXACT canonical scheduler/context/gate payload at6000-7228. Installed scheduler/
context/task-tail homes unchanged; boot source retired before VIC bitmap reuse.
The zero prefix also initializes future state/stack/image, but they are NOT
invoked by these disks. Identity includes length/checksum/entry4200/dispatch42D5/
capacity2224. Every complete4128-byte code/identity capture compares byte-exact.

Measured relocation deltas only: stage1two LOAD/end bytes, scheduler-tail
installerthree source bytes, task activationtwo source bytes, console installer
one checksum byte. Installer lengths unchanged, zero extra resident delivery
bytes. Console checksum is regenerated over composer+new activation bytes and
the build rejects any console byte change beyond checksum operands. ca65 uses
isolated generated constants; no normal build output is overwritten.

Both formats VICE exact slot at boot/xinit/clock/wave/completion/utilities/
shutdown/restart. Native both formats history/input, backgroundclock,32 wave
drags, foregroundCtrlC and console recovery, then exact slot check. Log's
"cached" latency means cached vertices, NOT pixels. No bootchainNMI stress or
physicalHW claim here; standalone C execution/NMI proof is separate.

Tool `tools/window_cache_controller_delivery.py` build/1986/vice/preserve,
work `build/window-cache-controller-delivery`. Reuses mature read-only smoke
functions from `graphics_cache_delivery.py` with explicit CORE_BYTES sizing
(former hardcoded512 captures generalized). All source inputs, emitted artifacts,
experimental disk hashes, exact build-report hash and every raw/log/provenance
file are bound by run reports before archival. Preserve revalidates all expected
captures/formats/32-drag gates and refuses overwrite. No ROMs/full snapshots
preserved. QUALIFIED evidence
`bench/{artifacts,results}/2026-09-28-window-cache-controller-delivery-r1`.
Non-r1 archive is historical/incomplete: archive test caught an omitted
canonical scheduler input copy/hash (bytes were embedded in secondary.prg).
Do not overwrite it or treat it as the final qualification. r1 explicitly
binds/preserves the consumed canonical input and must pass all archive tests.

Next actual normal/panic resident acceptance+compositor integration. Padding
still502, binding241 leaves261 BEFORE runtime validation, hooks/locks/marshalling/
persistent ticket/state. No complete-fit claim yet. Validate code/version/layout
before invoking unvalidated bank-1 C; initial checksum must precede row-core
selfmodification. CommonF7xx workspace is overwritten by other VIC gateways,
so it CANNOT retain a ticket/phase across polls. All state bytes must be charged,
not tucked into someone else's guards. Capture source and paste destination
must be immutable through READY; early drag cancels capture and falls back;
second drag/content mutation/resize/restack/close/handle-reuse/shutdown/cancel
must not resume stale row work. Ordinary recomposition during a move must not
destroy the retained READY cache merely because the source pixels are gone.
Full normal input/task/Z80/CtrlC/completion/overlap/resize/NMI/pixel gates are
required before enabling GUI cache use. Changes remain uncommitted.
Final758 host tests pass, including complete r1 archive/source/output/raw/run
binding checks. Clean parallel boot/all + placement-check passes; normal disk
hashes remain5dc9c2bf… (D71),1fae5569… (D64). Rebuilt experimental report is
byte-identical to r1, proving all listed input/linked/disk hashes regenerate
after clean. Both test disks are rebuilt under the work directory; transient
raw/logs were removed by make clean, not immutable evidence. No VICE sessions
remain. No new manual test yet; this step qualifies delivery, not pixel moves.

### Latest graphics checkpoint — pre-C acceptance and ticket seam, 2026-09-28

Read `docs/WINDOW-CACHE-ACCEPTANCE.md`. Page-bounded validation and persistent
original-ticket reconstruction now pass STANDALONE machine qualification in
VICE 3.10 and 1986. Normal disks are unchanged; no compositor hooks or pixel-
cached GUI dragging are installed. No new manual test yet. Changes remain
uncommitted on `graphics-window-cache-spike`.

New `bench/window-cache-acceptance/{validator,binding}.s` and
`tools/window_cache_acceptance.py` build/run(--engine 1986|vice)/preserve.
Trusted 79-byte validator copied to $F68A maps worker-flat, compares all 16 VCC2
identity bytes, sums ONE page (<=256), restores kernel. No unvalidated C, ZP,
software stack or callback; 16 polls for 3,977 bytes, last 137. Whole initial
sum and exact header required before INIT. Bad header/payload disable the
service; guarded calls return $FF without C. Sum is not authentication or
compensating-change protection. Do not revalidate mutable core after acceptance.

Five explicitly charged writable CODE bytes: acceptance state, checksum/ticket
word, owner, phase. Checksumming reuses ticket until acceptance; successful
commands snapshot original generation/owner/phase while masked; rejects retain
them. STEP reconstructs original ticket and owner, not current common scratch.
The probe replaces common code and poisons checksum/page between validation
polls; poisons common ticket/owner/phase before EVERY row STEP. Full 8,000-pixel
and 32-dirty-byte oracle passes: 132 rows/480 calls/66 images and 312 rows/337
calls/two images. Four commands blocked before acceptance account for +4 versus
the previous controller proof.

Safe pending-NMI drain under kernel I/O after copy/before worker (validator and
raw binding). Without this, outer serialization masks IRQ during copy and a
copy-time pending NMI suppresses worker observations. Each JSR charged three
bytes, existing installed drain already budgeted. Diagnostic CIA2 period 768
avoids 512-cycle CIA1 phase-lock. Stress positives: native 12,104 NMI (302 worker)
and 20,749 (159); VICE 12,034 (273) and 20,757 (237), exact drains=totals.
All 26 ZP bytes, I/D, MMU, caller/worker/USH/hardware stacks and guards pass.
Observed private offset $CC is not maximum-depth proof. $FF20/$FF80 observer/
IRQ ONLY standalone; physical RESTORE/Z80 NMI routing still unqualified.

Bad payload/header single-byte controls reject after 16/one polls, six blocked
commands, zero rows/pixels, all 26 private bytes stay $6D, no private C stack use
(seed intact). Actual single-byte SEI/ZP/USH stack/NMI pending faults trigger
only expected fields and fail positive oracle while pixel output remains exact.
Separate original PRGs prove one-byte changes despite different probe variants.
Extended diagnostic seed/scanner exceed old 128-byte signed-X copy limit;
unsigned loops qualified. Label insertion must match `\nscan:\n`, NOT install_scan.

REAL FOOTPRINT: raw 244 (217 gateway + copy/drain), seam 309 INCLUDES 79 validator
source and five state bytes, total 553 vs 502 available => 51 SHORT BEFORE hooks.
All objects have zero BSS/ZP. No production link/fit claim. Next recover bytes
via measured private savings/shared-installer refactor, then all actual normal/
panic hooks/locks/marshalling before live GUI tests. Do not borrow frozen shadow,
scheduler/apps/USH/common workspace/guards. Existing manager fixed-layout tests
require a new host trace/emulator qualification for any further savings.

Capture source and paste destination frozen until READY. Early drag cancels
capture/falls back; content mutation/clock overlap/resize/restack/close/handle
reuse/shutdown/cancellation invalidate stale ownership before writing. Moving
retained READY image cannot be invalidated just because ordinary background
recomposition erases source pixels. Need complete input/task/Z80/CtrlC/completion/
pixel/overlap gates before cached GUI enabled. Normal moves replay vertices,
NOT cached pixels.

Immutable `bench/{artifacts,results}/2026-09-28-window-cache-acceptance`
contains exact sources/generated assembly/maps/PRGs/raw/provenance/report hashes.
Run records bind full build-report hash plus programs/raw; preserve verifies all
and refuses overwrite. Five new host tests check decoders/state/no-C rejection/
budget/actual one-byte faults/archive hashes. make check: 763 tests, py_compile
and checksums pass. Full clean parallel boot/all/placement-check pass. Normal
D71/D64/kernel/maps/bootfs hashes match previous checkpoint exactly. Rebuilt
acceptance report is byte-identical to archive after clean; linked/program/source
hashes regenerate. make clean removed transient work raw/logs, not immutable
evidence; isolated PRGs rebuilt. No VICE sessions remain.

### Latest graphics checkpoint — compact validated transport, 2026-09-28

Read `docs/WINDOW-CACHE-COMPACT.md`. Standalone footprint reduction qualified
in VICE 3.10 and 1986. Still no normal resident link, revised-module disk
delivery, compositor hooks or pixel-cached GUI moves. No new manual test yet.
Changes remain uncommitted on `graphics-window-cache-spike`.

`tools/window_cache_compact.py` measure/module/build/run/preserve builds an
isolated specialization, reusing the acceptance diagnostic. Work directory
`build/bench/window-cache-compact`; new assembly source
`bench/window-cache-compact/raw.s`. Generic/production C flow remains unchanged.
Generated fixed-flow C rejects capture/paste geometry pointers other than the
shared request, then omits self-copying that request. Flow CODE 637→570.
Actual C dispatcher already uses the shared pointer. Host checks prove foreign
or NULL geometry rejection before mutation, capture/two-paste rows, cancellation
and generation wrap. Other C policy/command/controller sources unchanged.

Gateway is 196 bytes instead of 217: outer guard now owns PHP/SEI/PLP, common
command still CLDs; omit zero loads before MMU preset strobes; compute logical
dirty end from OFFSET+(RAWCOUNT-1)*8 with both carries. Full pixels/dirty and
all low-byte/count carry combinations qualified. UNCHANGED 213-byte row core.
Gateway source is appended to bank-1 module at $5146-$5209 and included in the
INITIAL checksum. Module 4,106 bytes, six spare before VCC2 $5210. All private
state, guarded 240-byte stack and 2,224-byte image remain unchanged. Do not
expand module past identity or shrink those allocations to fit future hooks.

Trusted raw wrapper installs a 20-byte loader at $F75A-$F76D. Loader copies
accepted source from worker RAM to common $F68A-$F74D, restores kernel I/O,
returns before the command. Source copy cannot overwrite the executing loader;
assembler guards enforce gateway<=208 and loader end<=PARAM. Raw called ONLY
behind accepted state + serialized resident guard, never directly. Same pending
NMI drain and common-workspace ticket reconstruction rules as previous proof.
Immutable banked source is not the common self-modifying copied gateway.

FULLY CHARGED: raw51 + seam309 (includes validator79/state5) + diagnostic patch
helper11 =371 resident bytes. Recover182 from553, aggregate headroom131 from502
BEFORE real manager hooks. Raw's diagnostic call remains charged. No complete
normal/panic allocation/fit claim; sources have zero BSS/ZP. Earlier delivered
3977-byte module DOES NOT contain this banked gateway source. Deliver this new
module before invoking new transport in an OS image.

Validation now17 polls, last10 bytes. Initial test caught the old hardcoded16
poll bound; generator/record decode derive it from module size. Page arithmetic
also handles exact256 multiples (last count0 encodes a full page, not an extra
page). Parent acceptance tool now accepts optional module/gateway/raw/driver/
source/fault-selector inputs; default CLI remains the older proof. Historical
archive immutable; current tool source hash has changed. Decoder default still
16 for old snapshots, new runs/preserve pass measured page_calls explicitly.

Both emulators: alignment132 rows/480 calls/66 images; repeated312/337/2 after
destroying original source, full8000+32 oracle exact. Poisoned common parameters
and original-ticket reconstruction still pass. Bad payload/header reject after
17/one polls; private26 bytes stay6D, stack unused, pixels untouched. Positives
NMI exact drains: native11981(worker475)/20762(338), VICE11937(483)/20647(339).
Coverage includes the worker source-copy lease; do not claim C-only arrivals.
All26ZP/I-D/MMU/stack/guard gates pass; observed private offsetCC unchanged.
Physical RESTORE/Z80 NMI routing still unqualified.

Four exact single-byte faults still fail positive oracle and preserve pixels.
ZP/USH-stack faults now patch the COPIED gateway via diagnostic helper after
acceptance: baseline writes original bytes, mutated immediate writes bad byte.
Do NOT alter accepted source and then weaken checksum to obtain a runtime
fault. SEI/NMI-pending faults remain actual instruction changes. Intentional
SEI leak may race NMI accounting (VICE drains differs by1); its negative gate
does not require positive NMI equality. All positive cases do require equality.

Evidence `bench/{artifacts,results}/2026-09-28-window-cache-compact` binds every
source/generated C/ASM/module/map/program/compiler flag, report/program/raw
hash and emulator provenance. New four host tests qualify C pointer semantics,
carry/page boundaries, full charged budget/allocations and both-emulator live
fault/archive hashes. make check767 tests and checksums pass. Full clean
parallel boot/all/placement-check pass; normal D71/D64/kernel/maps/bootfs hashes
exactly match prior checkpoint. Regenerated compact report is byte-identical
to archive after clean. Transient raw/logs removed by make clean, immutable
evidence retained; diagnostic PRGs rebuilt. No VICE processes remain.

NEXT: cold-boot/lifetime delivery of this revised module, then real normal/panic
resident hooks/locks/marshalling link within padding (or further measured private
savings if needed). Do not call aggregate131 a proved link fit. Freeze capture
source and paste destination until READY; early drag cancels capture/falls back;
invalidate ownership before content/overlap/resize/restack/close/reuse/shutdown/
cancel. Retained READY pixels must survive ordinary move background repair.
Full live GUI/input/task/Z80/CtrlC/completion/overlap/pixel gates before enabling.

## Compact module delivery and real transport link — 2026-09-28

Read `docs/WINDOW-CACHE-COMPACT-DELIVERY.md` before the next increment.
NEW delivery proof qualifies the exact4,106-byte module INCLUDING its banked
196-byte gateway source. Earlier controller delivery was3,977 without source.
Normal production sources/links/disks are unchanged by this increment; cache
is still not installed or invoked. No new manual test. Do not merge partial
placement proofs into a claim of active GUI caching.

`tools/window_cache_compact_delivery.py` wraps the existing isolated recipe.
Parent build accepts qualified module_path/extra_inputs; module must be listed
in verified proof manifest. Wrapper verifies map/module/gateway hashes and
exact gateway suffix. Same scheduler source6000, LOAD4200, endpoint7229,
same strict operand/checksum deltas, zero new resident delivery bytes.
Cold boot D71/D64 in VICE3.10: exact4,128-byte slot through eight lifetime
checkpoints (boot/xinit/clock/wave/complete/utilities/shutdown/restart).
1986: exact slot both formats after32 wave drags each with clock running,
completed-wave cancellation and console-alive command. This is NOT a cached
move performance test. Test disks D71 sha5339634c... / D64 d2194468....
Full artifacts/results at `2026-09-28-window-cache-compact-delivery` bind
qualified compact inputs, canonical scheduler, all derived installers/maps,
disks, full raw captures, logs, provenance and run/report hashes. Four tests.

`tools/window_cache_resident_link.py` replays actual normal AND panic recipes
in isolation and retargets EVERY split file. Qualified sources raw51+seam309
(includes validator79 and state5)+diagnostic helper11 =371CODE; all added
objects zeroBSS/DATA/ZP/RODATA. Spend49scratch+42primitive+280shared padding;
131primitive padding remains. Outline8 untouched. These are ordinary CODE
segments: whole-link placement, not forcing each object into an independent
fixed padding hole. Every segment matches both baselines, exact shadow
A1E0-C11F8000, LOW/HIGHBSS, module/common/syscall regions unchanged. Runtime
helper module sets/sizes unchanged, UAPP ZP link assertions pass. Five seam
fields live in charged writable CODE with exact offsets0/1/3/4.

This closes REAL transport placement only. NO adapter/hook bytes charged yet.
Experimental binaries explicitly UNBOOTABLE because private provider addresses
move and derived import bridges are stale. Do not package/run them. No OS
entry/poll or manager callback references the new seam. State init is only
relevant once the integrated startup path exists. Artifacts
`2026-09-28-window-cache-resident-link` include real provider objects, source/
generated inputs, normal/panic maps, split binaries and before/after normal
provider/output hashes. Three tests. make check774 tests/checksums/pycompile
pass; container boot/all are up-to-date and placement-check passes. Normal
D71/D64 remain5dc9c2bf.../1fae5569.... No VICE sessions remain.

NEXT: real C compositor adapter/hook/lock sizing within131 residual padding
(or further measured private C savings if it exceeds). Then regenerate all
private bridges and package integrated isolated disks, acceptance/polls/init
and actual bounded row invocation. Source/destination frozen untilREADY;
early drag cancels capture/fallback. Invalidate before content/overlap/resize/
restack/close/reuse/shutdown/cancel, but keep READY image during own move's
background repair. Reconstruct original ticket after shared-workspace reuse.
Full live GUI/input/task/Z80/CtrlC/completion/overlap/pixel gates before enable.

## Integrated cached-move candidate — 2026-09-28

Read `docs/WINDOW-CACHE-LIVE.md`. This supersedes the previous NEXT sizing/link
step. User asked to continue until there is something testable: stop here for
manual visual/input feedback, not at another placement-only checkpoint.

Private sources live in `bench/window-cache-manager/{adapter,native}.inc` and
`tools/window_cache_manager.py`; packaging/qualification in
`tools/window_cache_live.py`. The generated private repository is
`build/window-cache-live/repo`. Normal build sources/outputs are not switched
to cache hooks. Exact disks to test: `udeks-cache.d64/.d71`, NOT the private
repo's ordinary boot disks. Preserve at
`bench/artifacts/2026-09-28-window-cache-live/build/` with matching results.

Local register pointers save521 bytes with complete host trace equivalence.
487 bytes of adapter/hooks yield netmanager−34: CODE7645, RO130, HIGHBSS88.
Full transport377 (371closure+6commandwrapper), no new BSS/ZP/helper; pad159.
All normal/panic segments remain exact, shadowA1E0-C11F. All private bridges,
checksum installers, managed apps and bootfs rebuilt through actual recipes;
both incremental and cleanparallel test disks agree. Normal D71/D64 remain
5dc9c2bf.../1fae5569.... Runtime/module/delivery allocation unchanged.

At most4 STEP rows/poll; each row releases MMU/runtime/IRQ ownership, dirty
pages commit once/batch. Source/destination locks prevent writes while capture/
paste is active. Early drag cancels capture/fallback. Move retains owner image
through background repair. Lower clock repair also skips cached owner and
pastes retained pixels; no app replay. Resident phase82 marks frontend repair
busy while banked phase remains2; next PASTE sets3 and finishes2. New clicks
defer during paste, pointer IRQ/keyboard/task polls remain active. Content/
resize/restack/create/destroy/reuse/reset/cancel take invalidation/fallback.

Both native formats:16 moves, all8 horizontal alignments, every17472 pixel
matches shadow AND VIC, painter count and21 Z80 leases unchanged, active clock,
partialpaint fallback, partialpaste CtrlC, oversized resize fallback, handle
reuse, typed/history/echo/shutdown/restart, RESTORE/CIA2 NMI pressure, guards.
VICE both formats: captured17472 pixels/full8000 shadow=bitmap, immutable source,
guard, NMI drain/handoff, shutdown/restart. Native VICE input/drag NOT qualified.
Private xwave status uses callback handle BEFORE initial painting, because
window_create calls painter before assigning the app's global handle; initial
diagnostic handle would otherwise stay0 when cached moves never call painter.
Native runner's PC Minus was C128 Plus; choose positional Equals for C128 Minus
so xinit-q test remains strict. Sibling1986 source is untouched.

Runtime slot is not byte-identical to uninvoked delivery: row core has two
selfmod address operands and4 scratch bytes. Live oracle permits only those8
bytes, validates operands against exact last row, and compares everything else
(controller/gateway/header/slack) exactly. Tests inject pointer/opcode/header/
padding changes to ensure failure. Full VSF containsROM and is NOT archived.

Sample release60–81 PALframes plus settledpaste139–164, roughly4–5s combined:
reuse is proved, responsiveness is NOT accepted. Next after manual feedback:
reduce synchronous background/clock and dirty commit cost, then consider normal
promotion. Physical RESTORE/Z80 routing remains open. No commit/push this turn.

Final qualification: make check781 tests/checksums/pycompile pass; normal
container boot/all are up-to-date and placement-check passes. git diff--check
passes. Test artifacts/results are preserved with immutable SHA256SUMS and
report-to-run bindings; no VICE sessions remain. Normal disk hashes unchanged.

## Live-cache manual feedback — 2026-09-28

User: "it all looks good to me." Record positive manual feedback for the
presented live-cache candidate; do not infer the platform, exact cases, physical
RESTORE/Z80 routing or a latency measurement. Preserved evidence is unchanged.
Normal cache hooks are still not enabled, and no commit/push was requested.

NEXT engineering gate: measure background-repair versus paste/commit cost,
including number of256-byte dirty-page copies per move. The current4-row batch
can recopy a tiled bitmap page across adjacent batches. Evaluate bounded
commit/row alternatives against the existing native-input/CtrlC/clock/fullpixel/
guard gates before normal promotion; do not just raise batch size without
measuring console latency. The previous "stop for manual feedback" is satisfied.

## Band-boundary repaint follow-up — 2026-09-28

User authorized the repaint work. Read `docs/WINDOW-CACHE-REPAINT.md`.
New tool `tools/window_cache_repaint.py` generates reference/tiled private links
via the live builder; baseline and old manual artifacts remain immutable.
New test disk is under `bench/artifacts/2026-09-28-window-cache-repaint-tiled/build/`
or `build/window-cache-repaint/tiled/udeks-cache.d64/.d71`. NOT private repo's
ordinary boot disks. Normal cache hooks remain disabled.

Keep max4rows/poll; end pasted batches at8scanline boundary and commit only
there/final/error. Read lastSTEP offsetF780 low3bits before another gateway;
IRQ/NMI don't borrow it. Partialbands staydirty. Source/destination locks and
row runtime/MMU/IRQ restoration unchanged. No newstate/helper/ABI/modulebytes.
ManagerCODE7677 (+32vsacceptedcandidate), RO130/HIGHBSS88, transport377,pad127.
All normal/panic segments and shadowA1E0-C11F remainexact; bridges regenerate.

Read-only native page-entry/stack-derived return breakpoints count real page
copies/cycles, continuing the same partialframe. Paired D71/D64 medians:
pastecopies56→22.5, copycycles709451.5→288659.5, pasteframes156.5→129.5,
release+paste220→194.5, CtrlC211→156. No maskinginput/IRQ or OS patches.
Worstpaste164→313 due coincident clockminute repair; DON'T claim worstcase
improvement or accept responsiveness. Clockpaint counter in log attributes it.
NEXT: visible-damage/occlusion-aware clock/background repair, not a larger row
budget; preserve pixel/input/cancel/guard/ownership gates and hardware gates.

Initial tiled run exposed realshutdown bug: D011ANDCF copied live rasterhigh
to targethigh; sampler target482 (>PAL312), phase1stuck, OS Return held although
physicalkey released. Fixed normal `vic_graphics.s` toAND4F, oneimmediatebyte
2328, no footprintgrowth. Both comparisonvariants usefix. Native tiledshutdown
at295 retains226 and keyboard/restart pass; reference238→200. Sanitized failure
disk/kernel/map/runner/log/state preserved; NO ROMbearing VSF in archives.
Source/arithmetic and failed-vs-fixed onebyte-diff tests lock the correction.
Normaldisks NOW d99463d6.../65a37c26... due this correctnessfix; older unchanged
hash statements describe earlier checkpoints. Newcache disks d1be51f9.../
af502122.... Incremental/cleanparallel tiled builds match.

Final measured clock attribution: native tiled move7 has2 clock paints during
release/paste and313 pasteframes; all other paired moves have1. Its actual
page-copy count69 includes extra clockbackground plus a second presentation;
do not filter that sample out. All paired and tiled native records pass both
formats; VICE both variants/formats pass capture/bitmap/NMI/restart. Archives
`2026-09-28-window-cache-repaint-{baseline,tiled}` preserve complete source/map/
disk/run bindings andcomparison; failure/manifest locks originalCF kernel to
fixed4F by exactonebytediff. No ROM-bearing snapshots archived.
make check787 tests/checksums/pycompile pass; normalboot/all/placement-check and
gitdiff--check pass. No VICE remains. No commit/push or cache-default promotion.

User feedback 2026-09-28: "looks ok" for the presented tiled repaint candidate.
Platform and individual test cases were not specified; this is positive manual
feedback, not physical-C128, RESTORE/NMI, or worst-case performance qualification.
Next engineering gate remains visible-damage/occlusion-aware clock/background
repair. No commit/push or normal-cache promotion is implied by this feedback.

2026-09-28 visible clock/background repair candidate:
`tools/window_cache_occlusion.py`, doc WINDOW-CACHE-OCCLUSION.md. Separate disks
only, normal images untouched. Generic geometry fast paths: disjoint damage
does not paste; fully hidden damage does not draw; full-width/bottom-covered
damage repairs only its exposed upper strip. Other overlaps keep bounded
background/paste fallback, now with damage limited to the requesting window.
Hidden clients receive one empty-clip callback to acknowledge the update;
otherwise clock previous-minute state would cause repeated repairs per poll.
No app-ID policy, app binary, public ABI, BSS or banked module changes.
Register private window parameters pay the cost. Linked manager CODE7695,
RO130/HIGHBSS88, transport377, heldpad87; all normal/panic segments/helpers
unchanged, shadowA1E0-C11F. Cleanparallel disks match incremental: D64d4e2a96c...
and D71e27ebf93.... Normal still65a37c26.../d99463d6....

Matched native date changes after exact native mouse drags (D71==D64):
clock fully hidden (109,40) 278→119 frames, 40→0 pagecopies;
upper4-row strip (109,65) 278→126, 44→2;
complex overlap (144,88) 267→254, 40→33. One callback/change, no repeat over120
frames, no wave painter/Z80 reacquisition. Every8000-byte case canvas matches
reference and bank0/bank1; retained17472pixel oracle passes. Original16moves
worst sampled settledpaste313→163, medianfullmove194.5→194 (NOT general speedup).
Complex overlap still~5s: next optimize selective partial-overlap repair.
Physical/input/RESTORE gate and normal cache promotion remain separate.

Host pixel oracle117 geometries + disjoint/highX/three-layer/uncovering;
nativeinput/earlydrag/16moves/partialpasteCtrlC/resize/guards/console/restart;
VICEbothformats capture/pixels/NMI/restart, NOT nativeVICEdrag qualification.
Read-only profiler ignores only identical-frame/register/SP entry redispatch
after IRQ/NMI (3 candidate,0 reference), preserving all interrupt cycles. Clock
timing ends only after leaseREADY AND emptydirtymap AND pagecallreturn.
Archives `2026-09-28-window-cache-occlusion{,-reference}` bind source/maps/disks/
runners/provenance/logs/pixels/comparison, no ROM-bearing snapshots. No push or
normal cache promotion; prompt user to test candidate disks next.

Final gate: make check793 tests/manifests/pycompile pass, normalcontainerboot/all
and actualobjectplacement-check OK, gitdiff--check OK. No VICE remains. User
reported "looks good" on 2026-09-29 for the presented occlusion candidate.
Platform and individual cases unspecified; record positive manual feedback,
not physical/input/RESTORE or universal responsiveness qualification.
Next engineering step remains selective partial-overlap repair. No commit/push
or normal-cache promotion is authorized by this feedback.

2026-09-29 prefix/row-range repair is implemented and emulator-qualified as
another isolated candidate; see docs/WINDOW-CACHE-PARTIAL.md. First qualified
the banked provider independently (`tools/window_cache_partial.py`), then its
C compositor adapter (`tools/window_cache_partial_manager.py`). Preserve both
archives under bench/{artifacts,results}/2026-09-29-window-cache-partial{,-manager}.

Private command0.2 adds op6, PARAM F78A first/F78B end-exclusive/F78C-D prefix
width. Validate before mutation; retain original geometry and source stride;
only rows[first,end) and the left prefix are restored. Outside pixels unchanged.
Range metadata3 initialized DATA bytes are charged INSIDE the module, not a new
allocation. Private fixed-lease policy rejects wrong pointers; generic normal
policy remains unchanged. Core213/common gateway196 byte-identical to prior
proof. Module3971, identityslack141, gateway source50BF (loader-derived; removed
VICE's hardcoded5146 source range). VCC2 layout0.1 unchanged; checksum/header and
validator rebuilt for exact new provider. Do not mix provider/validator versions.

Standalone host tests cover alignments/widths/ranges/rejection snapshots,
corrupt metadata, full paste after partial, cancel/recapture. Compiled1986/VICE
all64bit alignments +52prefix rows17..66 pass completepixel/dirtymap oracle,
IRQ/I-D/ZP/HW-SWstack/shell/guards/NMI and six negative controls. Raw/state
decoders have mutation tests and hash-bound source/maps/executables/results.

Manager reuses clipped top/bottom/right and marshals only AFTER callbacks finish
(sharedVICworkspace can be clobbered); resetclip before the command. Host tests
match all screen pixels/117placements +disjoint/highX/three-layer/uncovering and
deliberate callback argument clobber. CODE7750 (+55), RO130/HIGHBSS88 unchanged,
transport377, heldpad32. All normal/panic segments/helpers exact. Clean private
parallel build equals incremental D64 13433b995d.../D71 fded272e8e.... Normal
still65a37c26.../d99463d6.... No source change in1986; no normal cache promotion.

Native bothformats: hidden119frames/0pages and upperstrip126/2 unchanged;
partial-overlap254/33 ->195/23 (~23%faster). Whole8000byte canvases match the
saved occlusion reference, same emulator provenance. One callback/change, no
repeat120frames, no wave painter/Z80 reacquisition. Same native earlydrag,
16moves, partialpasteCtrlC, typing, resizefallback, guards/NMI/restart pass.
VICEbothformats capture/fullpixels/NMI/restart, NOT nativeVICE dragging.
195frames remains~3.9s: no general responsiveness claim. Next after manual
feedback: bound/reduce synchronous lower-window composition, not more row
budget or larger cache. Prompt user to test this disk; physical/input/RESTORE
and default-promotion gates stay separate. No commit/push requested this turn.

Final qualification: make check803 tests +all preserved manifests/pycompile
pass; normalcontainer boot/all up-to-date and actualplacement-check OK;
gitdiff--check OK; no x128 sessions remain. Candidate archives/comparison/
clean-build proof saved. Subsequent feedback below supersedes the untested status.

2026-09-29 user rejected prefix candidate: considerable xclock drag-start delay.
Native reproduction exposed a missing case: xclock over completed xwave takes
265 PAL frames before outline (5.3s), clock alone17. Old suites moved xwave,
not xclock-over-wave. This is synchronous 8502 background wireframe replay,
not a new Z80 job or a mouse-driver regression. User approved temporarily blank
background while dragging, repairing it after release.

Isolated deferred candidate qualified; docs/WINDOW-DRAG-START.md. Existing
compositor gains private erase-only selector255; begin invokes no painters.
Valid CACHED_MOVE preserves image ownership; release repairs full old/new union.
Manager7762 (+12), RO130/HIGHBSS88, transport377, heldpad20; all normal/panic
segments/helpers unchanged. Cleanparallel private disks identical; normal still
65a37c26.../d99463d6.... Native D71/D64 clock-alone17 unchanged, overlap265→16
frames (~0.32s); gate<=30, mouse outline movement, no newZ80, fullshadow/VIC,
CtrlC+console typing+shutdown. Full prior native16move/cancel/resize/guards/NMI/
restart and VICEbothformats pass. Host releasecanvas matches prior after move,
resize, destruction during drag and cachedwave move; forcedclock canvases exact.
Release/background composition remains synchronous: no universal speed claim.
Archives2026-09-29-window-drag-start include timing source/runners/logs vs previous
prefix archive and clean-build proof, no ROM snapshots. D644872d6aa...,
D71e3eaa384.... Prompt user to test this separate disk next; no commit/push,
physical qualification or normal cache promotion authorized by this feedback.

Final gate for deferred drag: make check808 tests/manifests/pycompile pass;
normalcontainer boot/all up-to-date and actualobjectplacement-check OK;
gitdiff--check clean; normal disk hashes unchanged; no x128 sessions remain.

User feedback on deferred-drag candidate: "ok much better now, continue".
Record positive manual drag-start feedback, platform unspecified, not physical
qualification or normal-cache promotion. Next reduce the synchronous exposed
background replay after release; preserve fast outline start and input gates.

Architectural direction from user: projection/wireframe optimization belongs
to xwave, NOT the entire windowing system. Preserve this boundary in future
work. App owns samples/projection/render caches; manager stays generic about
composition/damage/clipping/stacking. The app-local projection prototype and
its tools/tests/evidence remain separate from this window-manager milestone.

2026-09-29 merge scope approved by user: commit the generic manager foundations,
tests and opt-in evidence; exclude the xwave projection experiment and its
app-transform build hooks. Do not enable caching/deferred dragging in normal
builds as a side effect of merging. Keep the minimal xwave image-completion
notification needed by the generic UAPP contract, not an app-specific cache.
Next: default-build delivery/integration as explicit manager work, then fresh
native keyboard/mouse/CtrlC/resize/RESTORE and physical acceptance gates.
See docs/WINDOW-MANAGER-MILESTONE.md for scope and outstanding limitations.

Scoped clean-worktree merge gate: make check808 tests/manifests/pycompile pass;
fresh parallel make boot/all and realobjectplacement-check pass. Default disks
are byte-identical to the previously qualified normal image (D6465a37c26...,
D71d99463d6...). Xwave projection tools/tests/images and build hooks excluded;
default cached/deferred dragging remains disabled. User approved this scope.

2026-09-29 issue #12 / graphics-window-manager-integration: the next manager
step now has a regular source-built WINDOW_CACHE=1 configuration. It promotes
the accepted generic compositor and bank-1 controller under the window service,
regenerates identity/checksum/page/gateway bindings from the actual link, and
rejects any normal/panic segment drift before packaging. Manager7762/RO130/
HIGHBSS88, charged transport377, heldpad20, shadow$A1E0-$C11F; no published
runtime or scheduler destinations move. Disk LOAD$4200 is distinct from USOV
temporary source$6000; a boot regression caught and corrected conflating them.

Default WINDOW_CACHE=0 remains off. Fresh source-only parallel builds and
1->0->1 switching reproduce both selected disks and the old default hashes.
No archived binary or app-transform path is needed. Xwave projection work stays
local/separate; no app BSS or projection table is added by this integration.
Runtime-only probes avoid the local xwave private-builder hooks.

Actual selected D71/D64 pass native1986 input/history, early/cached moves,
overlap repairs, oversize resize fallback, partial-pasteCtrlC, console typing,
guards/NMI and shutdown/restart; VICEbothformats fullpixels/NMI/restart pass.
Evidence under bench/{artifacts,results}/2026-09-29-window-cache-integration.
Selected D64c00d8936..., D7100ab0c99...; stable manual copies remain under
build/window-cache-integration/udeks-cache.{d64,d71}. See
docs/WINDOW-CACHE-INTEGRATION.md for build commands and manual acceptance.
Background release repair stays synchronous/slow; native VICE mouse and physical
input/RESTORE acceptance remain open before changing the default policy.

Final selected-build gate: make check825 tests/manifests/pycompile pass
(including the four still-local xwave projection tests; integration does not
use that prototype). Actual selected clock-only/clock-over-wave drag starts
are17PALframes in both formats, with a <=30 guard, outline motion, drained
repaint/fullshadowVIC, CtrlC+typing+shutdown. Timing evidence is separate from
the full compositor suite. A fixed300frame sample caught a subsequent periodic
clock commit; the read-only observer now waits for the dirty map to drain.
Immutable integration manifests bind inputs/runners/logs/pixels/clean switching.
Default build outputs restored to65a37c26.../d99463d6..., actualplacement OK;
integrated manual copies retained. No commit/push or default promotion yet.

2026-09-29 user feedback on the selected integration: "it looks ok on real HW".
Record positive overall physical-machine manual feedback. No itemized hardware
log, format/hash confirmation or explicit RESTORE/input-afterward result was
provided; do not infer those or authorize a default change/commit/merge from
this report alone. RESTORE + subsequent input confirmation was requested;
the subsequent report below resolves that gate. Keep xwave work separate.

2026-09-29 follow-up hardware confirmation: the user pressed RESTORE while
dragging a window on real hardware and input still worked afterward. Together
with the preceding positive overall feedback, this closes the requested manual
integration acceptance gate. Do not ask for that check again or infer exhaustive
physical NMI-source/Z80-handoff coverage. WINDOW_CACHE=0 remains unchanged until
promotion is approved. Recommended next: promote the accepted configuration,
commit/push the scoped window-manager work and review/merge via PR, keeping the
local xwave projection experiment out of that scope.

2026-09-29 user approved default promotion, scoped commit/push and PR merge.
WINDOW_CACHE now defaults to1; explicit0 retains the old compositor. Integration
contains no xwave projection tools, table, app changes or prototype evidence.
Historical opt-in qualification archives are immutable. Verify a fresh scoped
default build against their accepted D64/D71 hashes before publishing. Requested
hardware acceptance is complete, not exhaustive physical NMI/Z80 coverage.
Next manager work: bounded release/background composition, which is still
synchronous and slow; keep application-specific rendering outside the manager.
Scoped promotion gate:821 host tests pass; clean parallel default boot/all/panic
and placement-check pass. Default→0→default without clean reproduces selected
D64c00d8936.../D7100ab0c99... and prior65a37c26.../d99463d6... exactly. The kernel
dfef7e6d... and module758965e4... match the archived qualified integration.
