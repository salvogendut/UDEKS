# Disk-loaded graphical applications

The initial extraction checkpoint below is historical. For current namespace
and calculator usage see [Calculator addition](#calculator-addition-branch-app-xcalc)
and [the roadmap](ROADMAP.md).

## Four-application support (#30)

Accepted work: [issue #30](https://github.com/salvogendut/UDEKS/issues/30),
checkpoint `c05a011`, based on calculator commit `5cd34f9`.
**Four-app candidate:** `xclock &`, `xwave &`, `xcalc &`, and `xdraw &`
coexist. Calculator and drawing are separate ordinary native C tasks in bank 1,
using the owner-bound graphics bridge. Shell foreground/background control,
targeted Ctrl+C, desktop shutdown and the running-app panel cover all four.

The bounded transition keeps clock/wave in bank 0 and introduces
two bank-1 graphical clients. It does not page whole programs through the
calculator's execution address on every poll or paint. Checked reservations:

| Client | Image + BSS | Private software stack reservation | Relocated CPU pages |
| --- | --- | --- | --- |
| Clock (existing) | bank 0 `$0200-$0BFF` | Existing resident managed-call stack | Existing kernel pages |
| Wave (existing) | bank 0 `$1200-$1BFF` | Existing resident managed-call stack | Existing kernel pages |
| Calculator (implemented) | bank 1 `$2300-$34FF` (4,608 bytes) | `$8A00-$8CFF` | `$D500-$D6FF` |
| Drawing (implemented) | bank 1 `$3500-$3FFF` (2,816 bytes) | `$8D00-$8FFF` | `$D700-$D8FF` |

Each new stack reservation now contains 672 usable bytes, two 16-byte guards
and a 64-byte return trampoline; it is not 768 usable bytes. The boot-only data left
in the Z80 padded container is disposable only after native boot has consumed
it. The current Z80 code is 663 bytes at `$2000-$2296`, with no data allocation.
This layout narrows its old 8 KiB growth reservation; future code/data growth
into either client allocation must fail the build, not silently corrupt an app.
Existing foreground commands, shell, storage policy, cache and native task
pages are not repurposed. Native task IDs and window owners must be explicitly
bound, not assumed interchangeable.

Run `distrobox enter my-distrobox -- make -j8 graphics-apps-check placement-check`.
The gate reads real maps and UDEX images, verifies Z80 HEX against its padded
binary, checks physical-bank overlaps (including zero-page/hardware stacks),
and emits `build/four-apps/layout.json` with input hashes. Banked xcalc uses
3,912 image bytes plus 412 BSS bytes, leaving 284 bytes in its allocation.
Xdraw uses 1,477 image + 354 BSS bytes, leaving 985 bytes.
Resident bridge headroom is also reported; exceeding either
budget requires a placement revision. The accepted calculator disks remain
preserved in `bench/artifacts/2026-09-30-xcalc`.

Implementation sequence:

1. **Implemented:** placement gate and four-owner manager regression. A fifth
   window leaves the four descriptors unchanged; invalid/wrapping coordinates
   reject before mutation. Focus/click/drag/close dispatch and handle reuse
   are tested in both real C manager variants. The private resident owner query
   is not a public UAPP extension. These tests run four windows, not four apps.
2. **Implemented:** bounded bank-aware delivery and graphics request/event routing.
   Delivery and native execution now pass with two independently linked C
   clients. Calculator exercises the retained drawing/click/close interface.
   Marshal coordinates, geometry, titles and input; never store a foreign-bank
   title pointer or execute a foreign-bank paint/close pointer directly.
   Banked clients need explicit repaint/input/close events and owner-checked
   drawing. Establish correct compositing of overlapping clients, including
   partial/hidden damage; do not publish a cross-bank begin/end-paint lease
   that lets another app draw before its owner has finished. Closing or failed
   loading must retire events/windows before releasing an allocation.
3. **Implemented:** separate `XDRAW.BIN`, indexed banked lifecycle, shell target
   6, foreground bit 8, and an expanded panel for desktop plus four apps. Four-app
   state/drag/close/reload, invalid/fifth-load rejection, console and Ctrl+C pass
   on both VICE disk formats; native 1986 D64 input passes too.
4. **Accepted:** user confirms the candidate works on real hardware and
   authorizes merging. Next: the disk-loaded service slice.

This is bounded four-client support, not arbitrary-size executables, general
dynamic relocation or memory protection from hostile machine code. No
xwave algorithm or generic rendering optimization is bundled into this work.

### Four-app usage and graphics bridge — current candidate

Fresh `build/boot/udeks.d64` and `.d71` support this sequence, with device 8
already mounted as `/` by normal boot:

```text
xclock &
xwave &
xcalc &
xdraw &
cowsay hello
free
```

Move the clock left before launching the later apps to keep it exposed.
Drag/raise/close each window and use the calculator buttons. Xdraw has a 6×4
grid: click a cell to toggle ink, or its C button to clear all cells.
`xcalc -q` / `xdraw -q` stop only that app; reloading resets its private state.
An app launched without `&` is foreground, so Ctrl+C stops it while the three
background peers survive. `xinit -q` closes all four and shuts down the display.
Calculator/drawing windows are fixed-size. Repaints remain slow; wait for a
button action to finish before clicking the next one. The native harness waits
for sampled press/release edges rather than assuming a fixed 150-frame delay.
The user reports "everything looks fine also on real HW" and authorizes merging;
this records the requested functional hardware acceptance gate. The report does
not identify the machine variant, drive, or disk format.

Arithmetic, glyphs, layout and button logic remain in `XCALC.BIN`; the grid and
its state live in `XDRAW.BIN` (up to 41 drawing commands). The service
retains generic drawing commands and replays them at the current window origin
under the existing compositor's damage/client clip. It never invokes a callback
in the client's bank or holds a cross-task painting lease. See
[UTRQ 0.9](../abi/window.md#banked-clients-utrq-09) for the bounded interface.
Invalid submissions leave the committed image intact. Close retires the window
before the cooperative client exits and is reaped; a live task is never forcibly
released. This is a trusted cooperative design, not process memory protection.

Placement is build-checked in both normal/panic links:

- Bank-0 graphics module `$0C00-$11B8` (1,465 bytes in a 1,536-byte output),
  helper `$A100-$A1CE` (207 bytes), plus lifecycle glue in resident CODE.
  The low module installs lazily on first banked-client launch, after bootstrap's
  `$0C00` activation backup is dead; clock remains at `$0200-$0BFF`.
- Delivery image in bank 1 `$C700-$CCFF`, private retained command buffers
  `$CD00-$CFFF`. Filesystem policy is now bounded below `$C700`.
- Private loader/access module `$D900-$DFFF`: all 1,792 bytes used. Its added
  kernel-only helpers install the low module, copy eight bytes and read current
  task/state. These are not caller-provided raw-pointer syscalls.
- Resident BSS ends `$9AD2`: 45 bytes remain before LOWBSS. Direct indexed
  client-state arrays, service constants in MODULERODATA and lifecycle helpers
  in GRAPHICSHELP fit both clients within the existing reservations. The high
  module ends `$E633` (16 spare bytes); no memory boundary was extended.
- `free` reads the explicit task-2 state in diagnostic UTSK 0.2, rather than
  treating every live graphics task as a foreground-pool allocation.

Reproduce with the container build above, then host `make four-apps-probe`.
This runs VICE D64/1541 and D71/1571 lifecycle/input-routing tests and separate
missing/bad-magic/wrong-slot/oversized-BSS/fifth-image rejection checks. Four
live executable images and retained drawings survive rejection byte-for-byte.
VICE input is injected at the WM queue/getters. For native keyboard/1351 input:

```sh
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --emulator ../1986 --roms ../1986/roms --four-apps \
  --output build/four-apps/native-input-d64
```

Both input paths cover arithmetic/drawing, drag, independent close/reload,
console commands, Ctrl+C, shutdown, guards and completed shadow/bitmap equality.
Host tests cover ownership, atomicity, both indexed lifecycles and four-job
accounting. Clean parallel builds reproduce both disks and banked executables.

Evidence: `bench/{artifacts,results}/2026-10-01-four-apps`. Published
`build/udeks.*` release snapshots intentionally remain unchanged.

### Banked delivery checkpoint (historical load-only qualification)

The initial assembly loader ran in bank 1 at `$D900-$DD07` (1,032 bytes), within
the reserved `$D900-$DFFF` range, under the worker-flat MMU profile. Its image
uses previously zero padding in the existing secondary boot file: the LOAD
envelope and disk-file length do not grow. The resident C image and its
651-byte headroom are unchanged. This is a module, not new kernel C policy.

Private kernel-only `$F91C` accepts selector 3 or 4 and the existing 38-byte
UTRQ record with count 17: a length byte followed by a zero-padded 16-byte
basename. It resolves `/bin/name` via the normal filesystem; no new public
syscall or UAPP version is advertised. `$83/$84` release an idle allocation.
Task 2 and the selected task 3/4 lifecycle slot must be FREE. An owned image
cannot be replaced, even while its native context has not been activated.

The file is staged directly in its **unowned** destination. The 16-byte UDEX
header counts against the staging capacity; after validation, the image moves
down by 16 bytes and BSS is cleared. Exact EOF, magic/version/CPU/flags,
load/entry address, six callback JMP targets and image+BSS bounds must pass
before ownership is published. A failed load may dirty the free destination;
it does not alter a live peer or publish an allocation. All opened paths close
the file and preserve the complete caller request, including its sequence.
Release clears ownership/header metadata; it is not a task-cancellation API.
Future execution integration must retire windows/events before releasing.

The bank-switch/disk/state bridges fit in existing common reservations:
TASKLOADER uses 1,389/1,392 bytes and BOOTINIT 126/128. The old boot-only
42-byte activation backup now uses bank-0 `$0C00-$0C29`, only between disk-shell
selection and restoration of the scheduler activator. It is dead before
managed apps start; later calculator overwrite is explicitly regression-tested.
Published `$F910/$F913/$F916/$F919` and `$CF30/$FF16` entries stay unchanged.

Reproduce after the container build with host `make banked-apps-probe`.
The probe uses a one-shot normal kernel-poll hook, not arbitrary CPU takeover.
It loads inert managed fixtures (not graphics clients), checks both full-slot
boundaries, malformed files, missing files, name validation, stopped/zombie
guards, request/map preservation, independent ownership and release/reload.
Clock and wave run on their existing paths while the two additional images
are held in RAM; console commands and subsequent calculator launch must work.
**Do not call the old UAPP callbacks from these bank-1 images.** Native task
activation is implemented below; owner-checked graphics/events remain next
before calculator and the fourth graphical client can use these allocations.
Both VICE disk-format probes and the existing calculator regression pass;
1,032 host tests and a clean deterministic parallel build pass. Exact images
and records are preserved in `bench/{artifacts,results}/2026-10-01-banked-loader`.
This checkpoint has not been newly tested on 1986 or physical hardware.

### Native banked C execution (earlier checkpoint)

At this checkpoint the bank-1 module occupied `$D900-$DF62` (1,635 bytes); its 1,792-byte
reservation and the resident C image are unchanged. TASKLOADER/BOOTINIT use
1,389/124 bytes. All public syscall entries and UAPP 0.4 remain unchanged.
Private `$F91C` gains the following kernel-only operations:

| Selector | Effect |
| --- | --- |
| `$03/$04` | Load and validate task 3/4's image, without running it |
| `$43/$44` | Activate a loaded ordinary UDEX image (flags 0) |
| `$83/$84` | Release a FREE allocation, including stale context/wait metadata |
| `$C3/$C4` | Reap a root-owned ZOMBIE and release, or finish release after WAITPID |

Task 2 must be FREE during these calls. The selected task must be FREE except
for zombie reap; live release/reap is EBUSY. Activation binds parent task 1,
requires that parent to exist, initializes CPU/runtime state, then publishes
RUNNABLE last. Already activated images cannot restart without release/load.
Wrong-parent and unowned zombies are rejected. Managed flag-2 images still
load for validation but cannot execute through this path (ENOEXEC).

Ordinary programs have their own linked cc65 runtime (`sp` at relocated
`$02/$03`), unlike the bank-0 UAPP runtime. Software stacks are
`$8A10-$8CAF` and `$8D10-$8FAF`; hardware stacks and zero pages use the physical
bank-1 pages in the table above. Each has a private synthetic return address
and trampoline. A normal C return becomes EXIT through existing `$FF16`;
YIELD and SLEEP also use that existing scheduler boundary. The private bridge
only accesses build-verified lifecycle/context addresses, with IRQs masked.
It is not a user pointer API or isolation against hostile machine code.

Qualification compiles two different 661-byte C images (7 BSS bytes each),
both entered at image base + 2. Recursive automatic arrays remain live across
SLEEP at varying depths; per-client counters and DATA/BSS are checked after
interleaved YIELD/SLEEP. Both guards and the CPU-stack canary survive, exit
statuses are 43/44, and reaping clears every lifecycle/context/wait field.
Reload restarts from fresh DATA/BSS. Legacy clock/wave and disk console
commands work while these tasks run. This is actual compiled C execution,
not four graphical apps, a native input test or a performance benchmark.

Reproduce with:

```sh
distrobox enter my-distrobox -- make -j8 boot graphics-apps-check placement-check banked-native-fixtures
make banked-native-probe
python3 tools/xcalc_probe.py --output build/four-apps/native-legacy-regression
```

Exact images and D64/1541 + D71/1571 VICE results are preserved in
`bench/{artifacts,results}/2026-10-01-banked-native`. A separate clean parallel
build reproduces both disks and both C executables; 1,038 host tests pass.
No new 1986 or physical
hardware qualification is claimed; published `build/udeks.*` stays unchanged.

Remaining feature work: owner-bound graphics/events and close/cancellation,
calculator relink, fourth executable, shell/panel integration. Before exposing
these tasks to normal users, replace `free`'s current task-count heuristic
with actual task-2 allocation accounting: other live tasks do not make that
foreground allocation busy. Guards are checked by this probe; this increment
does not add an automatic runtime stack-overflow trap.

## Historical disk-extraction checkpoint (#22)

Issue [#22](https://github.com/salvogendut/UDEKS/issues/22), branch
`storage-disk-graphics`, follows merged PR #21. Normal D64/D71 images contain
closed SEQ `XCLOCK` and `XWAVE` files: raw UDEX bytes without a PRG prefix.
Neither application is bundled in normal bootfs anymore. Recovery commands,
the recovery shell and preloaded services remain transitional; this is not
yet the final kernel-only boot model.

## Try it

Cold boot a current image (default RC mounts device 8 at `/mnt`), then:

```text
ls /mnt
xclock &
xwave &
```

Move, resize and switch between the windows; type `cowsay hello` in the VDC
console while both run. Stop with `xwave -q`, restart with `xwave` (no `&`),
then press Ctrl+C: the clock should keep running and the prompt return.
Repeat from a cold boot with wave before clock. `xinit` remains optional:
either application initializes the graphical desktop when needed.

First launch needs `/mnt`; without it, the current `request failed` message
returns to a usable prompt. Mount and retry. Stopping does not unload an app;
subsequent starts use the retained image, even if media is removed. Reboot to
test a changed file. Optional automatic startup belongs in disk `RC`:
append `xclock &` and `xwave &` after the default `mount 8 /mnt` line.

## Implementation boundaries

- Existing common gate `$F916` delegates disk read/validation to the private
  bank-1 loader extension. No new public ABI or service placement.
- Clock must target bank-0 `$0200-$0BFF`; wave `$1200-$1BFF`. Each has six
  absolute JMP callbacks; every target must lie after its table and inside
  its own image, not in BSS or the other app. Exact EOF/header/size/BSS and
  flags checks complete before any live destination write.
- Staging borrows bank-1 task 2 only while FREE. Rejected busy loads leave
  that allocation and its common launcher untouched, including STOPPED and
  ZOMBIE ownership. This is a synchronous compatibility loader, not a new
  scheduler, allocator, or arbitrary executable sandbox.
- No app, window-manager, rendering, input-driver or Z80 algorithm changes.
  Existing retained-code, foreground/background and cancellation semantics
  remain. First-load IEC latency is expected; optimization is separate work.
- The failure tail now establishes the CPU zero flag from its nonzero error
  result, not zero X. Otherwise the assembly managed caller could enter old
  slot contents after a missing/invalid file. Negative live tests cover this.

## Repeatable checks

Build with `distrobox enter my-distrobox -- make -j8 boot disk-exec-image panic-probe placement-check`.
Run `make check` on the host, then:

```sh
python3 tools/managed_disk_probe.py --faults --output build/disk-graphics/vice-faults
python3 tools/managed_disk_probe.py --drive 1571 --disk build/boot/udeks.d71 \
  --first xwave --output build/disk-graphics/vice-wave-first
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --emulator /var/home/salvogendut/Dev/1986 \
  --roms /var/home/salvogendut/Dev/1986/roms --disk build/boot/udeks.d64 \
  --disk-shell --sysinfo --disk-graphics --output build/disk-graphics/1986
```

VICE feeds normal terminal key events, checks both launch orders, disk/code
identity, missing mount/media entry, malformed headers/callbacks, atomic
rejection with a running peer, and retained restart without media. The busy
case deliberately seeds STOPPED/ZOMBIE ownership; it is not a native child
creation test. The 1986 harness uses native keyboard/1351 events and raw IEC
against unmodified emulator sources. No physical-hardware acceptance is
inferred from these checks.

## Candidate checkpoint — 2026-09-30

VICE true-drive D64/1541 (clock first, 13 file faults plus busy ownership)
and D71/1571 (wave first) pass. Native 1986 revision `43d7dce` passes raw-IEC
loading, clock drag/resize, wave drag, foreground Ctrl+C, both-app console
use, stop/restart and media recovery. Existing disk-exec, RC-started clock,
free/df and real compiled SPAWN/EXIT/WAITPID regressions pass. A clean parallel
build reproduces both normal disks, the panic disk and the D64 disk-exec fixture
byte-for-byte. The shadow-clear/bitmap check uses mounted disk apps now.

TASKLOADER uses 1,362/1,392 bytes before BOOTINIT; TASKLOOKUP 1,138/1,536.
Normal bootfs now uses 8,016/12,544 bytes. This recovers bootfs content space,
not resident kernel RAM, and does not shrink the fixed secondary envelope.
The app and resident kernel image binaries are unchanged; only loader/delivery changes.
Managed programs must be invoked through `xclock`/`xwave`; explicit
`/mnt/XCLOCK` is not an ordinary foreground executable (its managed flags are
deliberately rejected by that path).

Exact candidate images and records are preserved under
`bench/artifacts/2026-09-30-disk-graphics` and
`bench/results/2026-09-30-disk-graphics`. Manual acceptance of this candidate
in 1986 and/or on hardware is unrecorded. The user subsequently authorized
review/merge and continuation with utility and command-layer extraction;
that authorization is not a physical test result.

## Calculator addition (branch app-xcalc)

`xcalc &` loads `/bin/xcalc` from `XCALC.BIN`; no manual mount is needed.
Use its mouse buttons for +, -, multiplication, division, decimal entry,
sign change (+ over -), equals, and C (clear). Two fractional digits are
retained; extra fractional input is ignored and results truncate toward zero.
The supported range is -200000.00 through 200000.00, with a bounded signed
32-bit multiplication intermediate. E1 means division by zero; E2 means
overflow. C clears an error; entering a digit also starts a fresh calculation.
Operations chain left-to-right, not with expression precedence.

The first version is fixed-size, movable and closable, with black-on-yellow
graphics. `xcalc -q` stops it; `xcalc` without & is foreground and Ctrl+C at
the VDC console closes it. Keyboard calculator entry, percent, square root
and scientific functions are later work. No Z80 is needed for this workload.

In that earlier `app-xcalc` build the calculator occupied enlarged bank-0 slot 1 and was mutually exclusive
with xclock: stop/close one before starting the other. A live peer produced
`slot busy`, without overwriting its code. xwave could coexist in slot 2.
The current three-app candidate above supersedes this restriction.
Arithmetic and UI are entirely in the disk image; the resident change is
bounded click delivery and lifecycle/ownership routing. See
[UDEX placement](../abi/executable.md). No general allocator is implied.

Acceptance tools: `tools/1986_storage_smoke_build.py --xcalc` tests actual
keyboard/1351 input against the unmodified sibling emulator;
`tools/xcalc_probe.py` tests VICE true-drive D64/D71 boot, loading, arithmetic
through an injected WM click queue, slot exclusion, console operation and
shadow/bitmap equality. The latter does not claim native VICE mouse coverage.
Fresh candidate images are `build/boot/udeks.d64` and `build/boot/udeks.d71`;
the published `build/udeks.*` snapshots stay at the accepted main release.
