# XSPRDEF — sprite editor

The accepted `graphics-xspr-pixel-update` checkpoint adds a visible sprite
number and held-button painting after disk Save/Load and BASIC export,
fast pixel updates and generic larger-app capacity. This is an
independent relocatable program, not a kernel-specific editor.

## Try it

Cold-boot a freshly built worktree image: `build/boot/udeks.d64`, `.d71` or
`.d81`. Published snapshots may still contain the older session-only editor.
Use a **disposable disk copy** for write tests.

```text
xsprdef &
```

Fresh builds mount the normal system root read/write by default. Loading does
not require a writable mount; saving does. If you explicitly remounted RO,
use `mount -o remount,rw 8 /` before saving. Recovery bootfs remains read-only.
Mouse port 1 / joystick port 2 are unchanged.

- Click a numbered button to edit one of eight 24×21 monochrome sprites.
  Each magnified cell toggles one pixel; the framed preview is the 1× image.
- The current **sprite number (1–8)** appears beside the preview and remains
  visible during Save/Load dialogs.
- **Hold the primary button and move** to paint a continuous stroke. Starting
  on yellow draws black; starting on black erases. Holding still or retracing
  keeps the same ink, rather than repeatedly toggling pixels. Skipped cells
  are interpolated using incremental pixel updates, yielding between cells.
  Release, leaving the grid or losing focus ends the stroke; toolbar/dialog
  buttons still need individual clicks. Title-bar dragging is unchanged.
- **S** opens `SAVE SPRITES?`, shows `SPRITES.SPR`, and offers **Y**/**N**.
  Y saves the entire eight-sprite bank, including the current edit.
- **L** opens `LOAD SPRITES?`. Y replaces the bank and current edit only after
  a complete valid read and successful close. N leaves them unchanged.
- **B** keeps the current edit in the session bank and returns to the list.
  The list also has S/L controls, so several sprites can be edited before saving.
- **E** on the list opens `EXPORT BASIC?` for `SPRITES.BSV`, with Y/N controls.
  From the editor, click B first to keep your changes and reach the list.
- **C** clears the current sprite; **I** inverts its 504 pixels.
- Result dialogs show DONE or a file error; their B button dismisses them.
- `xsprdef -q`, the window close control, or `xinit -q` ends the app. Unsaved
  work is lost.

These are **clickable buttons**, not keyboard shortcuts. A modal dialog
accepts only its visible confirmation/dismiss controls.

### Saving safely

The filename is fixed at `/SPRITES.SPR`. Saving is **create-exclusive**:
an existing file reports **FILE EXISTS** and is never replaced or deleted.
This first integration does not add overwrite, rename, automatic remounting,
or a filename picker. Use a fresh disk copy for a second independent save test.

The file is exactly **504 bytes**: eight consecutive 63-byte sprites,
three bytes per row, MSB first. There is no PRG load address, header, palette
or hardware-register state. A truncated or oversized file is rejected.
Failed loads preserve the previous bank and working edit.

Writes are not transactional: a media/write/close failure can leave a partial
file. The editor reports the error, does not retry the write, and does not
silently remove that file. Repeated Save then may report FILE EXISTS.

For persistence acceptance: draw in sprites 1 and 8, save with Y, change some
pixels without saving, load with Y and verify restoration. Cold-boot the same
written copy, launch the editor, load again and inspect both sprites. Also
check N cancellation, read-only saving, a duplicate save, console typing,
window dragging and closing.

### Exporting for C128 BASIC 7.0

Click **B → E → Y** (or E → Y if already on the list). This creates
`/SPRITES.BSV` containing the entire bank in the same byte layout as:

```basic
BSAVE "SPRITES",B0,P3584 TO P4096
```

There are **514 file bytes**: the little-endian load address `00 0E`, followed
by eight 64-byte blocks. Each block contains 63 image bytes plus a zero padding
byte. The export streams this layout; no second 512-byte app buffer is needed.
This matches the [Commodore sprite memory layout and BSAVE range](https://www.commodore.ca/manuals/128_system_guide/sect-06b.htm).

After resetting into **stock C128 BASIC**, with the exported disk in drive 8:

```basic
BLOAD "SPRITES.BSV",B0,P3584
```

The export is a real Commodore **PRG** file, just like BSAVE output. Do not
add `,S`: the first SEQ-export experiment worked on 1541, but the 1571/1581
burst loaders rejected it. The final opt-in PRG create mode avoids that
drive-dependent behavior. No conversion or file-type relabelling is needed.
`BLOAD "SPRITES.BSV",B0` also uses the exported load-address header.
Loading installs the data but does not display the sprites; BASIC's `SPRDEF`
can be used to inspect the eight definitions.
In BASIC's upper/graphics character set, type the filename without Shift.
Sprite data is on the VIC-II/40-column side, not the VDC display.

To keep a regular PRG copy after loading, BASIC can write a **new filename**:

```basic
BSAVE "SPRITES-BASIC",B0,P3584 TO P4096
```

E shares Save's read-only/create-exclusive safeguards: an existing BSV file
is not overwritten, and errors must be checked. S/L still use only the raw
504-byte `SPRITES.SPR`; there is no BSV import or automatic format detection.
Keep the SPR file if you want to reopen the bank in the editor.

## Capacity and rendering

Current executable: **6,920 file bytes; 6,458 image+BSS bytes**. It uses the
generic joined task-3/task-4 allocation, leaving room for two compatible-sized
peers (for example `xclock &` and `xdraw &`). Launch the editor first; existing
apps are never moved to make room. Closing it returns both allocations.
The ordinary four-app clock/wave/calculator/drawing configuration is unchanged.

UTRQ 0.15 PRESENT_DELTA retains the complete image but draws just the changed
8×8 cell and 1× preview pixel when topmost. Busy updates retry without toggling
twice. Clear, Invert, selection, dialogs and move/uncover use full repaint.
There is no BASIC CHAR call, app-side direct VIC access or text-mode switch.
The editor uses 50 scene commands; the shared 63-command private buffer also
provides the 504-byte load staging area while the compositor owns its retained
copy.

Native file requests use OPEN/READ/WRITE/CLOSE through `$FF16`, not the
synchronous console gate. The editor requests UTRQ 0.17 for held input and
0.16's generic create-exclusive PRG export; S/L retain their 0.14 file semantics.
There is no app-name routing. See the [SDK](GRAPHICAL-APPS-SDK.md).

## Verification

Build in this dedicated worktree, **never clean the repository root**:

```sh
distrobox-enter my-distrobox -- make -j8 boot graphics-apps-check placement-check
make check
make xsprdef-probe
make xsprdef-files-probe
```

The host tests exercise every pixel, dense/random patterns, modal hitboxes,
cancel, short reads, invalid lengths, failed/short writes, transfer and CLOSE
errors, and failure-atomic loading. The display gate runs 1,028 real-cc65
rectangle cases and 2,048 real-6502 input cases, including cc65 marshalling.
The **1,366-test** host suite covers the
export header, every padding byte, source preservation, all 22 writes and
CLOSE error paths, versioned PRG admission and exact empty-file finalization,
all eight sprite labels, held draw/erase, retracing, interpolation and controls.

VICE persistence probes use disposable copies and two emulator processes:
save in the first boot, load in the second. D64/1541, D71/1571 and D81/1581
pass exact bank readback, read-only/missing/existing-file errors, cancellation,
console/cover/uncover, stack guards and preservation of every existing file.
They inject WM click events, **not physical mouse input**.
The file probe also exports the bank, then runs a separate stock BASIC
session: BLOAD with an explicit address and with the header alone must match
all 512 bytes and preserve surrounding guards. BASIC BSAVE must produce a
byte-identical 514-byte file, while every existing disk file stays unchanged.
This uses real BASIC commands, not monitor LOAD or a substitute loader.
The updated pixel probe passes ten exact dense edits without full composition,
movement, dialog cancellation and three-app coexistence.

Native keyboard/1351 qualification against the unmodified sibling 1986:

```sh
distrobox-enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --xsprdef-files --emulator /path/to/1986 --roms /path/to/1986/roms \
  --disk build/boot/udeks.d64 --output build/sprite-files/1986-d64
```

Use `--xsprdef` instead for ten exact pixel-update comparisons plus physical
1351 held strokes, retracing/erase/diagonal checks, toolbar isolation, title
dragging, console input and close. It requires zero full compositions for
pixel editing and held strokes. This is distinct from the older file-only
qualification; current painting evidence lives under `build/sprite-paint/`.
The final `1986-d64-final` run passes these checks against unmodified 1986
`19386ef8`; VICE `vice-d64` passes pixel deltas, move/uncover and coexistence,
and `files/files-1541-_jjg0ts6` rechecks persistence and the BASIC round trip.
The file probe writes only a disposable copy, cold-boots twice and independently
decodes the resulting disk. Logs, images, hashes and readback records are under
`build/sprite-files/` (initial persistence) and `build/sprite-prg/` (final export).
The earlier `build/sprite-basic/` SEQ-file experiments are superseded.
See [HANDOVER](../HANDOVER.md) for completed runs. On 2026-10-08 the user
accepted BASIC export, then sprite numbering and held painting, and requested
PR/merge of the accumulated work. The latest manual-test platform was not
specified; no additional physical-C128 qualification is inferred.

## Limits and deferred work

No overwrite, thumbnails, filename selection, undo, multicolor
editing or live VIC sprite-register editing yet. The editor has fixed geometry.
Full-window painting remains synchronous. Neither bounded joined allocations
nor this app adds general background-console input or forced cancellation.

Historical pixel-only comparisons and the separately flagged four-native
wave-resize timing gate remain recorded in HANDOVER; do not equate this
sprite qualification with a passing whole-window-manager performance suite.
The original review was issue #41 / PR #42; the initial file prototype is
preserved under `experiments/xsprdef-files/` but is not the production source.
