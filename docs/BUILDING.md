# Building UDEKS

## Reference environment

The validated development environment is the Fedora 44 `my-distrobox`
container. As of 2026-09-23 it contains:

| Tool | Validated version/source |
|---|---|
| cc65/ca65/ld65 | Fedora package `cc65-2.19-15.fc44` (`cc65` reports V2.18) |
| SDCC | 4.6.2, revision 16671, from `../sdcc/bin` |
| RASM | 3.2.1 Atlas, build 2026-05-05 |
| GNU Make | 4.4.1 |
| Python | Python 3 supplied by Fedora |

These versions validate the scaffold; they are not yet the pinned release
toolchain. Phase 0 will replace environmental assumptions with checksummed tool
sources or packages.

To install the currently validated 8502 tools in the container:

```sh
distrobox enter my-distrobox
sudo dnf install cc65
```

SDCC and RASM are currently provided through paths shared with the host. A clean
environment bootstrap will be added before the Phase 0 exit gate.

## Targets

```sh
make doctor     # report every required program and fail if one is absent
make check      # host-side unit and utility checks; no target compiler needed
make 8502       # build build/8502/udeks-8502.bin
make z80        # build build/z80/udeks-z80.bin through SDCC
make z80-asm    # build the independent RASM smoke image
make            # build all three target images
```

The 8502 artifact is a 97-byte raw bring-up image linked at `$2000`. The SDCC
artifact is a fixed 8 KiB raw window covering `$2000`–`$3FFF`; only its leading
bytes currently contain code. Neither is bootable yet.

`tools/ihx_to_bin.py` performs strict Intel HEX checksum validation and rejects
addresses outside the declared output window. This avoids silently creating an
unexpectedly large or truncated Z80 payload.

## Tool boundaries

The 8502 side uses one relocatable object ecosystem: cc65 emits ca65 input,
ca65 creates objects, and ld65 places them according to
`cfg/8502-bootstrap.cfg`.

The Z80 side has two intentionally separate paths:

- SDCC C and assembly linked into the same image use SDCC's `sdasz80` object
  format and linker.
- RASM builds standalone images. A RASM image and an SDCC image meet only at a
  documented binary/jump-table boundary.

Do not attempt to feed SDCC `.rel` files to RASM.

## Emulator plan

The local `../1986` C128DCR emulator is the primary integration target. VICE
`x128sc` and `c1541` are planned as an independent behavior oracle and disk
image tool. Real-hardware verification gates MMU, timing, video, IEC, and
CPU-handoff milestones.
