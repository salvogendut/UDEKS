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

> [!IMPORTANT]
> This is an experimental native OS, not a general-purpose Unix or a finished
> microkernel distribution. Many services are still preloaded. Storage is
> read-only, task capacity is limited, and graphical repaints can be slow.

## Download and boot

The checked-in images contain the accepted root-namespace build from
[PR #28](https://github.com/salvogendut/UDEKS/pull/28).

| Image | Use |
| --- | --- |
| [Download D64](build/udeks.d64?raw=true) | 1541-compatible drives and Pi1541; also VICE and 1986. |
| [Download D71](build/udeks.d71?raw=true) | A 1571-compatible drive or emulator configured for D71. |

See [image provenance and checksums](build/README.md). These are ordinary
CBM DOS disk images, not a special UDEKS disk format.

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
xclock &
xwave &
cowsay hello
```

The clock and wave appear on the **VIC-IIe / 40-column display**, independently
of the VDC console. Mouse: port 1 (1351); joystick: port 2. Use `xclock -q`
or `xwave -q` to stop a background app; `Ctrl+C` stops a foreground app.
`xinit -q` shuts down the graphics display.

Since merged PR #31, freshly built images also support
`xcalc &` (decimal calculator) and `xdraw &` (click-to-toggle drawing grid).
**All four graphical apps can run together**, with independent bank-1
allocations for calculator and drawing. Click xdraw's C button to clear it;
`xcalc -q` / `xdraw -q` close the respective app. See
[four-app candidate and tests](docs/DISK-GRAPHICS.md#four-application-support-30).
The published download snapshots above remain the accepted main build.
Use `build/boot/udeks.d64` or `build/boot/udeks.d71` for this test candidate;
VICE D64/D71 and native 1986 input checks pass; physical-C128 acceptance of
this candidate is the next gate.

On `graphics-generic-apps` (#35), an independently built `.BIN` can now launch
as `name &` into either free compatible native slot, without an OS name-table
entry. Try the [generic-app demo and build recipe](docs/GRAPHICAL-APPS-SDK.md).
Generic foreground/control and migration of the legacy app paths are still
pending; the published snapshots above have not been replaced.

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
- A coherent `cd`/`pwd`/`ls`/`cat`/`df` namespace over flat DOS files:
  `NAME.BIN` → `/bin/name`, `RC.ETC` → `/etc/rc`. Raw data mounts retain
  ordinary filenames. `.SH` is reserved and readable, but execution is deferred.
- Overlapping, focused, movable and resizable VIC-IIe windows. Drag/resize uses
  outlines until release; a retained cache assists repainting.
- `xclock` uses the same TI/TI$-compatible timebase as `date`. `xwave` uses
  the Z80 for sinc-surface heights and the 8502 for projection and plotting;
  computed heights survive moves and resizes.
- Native D64/D71 boot, hardware discovery, cooperative task switching and
  bounded Z80 jobs. `free` reports the fixed task-memory pool, **not all unused
  physical RAM**; `df` reports the selected disk's DOS allocation blocks.

The accepted namespace has VICE and native 1986 qualification plus positive
user feedback. Earlier boot/graphics builds were tested on C128 + Pi1541;
this is not a claim that every model, peripheral or failure path is qualified.
The target baseline is a stock 128 KiB C128 with 16 KiB VDC RAM; 64 KiB VDC,
REU and GeoRAM are optional. PAL and NTSC remain targets.

**Current feature:** qualify four simultaneous graphical apps. **Next architectural
milestone:** extract the first non-kernel service into a disk-loaded program.
General scripting, filesystem writes, broader tasking and optimization are
separate roadmap work. The existing `/etc/rc` command runner is not a POSIX
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

Fresh build outputs are `build/boot/udeks.d64` and `build/boot/udeks.d71`.
The downloadable copies at `build/udeks.d64` and `build/udeks.d71` are
deliberately published snapshots: ordinary builds do not replace them.
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
