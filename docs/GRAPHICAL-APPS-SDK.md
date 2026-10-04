# An independent graphical app (development SDK)

Issue #35 now supports **`name &` without an OS name-table entry**. The same
compiled file runs in either free compatible native allocation. This is an
intermediate SDK: foreground generic launch, arguments, name-based stop and
migration of the four existing named clients are still pending.

## Try the candidate

Cold-boot `build/generic-apps/generic-demo.d64` (or `.d71`). Device 8 is mounted
as `/` at startup. Run:

```text
hello &
second &
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
close boxes or desktop shutdown, **not `hello -q` or bare `hello`**. Background
jobs do not become the console's Ctrl+C target.

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
PRG load prefix. D71 works identically. Never rename a host `.BIN` to `.PRG` or
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

Next: finish generic foreground/control integration, migrate calculator and
drawing off named CONTROL, then resolve the legacy clock/wave compatibility
model. Only one byte remains before resident LOWBSS: further resident growth
requires a measured service-placement change, not borrowing task stacks or
guard space. Performance tuning and more than four apps are out of scope.
