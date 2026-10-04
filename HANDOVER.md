# UDEKS engineering handover — Tasking 0.1 and graphics bring-up

This records the Tasking 0.1 implementation plan as of 2026-09-27 and later
engineering checkpoints. It is retained for reproducibility and handover, not
as the current priority list. The [roadmap](docs/ROADMAP.md) now sets the next
feature milestones; [PLAN.md](docs/PLAN.md) remains the architecture and ADR
0007 remains authoritative about the resident-core boundary.

## Current feature handover — 2026-10-04

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
