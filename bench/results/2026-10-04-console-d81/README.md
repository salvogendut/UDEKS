# Foreground apps, independent console command, D81 — 2026-10-04

Working-tree implementation following `1699e82` on `graphics-generic-apps`.
Exact disks, examples and linker maps are in
`bench/artifacts/2026-10-04-console-d81`; hashes pin both inputs and results.

`vice-d64`, `vice-d71`, `vice-d81`: VICE 3.10 x128 Flatpak, true-drive
1541/1571/1581 respectively. `tools/console_apps_probe.py` uses ordinary ush
commands through injected keyboard events, not direct loader calls. Unknown
ARGS and AGAIN filenames contain the same separately built console executable.
Arguments, stdout/stderr, actual exit 37 and fresh BSS pass. The VIC status
record stays byte-identical across console-only commands. HELLO runs foreground
in task 3, then SECOND foreground in task 4 alongside background HELLO; Ctrl+C
retires only the foreground instance. Both tasks are then reused in background,
clock/wave bring the window count to four, console reloads and cowsay succeed,
and desktop shutdown/reaping returns to usable console commands. Task-state
observations explicitly select bank 0; raw `.bin` files have VICE's two-byte
load-address prefix. This does not qualify native background console stdin.

`generic-d64`: existing unknown-name background test passes malformed/missing/
oversized/full rejection, per-instance input, drag/close/reload, legacy `-q`
isolation, console liveness and completed shadow/bitmap equality. Pointer/WM
events are injected; this is not physical mouse qualification.

`native-input-d64`: unmodified 1986 `81485cc7` passes the existing four-app
raw-IEC and native keyboard/1351 sequence (calculator, drawing, drag, panel,
independent reload, targeted Ctrl+C, shutdown and guards). It does not separately
qualify the new example or D81 on 1986. No sibling emulator files changed.

`typed-boot-d81`: the final image also reaches the shell after typing BASIC
`BOOT` on a cold C128/1581 VICE session. c1541 independently recognizes the image
as standard D81, lists all 21 DOS files and reports 2,577 blocks free (the
four-example demo has 2,567). Physical 1581 confirmation remains pending.

`clean-result.json`: eleven outputs match byte-for-byte after a clean parallel
build in `build/generic-apps/clean-console.MH5AO9`. `layout.json` records actual
graphics placement; both normal/panic placement checks pass. No app allocation,
software stack, CPU page, common gateway or published ABI moved. The read-only
filesystem no longer carries the unused outgoing filename encoder, making
room for 1581 geometry and a 16-bit directory cursor. Public release snapshots
remain unchanged.

Reproduce:

```sh
distrobox enter my-distrobox -- make -j8 boot graphical-example console-example graphics-apps-check placement-check
make console-apps-probe
python3 tools/generic_launch_probe.py --disk build/boot/udeks.d64 --drive 1541 --output build/generic-apps/generic-regression
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py --emulator ../1986 --roms ../1986/roms --four-apps --output build/generic-apps/native-regression
python3 tools/boot_entry_probe.py --disk build/boot/udeks.d81 --drive 1581 --output build/generic-apps/typed-boot-d81
make check
```
