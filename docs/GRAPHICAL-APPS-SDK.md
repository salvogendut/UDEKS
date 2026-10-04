# An independent graphical app (development SDK)

Issue #35 now supports **`name` and `name &` without an OS name-table entry**. The same
compiled file runs in either free compatible native allocation. This is an
intermediate SDK: native arguments, name-based stop and
migration of the four existing named clients are still pending.

## Try the candidate

Cold-boot `build/generic-apps/apps-demo.d64` (or `.d71` / `.d81`). Device 8 is mounted
as `/` at startup. Run:

```text
hello &
second
```

`second` owns the foreground: press **Ctrl+C** to close it and return the
prompt. `hello` keeps running. Then:

```text
second &
args alpha beta
cowsay hello
```

Two independently owned HELLO windows appear. Click a window's client area:
its black square moves between the two ends, without changing the other
instance. Drag one, close it with its close box, and run its command again.
The running panel shows `hello` and `second`. A third launch while both native
slots are occupied reports `task slot busy`; the two live apps remain intact.
`xinit -q` closes the desktop and all its apps.

HELLO.BIN and SECOND.BIN deliberately contain identical executable bytes.
Neither filename is compiled into the OS. You can also launch `hello &` twice;
ownership is per task/window, not unique per filename. For this increment use
close boxes or desktop shutdown, **not `hello -q`**. Background
jobs do not become the console's Ctrl+C target.

Graphics are initialized lazily by the first valid CREATE request, not simply
by loading a native executable. Bare native launch currently accepts no app
arguments; close/Ctrl+C is cooperative through the graphics event protocol.

Clock/wave can coexist with these two native clients. Calculator/drawing use
the same native allocations, so do not expect them in addition to both demos.
Four windows remain the ceiling; this is not yet four interchangeable slots.

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

## Native clock migration candidate

On branch `graphics-native-clients`, `make native-clock` builds an independent
relocatable clock as **NCLOCK.BIN**. It shares no app callbacks, fixed task id or
private runtime symbols with the resident system. Both generic slots accept
the exact same 2,463-byte file (2,039 image + 351 BSS bytes; staging includes the
relocation table). All face/tick/hand/digit calculations stay in the disk app;
the existing graphics service retains 43 ordinary commands. The app reads the
same common TIME snapshot as `date`, updates once per changed minute, and
sleeps between event checks. It does not re-submit its image merely on a move.

Test **`build/native-clients/native-clock-demo.d64`**, `.d71` or `.d81`:

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
The candidate uses the current **fixed-size** generic API, not yet the legacy
clock's resizable window. No `nclock -q` support is implied.

VICE D64/D71/D81 qualifies both slots, an independent drawing oracle, `date`,
dragging, targeted Ctrl+C, reuse, console and four windows with the old apps.
Unmodified 1986 D64 also passes native keyboard/1351 drag and close, time
changes, cancellation/reuse and guards. Physical-C128 feedback is still due.
Exact artifacts/results: `bench/{artifacts,results}/2026-10-04-native-clock`.

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
`add_disk_apps.py` as above. Next gates are generic resize/retained-wave/worker
services and a measured four-native-allocation layout before default cutover;
see the [migration plan](GENERIC-GRAPHICS-APPS.md#clockwave-migration-follow-up-2026-10-04).

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
it does not consume either native graphical slot. Bounded console commands work
with all four windows present, but block cooperative app progress until they
return. Do not run an endless loop, use the bank-1 graphics veneers, or append
`&` to these fixed-address commands. General console stdin, native background
console jobs, pipes/redirection, and shell `$?` expansion are not implemented by
this recipe. The example deliberately returns 37; the test reads the actual
loader exit status, not a printed imitation. Programs must target UDEKS APIs;
this does not make arbitrary Commodore PRGs or Linux binaries compatible.

## Bounds and lifecycle

- Native image/BSS allocations are 4,608 and 2,816 bytes. The complete file
  (header, image and relocation table) must also fit the chosen allocation.
  Each task has its own bounded runtime, CPU pages and software stack.
- CREATE/PRESENT/EVENT/CLOSE use UTRQ 0.9. Up to 48 eight-byte commands are
  retained per client; the service copies them and clips painting to its window.
  Input is client click/close, not a general keyboard event API.
- The sample owns its drawing data and private counter. It must yield/sleep;
  arbitrary uncooperative or invalid machine code is not hardware-isolated.
- Close requests retire the window, then wait for cooperative task EXIT before
  reaping and releasing its allocation. Do not call legacy UAPP callbacks from
  a bank-1 native task.

## Qualification and remaining work

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
model. Five bytes remain before resident LOWBSS: further resident growth
requires a measured service-placement change, not borrowing task stacks or
guard space. Performance tuning and more than four apps are out of scope.
