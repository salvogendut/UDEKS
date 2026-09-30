# Disk-loaded graphical applications

The initial extraction checkpoint below is historical. For current namespace
and calculator usage see [Calculator addition](#calculator-addition-branch-app-xcalc)
and [the roadmap](ROADMAP.md).

## Four-application support (#30)

Current work: [issue #30](https://github.com/salvogendut/UDEKS/issues/30),
branch `graphics-four-apps`, based on accepted calculator commit `5cd34f9`.
**Not yet available:** the runtime still permits clock or calculator in slot 1,
with wave in slot 2. The four-entry window registry does not allocate app RAM.

The proposed bounded transition keeps clock/wave in bank 0 and introduces
two bank-1 graphical clients. It does not page whole programs through the
calculator's execution address on every poll or paint. Candidate reservations:

| Client | Image + BSS | Private software stack reservation | Relocated CPU pages |
| --- | --- | --- | --- |
| Clock (existing) | bank 0 `$0200-$0BFF` | Existing resident managed-call stack | Existing kernel pages |
| Wave (existing) | bank 0 `$1200-$1BFF` | Existing resident managed-call stack | Existing kernel pages |
| Calculator (proposed) | bank 1 `$2300-$34FF` (4,608 bytes) | `$8A00-$8CFF` | `$D500-$D6FF` |
| Fourth client (proposed) | bank 1 `$3500-$3FFF` (2,816 bytes) | `$8D00-$8FFF` | `$D700-$D8FF` |

The new stack reservations must include their own guards/context needs; they
are not a measured 768-byte usable-stack guarantee. The boot-only data left
in the Z80 padded container is disposable only after native boot has consumed
it. The current Z80 code is 663 bytes at `$2000-$2296`, with no data allocation.
This proposal narrows its old 8 KiB growth reservation; future code/data growth
into either client allocation must fail the build, not silently corrupt an app.
Existing foreground commands, shell, storage policy, cache and native task
pages are not repurposed. Native task IDs and window owners must be explicitly
bound, not assumed interchangeable.

Run `distrobox enter my-distrobox -- make -j8 graphics-apps-check placement-check`.
The gate reads real maps and UDEX images, verifies Z80 HEX against its padded
binary, checks physical-bank overlaps (including zero-page/hardware stacks),
and emits `build/four-apps/layout.json` with input hashes. Existing xcalc uses
4,027 image+BSS bytes, leaving 581 in the proposed allocation for its changed
client bindings. This is an input to a new link, **not** proof that those
bindings fit. Resident bridge headroom is also reported; exceeding either
budget requires a placement revision. The accepted calculator disks remain
preserved in `bench/artifacts/2026-09-30-xcalc`.

Implementation sequence:

1. **Implemented:** placement gate and four-owner manager regression. A fifth
   window leaves the four descriptors unchanged; invalid/wrapping coordinates
   reject before mutation. Focus/click/drag/close dispatch and handle reuse
   are tested in both real C manager variants. The private resident owner query
   is not a public UAPP extension. These tests run four windows, not four apps.
2. **Next:** bounded bank-aware delivery and graphics request/event routing.
   Marshal coordinates, geometry, titles and input; never store a foreign-bank
   title pointer or execute a foreign-bank paint/close pointer directly.
   Banked clients need explicit repaint/input/close events and owner-checked
   drawing. Establish correct compositing of overlapping clients, including
   partial/hidden damage; do not publish a cross-bank begin/end-paint lease
   that lets another app draw before its owner has finished. Closing or failed
   loading must retire events/windows before releasing an allocation.
3. Relink xcalc, supply a separate fourth test executable, and integrate shell
   foreground/background control and the running-app panel. Gate with four
   concurrent apps, independent state after repeated focus/drag/reload,
   atomic invalid/fifth-load rejection, console commands and targeted Ctrl+C.
   Test both disk formats in VICE, native input in 1986, then physical C128.

This is bounded four-client support, not arbitrary-size executables, general
dynamic relocation or memory protection from hostile machine code. No
xwave algorithm or generic rendering optimization is bundled into this work.

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

The calculator occupies the enlarged bank-0 slot 1 and is mutually exclusive
with xclock: stop/close one before starting the other. A live peer produces
`slot busy`, without overwriting its code. xwave can coexist in slot 2.
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
