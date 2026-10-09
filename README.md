# UDEKS

<p align="center">
  <img src="UDEKS.png" alt="UDEKS logo: a smoking pipe above the project name and Unified Dual-Engine Executive Kernel System expansion" width="560">
</p>

UDEKS—the **Unified Dual-Engine Executive Kernel System**—is a native operating
system for the Commodore 128, written in assembly and predominantly C, under
[GPL-3.0-or-later](LICENSE).

The C128 was among the earliest 8-bit home computers to combine two CPUs with
two independent display engines. UDEKS builds on that neglected potential:
the 8502 manages the system and I/O, the Z80 handles bounded computation, the
VDC hosts the console, and the VIC-IIe drives a graphical desktop. The CPUs
share the bus and **take turns; they do not execute simultaneously**.

The name echoes the Latin *iudex*, “judge.” UDEKS is dedicated to
“Professor Lo Giudice,” who taught its creator programming as a child and
embodied authority, knowledge, insight, firm direction, and paternal sweetness.
Read the [dedication](DEDICATION.md).

**[Roadmap](docs/ROADMAP.md)** · **[Documentation](docs/README.md)** · **[Build guide](docs/BUILDING.md)**

Normal boot now loads the [time service from disk](abi/services.md#coherent-boot-integration-and-manual-acceptance).
`/etc/rc` invokes `svc load /TIME.SVC`; `svc status`, `svc stop` and `svc load`
manage its lifetime independently of the scheduler. This is the first service
extraction, not yet a general-purpose module loader.

> [!IMPORTANT]
> This is an experimental native OS, not a general-purpose Unix or a finished
> microkernel distribution. Many services are still preloaded. Fresh builds mount
> the normal system root read/write; use disposable copies while testing.
> Create-only writes have passed the functional checklist on C128/PI1541;
> the changed boot default passes VICE/1986 but needs fresh hardware acceptance.
> Task capacity is limited and graphical repaints
> can be slow.

## Download and boot

The current downloads include writable root, file commands, the sprite editor
(D71/D81), and disk-loaded timekeeping. The
[SAVE test and writable-mount instructions](docs/GRAPHICAL-APPS-SDK.md#counted-disk-io-utrq-014)
apply to these images. Use disposable media for write testing; overwrite and
append are not implemented. Exact-file `cp`, `mv` and `rm` are available (see below).
The [qualification record](bench/results/2026-10-07-storage-acceptance/README.md)
includes the hardware acceptance. The VICE 1581 mid-write-ejection run remains
unqualified, but the [equivalent 1986 test now passes](bench/results/2026-10-07-storage-eject-1986/README.md).

Published 2026-10-09; ordinary `make boot` reproduces these three formats:

| Image | Use |
| --- | --- |
| [Download D64](build/udeks.d64?raw=true) | 1541-compatible drives and Pi1541; also VICE and 1986. Omits only `xsprdef`. |
| [Download D71](build/udeks.d71?raw=true) | A 1571-compatible drive or emulator configured for D71; all apps. |
| [Download D81](build/udeks.d81?raw=true) | A 1581-compatible drive or emulator configured for D81; all apps. |

See [checksums](build/SHA256SUMS), [provenance](build/README.md) and
[qualification and limits](bench/results/2026-10-09-default-time/README.md).
VICE qualifies disk-service loading in all three formats; native 1986 qualifies
D64/1571 input and clock dragging. These checks do not establish new physical-C128
acceptance. All are ordinary CBM DOS disk images. Local builds go to `build/boot/`;
publishing into `build/udeks.*` is a separate, explicit step.

1. Select/mount the image as device **8**.
2. Start in native C128 mode with the **80-column VDC display** enabled.
3. If the emulator does not autoboot, type `BOOT` at the BASIC prompt.
   Use a fresh boot when changing images.

Bootstrap mounts the system disk at `/`, loads `/bin/ush`, then runs the
bounded startup commands in `/etc/rc`. No manual mount is needed for system
commands or graphical apps:

```text
ls /bin
cd /etc
cat rc
cd /
df
svc status
xclock &
xwave &
cowsay hello
```

The clock and wave appear on the **VIC-IIe / 40-column display**, independently
of the VDC console. Mouse: port 1 (1351); joystick: port 2. Use `xclock -q`
or `xwave -q` to stop a background app; `Ctrl+C` stops a foreground app.
`xinit -q` shuts down the graphics display.

Add `xcalc &` (decimal calculator) and `xdraw &` (click-to-toggle drawing grid)
to run **all four graphical apps together**. All four are independent,
relocatable disk programs with private runtimes and stacks. Clock and wave
resize; calculator and drawing use fixed-size layouts. Click xdraw's C button
to clear it; `xcalc -q` / `xdraw -q` close the respective app.

Fresh D71/D81 builds also include [`xsprdef`, the sprite editor](docs/XSPRDEF.md)
(omitted from D64 to leave working space for files).
Run `xsprdef &` to edit eight 24×21 monochrome definitions with
an 8× editor and 1× preview. It uses the same generic app slots, not a special
kernel entry. The current sprite number stays visible beside the preview;
hold the primary mouse button to draw or erase a stroke. Click S/L for
confirmed Save/Load of the entire bank as
`/SPRITES.SPR`. Saving **creates only** and the normal root is writable by default:
existing files are never overwritten. B keeps edits while returning to the list.
The list's **E** button exports `SPRITES.BSV` for stock C128 BASIC:
`BLOAD "SPRITES.BSV",B0,P3584`. It creates a genuine PRG file without changing
the compact `SPRITES.SPR` format.
Use a freshly built image from `build/boot/`; the published downloads above
do not include these editor features. The larger editor joins two free allocations,
leaving room for two compatible-sized peers; launch it first. See its guide
for safe disposable-disk testing and file-format details.

Use `mount -o remount,ro 8 /` to make the system root read-only, and
`mount -o remount,rw 8 /` to enable writes again. Recovery bootfs stays read-only;
an unqualified `mount 9 /mnt` also remains read-only. Fresh builds include
standalone `cp SOURCE DEST`, `mv SOURCE DEST`, and `rm FILE`
([issue #47](https://github.com/salvogendut/UDEKS/issues/47)). These act on exact
regular-file names on the same mounted filesystem: no overwrite, wildcard,
recursive deletion or cross-device copy. Failures can leave partial disk work.
Use disposable copies for acceptance testing. D64 omits the optional `xsprdef`
sprite editor to leave **31 free blocks**; D71/D81 include it. Use those larger
formats or a separate writable data disk for larger files. Existing published
download snapshots are not automatically updated by a source build.

A new `.BIN` launches as `name` or `name &`
into any free **compatible-sized** allocation, without an OS name-table entry.
`name -q` stops a matching instance; Ctrl+C targets the foreground instance.
See the [SDK and limits](docs/GRAPHICAL-APPS-SDK.md) and
[four-native-slot layout](docs/GENERIC-GRAPHICS-APPS.md#four-native-slot-cutover--2026-10-05).
The SDK also builds [independent argc/argv console commands](docs/GRAPHICAL-APPS-SDK.md#independent-console-commands)
with stdout/stderr and an exit status. They use one fixed foreground allocation
and pause cooperative app progress until returning; general background console
jobs and stdin are not yet supported. On the active #52 branch, the separate
[scheduled console SDK](docs/NATIVE-CONSOLE-APPS.md) now delivers private
arguments, stdout/stderr, cooperative sleep and foreground status (`echo $?`)
without stopping graphical peers. Foreground Ctrl+C now cancels native tasks
with or without a window and returns status 130; stdin and background terminal
policy remain next. Published downloads do not yet contain this checkpoint.
Four graphical slots are available, but
not every binary fits every
slot. The loader can borrow two free adjacent allocations
for a larger native app: up to **7,168 image+BSS bytes**, with room for two
other apps. Four ordinary apps remain supported; live apps are never moved
to make room. See the [larger-app test sequence](docs/GRAPHICAL-APPS-SDK.md#larger-native-apps-capacity-candidate-2026-10-07).
The retained drawing pool is shared and each native task has a bounded
160-byte C stack. Fresh source builds produce `build/boot/udeks.d64`, `.d71`
and `.d81`.

Wave resize no longer spends as long rebuilding coordinates: the native PAL
two/four-app checks improved from about 15/28 seconds to 8/12 seconds after
release, without further clicks. Dense wireframe painting is still slow;
this is not instant resizing. The improvement is app-local, not new wave
policy in the window manager.

`/mnt` starts free. To use a separate data disk on device 9:

```text
mount 9 /mnt
ls /mnt
cat /mnt/HELLO
cd /
umount /mnt
```

Replace `HELLO` with a file on that disk. Leave `/mnt` before unmounting;
open files also keep it busy. System commands remain available afterward.

## What works

- Mixed-case, black-on-yellow VDC console with command history, a live running-app
  panel, Unix-like streams and Bash-like command names.
- Disk-loaded `ush`, utilities and graphical apps. Bare commands use system
  `/bin`, never an arbitrary data disk; bootfs provides explicit recovery.
- Four generic native graphical allocations, an independent app SDK, dynamic
  running-instance names, foreground/background launch and clean slot reuse.
- A coherent `cd`/`pwd`/`ls`/`cat`/`df` namespace over flat DOS files:
  `NAME.BIN` → `/bin/name`, `RC.ETC` → `/etc/rc`. Raw data mounts retain
  ordinary filenames. `.SH` is reserved and readable, but execution is deferred.
- Overlapping, focused, movable and resizable VIC-IIe windows. Drag/resize uses
  outlines until release; a retained cache assists repainting.
- `xclock` uses the same TI/TI$-compatible timebase as `date`. `xwave` uses
  the Z80 for sinc-surface heights and the 8502 for projection and plotting;
  computed heights survive moves and resizes.
- Native D64/D71/D81 boot images, hardware discovery, cooperative task switching and
  bounded Z80 jobs. `free` reports the fixed task-memory pool, **not all unused
  physical RAM**; `df` reports the selected disk's DOS allocation blocks.

The accepted namespace has VICE and native 1986 qualification plus positive
user feedback. Earlier boot/graphics builds were tested on C128 + Pi1541;
this is not a claim that every model, peripheral or failure path is qualified.
The target baseline is a stock 128 KiB C128 with 16 KiB VDC RAM; 64 KiB VDC,
REU and GeoRAM are optional. PAL and NTSC remain targets.

**Completed feature:** four generic native app slots, emulator-qualified and
accepted by the user for merge. **Completed feature, accepted for merge:**
[#44 — safe create-only disk writes](https://github.com/salvogendut/UDEKS/issues/44),
implemented with public UTRQ 0.14, explicit writable mounts and the standalone
SAVE command. The manual checklist passes in 1986 and on real C128/PI1541;
1581 mid-write ejection/recovery also passes under native 1986. The separate
VICE limitation remains documented. [PR #45](https://github.com/salvogendut/UDEKS/pull/45)
records the merge. The first non-kernel service extraction is now installed
by normal boot: `TIME.SVC`, with failure recovery and a disk-only loader.
**Active next feature:** [independently scheduled console programs](docs/NATIVE-CONSOLE-APPS.md)
(#52). The first no-window stdout/stderr/sleep example works alongside graphics;
private arguments, native exit-status reporting and terminal job control remain
in progress. General scripting and optimization remain separate roadmap
work. The existing `/etc/rc` command runner is not a POSIX
`sh` or Bash implementation.

## Screenshots

These show the project's boot console and dual-display desktop; older captures
may contain messages or command paths that differ from the current images.

<p align="center">
  <img src="screenshot/udeks-boot.png" alt="UDEKS boot console" width="640">
</p>

<p align="center">
  <img src="screenshot/udeks-xclock.png" alt="Analog xclock on the VIC-IIe display" width="384">
</p>

<p align="center">
  <img src="screenshot/udeks-running-apps.png" alt="VDC console with the running-app panel" width="640">
</p>

<p align="center">
  <img src="screenshot/udeks-xwave-xclock.png" alt="Resizable xwave and xclock windows sharing the VIC-IIe display" width="384">
</p>

<p align="center">
  <img src="screenshot/udeks-dual-display.gif" alt="Animated UDEKS session with both displays working together" width="720">
</p>

## Build from source

| Target | C | Assembly / linking |
| --- | --- | --- |
| 8502 | cc65 | ca65 / ld65 |
| Z80 | SDCC | sdasz80 / sdld; RASM for standalone assembly |

The reference environment is `my-distrobox`; Distrobox is not intrinsically
required when the [toolchain](docs/BUILDING.md) is installed elsewhere.

```sh
distrobox enter my-distrobox
make doctor
make check
make boot
```

Fresh build outputs are `build/boot/udeks.d64`, `build/boot/udeks.d71` and
`build/boot/udeks.d81`.
The older copies at `build/udeks.d64` and `build/udeks.d71` are deliberately
published snapshots: ordinary builds do not replace them. The current test
downloads above instead point to immutable qualification artifacts.
After qualification, `make publish-boot` refreshes those copies and their
checksums. See the [publication procedure](docs/BUILDING.md#publishing-disk-images).

## Documents

- [Roadmap and next priorities](docs/ROADMAP.md)
- [Architecture and implementation plan](docs/PLAN.md)
- [Build, test and publication guide](docs/BUILDING.md)
- [Documentation index](docs/README.md) — interfaces, services, decisions and historical evidence
- [Contributing](CONTRIBUTING.md) · [Engineering handover](HANDOVER.md)

Source layout: `src/kernel` and `src/8502` contain the executive;
`src/services` contains mostly-C service modules; `src/apps` and `user`
contain standalone applications and shell code. Contracts live in `abi`,
linker configurations in `cfg`, tests in `tests`, and preserved benchmark
images/results in `bench`.
