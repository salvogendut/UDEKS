# An independent graphical app (development SDK)

Issue #35 supports **four generic native allocations**. Build once, install a
`.BIN`, then use `name`, `name &` or `name -q` without an OS name-table entry.
All four bundled graphical programs use this path. Allocation is size-based;
not every program fits every slot. Native arguments and interactive
background-console stdin are still separate work.

## Bounded Z80 requests (UTRQ 0.11)

Independent native programs can now request the same bounded worker operations
as the old wave demo, without importing bank-0 UAPP functions or opening a
window. Build with `--graphics-abi 11`, include `worker.h`, fill the four-byte
request and call `worker_request()`. Zero means success; other returns are
errno values. [Exact arguments, results and lifetime](../abi/task-request.md#bounded-worker-011).

For one surface row, set payload bytes to `5, row, 1, 25`. On success **copy
the 25 bytes from `udeks_worker_output` into private memory before making any
other request or yielding**. The shared scratch buffer is not a retained app
image. Yield between rows to keep input and peers running; moving a window
must reuse saved app data rather than resubmit computation.

`make native-worker-probe-app` builds `user/examples/worker_probe.c`, a console-only
qualification client, using the same independent native builder. Its monitor
driver is `tools/native_worker_probe.py`; it is not an interactive end-user
command. Two copies run in different allocations, check bounded errors and
all surface samples, survive other users of the worker, then exit/reload.
General background-console stdin/argument handling remains separate work.

## Try the candidate

Cold-boot a fresh `build/boot/udeks.d64`, `.d71` or `.d81`. Device 8 is
mounted as `/` at startup:

```text
xclock &
xwave &
xcalc &
xdraw &
cowsay four apps alive
```

Move, raise, close and reload each window. Clock and wave resize after releasing
the outline; calculator and drawing intentionally use fixed-size layouts.
A fifth launch reports `task slot busy` without disturbing peers.
`xinit -q` closes the desktop and its apps. `name -q` closes the first matching
live instance (not every duplicate). Bare `name` owns the foreground; Ctrl+C
at the VDC console closes only that instance, leaving background apps running.

Build/install HELLO using the commands below, then run `hello &` four times
on an empty desktop. Each window has independent clicks and state, although
all four use identical executable bytes. The name and slot are not compiled
into the system. Close boxes retire instances; reloading clears their private
state. Graphics initializes on CREATE, not merely on native program admission.

## Build and install without rebuilding UDEKS

The example source is [`user/examples/xhello.c`](../user/examples/xhello.c).
It uses the existing owner-checked [graphics requests](../abi/window.md),
returns on close and sleeps between events. There is no task number, load
address, named service-control ID or resident callback in the C source.

```sh
distrobox enter my-distrobox -- make graphical-example
cp build/generic-apps/example/HELLO.BIN build/generic-apps/example/SECOND.BIN
python3 tools/add_disk_apps.py --disk build/boot/udeks.d64 \
  --output build/generic-apps/my-apps.d64 \
  build/generic-apps/example/HELLO.BIN build/generic-apps/example/SECOND.BIN
```

The first command compiles/links only the example and its runtime; it does not
link the kernel. The installer accepts arbitrary portable `NAME.BIN` filenames,
writes a **new** disk copy and refuses existing outputs or filename collisions.
It preserves the executable byte stream as a closed CBM DOS SEQ file, with no
PRG load prefix. D71 and D81 work identically. Never rename a host `.BIN` to `.PRG` or
prepend a load address. Use fresh output names when repeating installation.
The installer checks the UDEX signature; the runtime loader still performs
the complete executable/relocation validation.

For your own program, use the build recipe in
[`tools/build_graphical_example.py`](../tools/build_graphical_example.py):
compile C, assemble `native_graphics_entry.s` and `graphics_request.s`, link
with `cfg/8502-reloc-app.cfg` and the private cc65 runtime, then use
`o65_to_udex.pack_o65` with the exported `_udeks_program_entry`. The extra
`_hello_clicks` export exists only for this example's test; replace/remove it
for your program. The fixed `$1000` link base is a relocation convention, not
an app slot assignment. Never scan instruction bytes to infer relocations.

The builder also accepts arbitrary sources and filenames directly:

```sh
distrobox enter my-distrobox -- python3 tools/build_graphical_example.py \
  --source /absolute/path/to/myapp.c --source /absolute/path/to/model.c \
  --name MYAPP --output build/myapp
```

Repeat `--source` for each C translation unit (unique basenames); the default
HELLO-specific export is omitted for custom sources. Optional `--export SYMBOL`
retains a diagnostic symbol in the app's map, not a binding to the kernel.

## Earlier native-clock migration candidate (historical)

The following commands/results describe the earlier two-native-slot build.
The current default XCLOCK.BIN uses the same public API and the four-slot layout above.


On branch `graphics-native-clients`, `make native-clock` builds an independent
relocatable clock as **NCLOCK.BIN**. It shares no app callbacks, fixed task id or
private runtime symbols with the resident system. Both generic slots accept
the exact same 2,770-byte file (2,180 image + 369 BSS bytes; staging includes the
relocation table). All face/tick/hand/digit calculations stay in the disk app;
the existing graphics service retains 43 ordinary commands. The app reads the
same common TIME snapshot as `date`, updates on a changed minute or size, and
sleeps between event checks. It does not re-submit its image merely on a move.

Test **`build/native-clients/resize-demo.d64`**, `.d71` or `.d81`:

```text
nclock &
clock2
```

The windows initially overlap: drag the top clock aside. Ctrl+C at the VDC
console closes only `clock2`; `nclock` remains. Then:

```text
clock2 &
date 214500
cowsay clocks alive
xinit -q
```

Both clocks should show 21:45; either close box retires that instance and its
slot can be reused. `NCLOCK.BIN` and `CLOCK2.BIN` contain identical bytes. These
are deliberately separate test filenames: **shipped `xclock`/`xwave` remain
unchanged**, so there is no concurrency or resize regression in normal builds.
Drag each lower-right grip to resize it: the outline moves while contents are
hidden, then the app scales its own face to the new size. UTRQ 0.10 reports
owner-checked geometry events; the graphics service contains no clock model.
No `nclock -q` support is implied.

VICE D64/D71/D81 qualifies both slots, an independent drawing oracle, `date`,
dragging, independent growth/minimum/regrowth, targeted Ctrl+C, reuse, console
and four windows with the old apps. Unmodified 1986 D64/1571 and D81/1581 also
pass native keyboard/1351 resizing, drag/close, time, cancellation/reuse and
guards. Physical-C128 feedback for resizing is still due. Exact artifacts/results:
`bench/{artifacts,results}/2026-10-04-native-resize`. The earlier
`2026-10-04-native-clock` archive preserves the fixed-size first candidate.

Follow-up after manual 1986 feedback: the running-app panel's repeated-initial
bug is fixed in fresh `build/native-clients/native-clock-demo.d64` / `.d71` /
`.d81`. VICE and 1986 verify actual panel characters/attributes and lifecycle
updates. D81 also passes in 1986 with **1581 selected before restart**; see
[D81 setup](D81.md#1986). Updated evidence is kept separately in
`bench/{artifacts,results}/2026-10-04-app-panel`; earlier snapshots are unchanged.

Rebuild/test without changing the kernel or default disk contents:

```sh
distrobox enter my-distrobox -- make native-clock
make native-clock-probe  # host VICE; build boot images in the container first
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --emulator ../1986 --roms ../1986/roms --native-clock \
  --output build/native-clients/1986-d64
```

The probe disks are `build/native-clients/vice-d64/native-clock.d64` (and
corresponding D71/D81 paths). For manual packaging, install NCLOCK.BIN with
`add_disk_apps.py` as above. The retained-wave/worker gates are now implemented;
next is a measured four-native-allocation layout before default cutover;
see the [migration plan](GENERIC-GRAPHICS-APPS.md#clockwave-migration-follow-up-2026-10-04).

## Earlier native-wave migration candidate (historical)

The current default XWAVE.BIN is native; use fresh build/boot disks for the four-slot cutover.


`NWAVE.BIN` is a separately built UDEX 0.2 app using UTRQ 0.12 packed paths
and 0.11 bounded worker requests. No resident app ID or private kernel import
is involved. It preserves the current sinc function and all 524 grid edges.
Its 3,422-byte image+BSS fits the larger slot; launch it before NCLOCK so the
clock can use the smaller slot. Four interchangeable native allocations are
still pending; the default legacy binaries are deliberately not replaced yet.

```sh
distrobox enter my-distrobox -- make -j8 boot native-wave native-clock
python3 tools/add_disk_apps.py --disk build/boot/udeks.d64 \
  --output build/native-clients/native-wave-demo.d64 \
  build/native-clients/wave/NWAVE.BIN build/native-clients/clock/NCLOCK.BIN
# The same command supports .d71 and .d81 input/output.
```

Cold-boot the candidate disk, then try:

```text
nwave &
nclock &
date 03:15:00
cowsay hello
```

Drag, raise, grow/shrink/regrow, and close either window. Wave moves must not
recompute the function; resize uses the existing private height field. Close
both, try foreground `nwave` and Ctrl+C, then reload. The original `xclock &`
and `xwave &` can coexist in the two legacy slots; `xinit -q` closes the desktop.
The native wave's vectors are retained, not a full pixel backing store, so
compositor repaint latency remains open. This checkpoint is VICE-qualified;
1986 and physical-C128 feedback on these new paths is still needed.

For other dense line drawings, build with `--graphics-abi 12` and submit the
[packed path format](../abi/window.md#packed-retained-paths-utrq-012). It supports
9-bit X coordinates, disconnected paths and signed byte deltas. The same API
can carry any bounded geometry; wave projection stays in `user/lib/wave_paths.c`.

### Resizable app contract

Build with `--graphics-abi 10`. CREATE chooses RESIZABLE (`$08`) or FIXED_SIZE
(`$10`), plus optional MOVABLE/CLOSABLE. EVENT supplies the last drawn width
(LE16) and height; its seven-byte reply contains state, optional click, and
current dimensions. On state 2, rebuild your content, PRESENT it, and acknowledge
that size in the next EVENT. A pending click is not consumed by a resize.
See [the exact ABI](../abi/window.md#geometry-events-utrq-010). Default SDK builds
remain at 0.9, preserving old fixed-size programs and their four-byte replies.

The native clock build uses `--static-locals` (nonrecursive, task-private) and
`--capacity 2816` to check both file and image+BSS against the smaller slot.
These are optional SDK build choices, not a special clock loader path.

## Independent console commands

Console commands already use name-independent disk lookup too. The new
[`args.c`](../user/examples/args.c) demonstrates the existing UDEX 0.1 console
ABI: `udeks_program_main(argc, argv)`, stdout (1), stderr (2), a returned
eight-bit exit status, and BSS reset on each invocation. `ARGS.BIN` and its
identical renamed copy `AGAIN.BIN` need no kernel or ush entry.

```sh
distrobox enter my-distrobox -- make console-example
python3 tools/add_disk_apps.py --disk build/boot/udeks.d81 \
  --output build/generic-apps/my-console.d81 build/generic-apps/console/ARGS.BIN
# Your own C command, built without relinking the OS:
distrobox enter my-distrobox -- python3 tools/build_console_example.py \
  --source /absolute/path/to/mytool.c --name MYTOOL --output build/mytool
```

The entry/runtime links at `$0200` with a 2,560-byte image+BSS ceiling. This
**synchronous** compatibility loader saves/restores the legacy clock allocation;
it does not consume any native graphical slot. Bounded console commands work
with all four windows present, but block cooperative app progress until they
return. Do not run an endless loop, use the bank-1 graphics veneers, or append
`&` to these fixed-address commands. General console stdin, native background
console jobs, pipes/redirection, and shell `$?` expansion are not implemented by
this recipe. The example deliberately returns 37; the test reads the actual
loader exit status, not a printed imitation. Programs must target UDEKS APIs;
this does not make arbitrary Commodore PRGs or Linux binaries compatible.

## Bounds and lifecycle

- Four file capacities are 4,608 / 2,816 / 4,096 / 2,560 bytes. Reserve the
  final 256 bytes of each allocation for runtime state: image+BSS limits are
  4,352 / 2,560 / 3,840 / 2,304 bytes. The whole file, including relocation
  metadata, must fit too. Each task has private CPU pages and a **160-byte C
  stack** with guards; keep call depth/local arrays bounded (or use private
  static data for nonrecursive code). Admission order is smallest fitting first.
  [Exact addresses and lifetimes](GENERIC-GRAPHICS-APPS.md#four-native-slot-cutover--2026-10-05).
- CREATE/PRESENT/EVENT/CLOSE use UTRQ 0.9. Up to 48 eight-byte commands are
  retained per client; the service copies them and clips painting to its window.
  UTRQ 0.12 alternatively accepts a packed path stream of at most 1,280 bytes.
  A shared 2,304-byte retained pool bounds total drawing data; ENOMEM leaves
  prior images intact. Input is client click/close, not a general keyboard event API.
- The sample owns its drawing data and private counter. It must yield/sleep;
  arbitrary uncooperative or invalid machine code is not hardware-isolated.
- Close requests retire the window, then wait for cooperative task EXIT before
  reaping and releasing its allocation. Do not call legacy UAPP callbacks from
  a bank-1 native task.

## Qualification and remaining work

Current regression: run `make four-native-probe` on the host after
`distrobox enter my-distrobox -- make -j8 boot graphical-example graphics-apps-check placement-check`.
It uses Flatpak VICE and copies the disks before adding unknown-name examples.
D64/D71/D81 cover four bundled apps, four identical independent app instances,
private state/input, resize/worker oracles, malformed/full rejection, name-based
stop, guarded stacks, reload and console use. Physical C128 acceptance remains due.

Older probes below target preserved two-native-plus-legacy builds, not the
new four-native allocation layout:

`make generic-launch-probe` runs on the **host** after building `boot` and
`graphical-example` in my-distrobox. It uses host Flatpak VICE, ordinary shell
input and injected WM events; it does not patch the loader or scheduler poll.
D64 and D71 cover unknown filenames, independent input, automatic placement,
bad images, missing files, capacity rejection, safe legacy stop, drag/close,
clean slot reuse and console liveness. Existing four-app VICE and native 1986
input regressions remain separate gates. Physical-C128 acceptance of the new
generic example is pending.

`make console-apps-probe` additionally checks independent console names,
arguments, stdout/stderr, status 37, repeat BSS initialization, foreground
launch/Ctrl+C in both native slots, and console execution with four windows.
It covers VICE D64/1541, D71/1571 and D81/1581; build `boot`,
`graphical-example` and `console-example` in the container first.

Next: finish instance/name-based control, migrate calculator and
drawing off named CONTROL, then resolve the legacy clock/wave compatibility
model. Twenty bytes remain before the fixed boot assets: further resident growth
requires a measured service-placement change, not borrowing task stacks or
guard space. Performance tuning and more than four apps are out of scope.
