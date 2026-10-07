# XSPRDEF — session sprite editor

Review branch: `graphics-xspr-review`, based on `graphics-xspr` commit
`8ef5c25` (issue #41 / PR #42). This is an ordinary relocatable disk app.
No app-name routing or sprite-editor policy was added to the kernel.

**Accepted and parked, 2026-10-07:** the user approved this checkpoint for
commit/push/PR/merge and asked to put further editor work aside. The review
supersedes the early PR #42; the remaining features below are deferred, not
new work to start automatically. The latest manual-test platform is unspecified.

## Try it

Build **inside a dedicated worktree**, then cold boot its disk, not an older
published snapshot:

```sh
distrobox-enter my-distrobox -- make -j8 boot graphics-apps-check placement-check
```

Images are `build/boot/udeks.d64`, `.d71` and `.d81` relative to the worktree.
The default boot mounts device 8 at `/`. Run `xsprdef &`; the VIC-II display
shows eight numbered buttons. Mouse port 1 / joystick port 2 are unchanged.

- Click a number to edit that sprite. Each 8×8 cell toggles one pixel; the
  framed preview at right is the exact 1× image.
- **S** asks `SAVE?`. **S** again saves to that number in the session bank and
  returns to the list. **B** cancels the question without discarding the edit.
- **B** outside confirmation discards the working changes and returns to the list.
- **C** clears the working copy; **I** inverts all 504 pixels. Neither changes
  the saved definition until confirmed with S/S.
- `xsprdef -q`, closing the window or `xinit -q` ends the app and loses the bank.

The letters label clickable buttons, not keyboard shortcuts. During SAVE?
the working copy is frozen and only S/B are active and visibly framed.

## What the review fixed

The old rectangle decomposition stopped after four separate runs in a row
and silently truncated the command buffer. Its Python reference test did not
implement that limit, so valid checkerboards/noisy patterns could pass tests
while displaying incorrectly. Now each 24×21 view is exactly 15 bitmap tiles,
independent of pixel content. Both panes and controls use at most 46 commands
(368 retained bytes) out of the 56-command private buffer.

The numbered buttons now respond across their whole visible 20×20 bounds and
not outside them. Save confirmation keeps its controls visible. The canvas
has a frame; Clear/Invert and behavioural tests exercise every pixel, including
the bottom-right corner. The app acknowledges its fixed geometry on the 0.13
EVENT request so size notifications cannot starve clicks.

UTRQ 0.13 adds a **generic** 8×5 monochrome tile, integer scales 1–8. The
renderer reuses the glyph loop. The shared read helper and desktop-start
wrapper move into existing resident glue; no fixed memory reservation or
retained-pool boundary moves. Old glyphs, paths and client clipping remain
unchanged. This does not implement incremental/damage-only repaint.

## Limits and next useful features

- Eight app-private **monochrome** 63-byte definitions, not the VIC's live sprite
  registers/data and not disk files. There is no persistence or export yet.
- The list still uses numbered buttons, not eight thumbnails. The editor is
  fixed size and click-only; no grid overlay, paint-drag, undo history or
  multicolor editing. B discards the entire current edit.
- Painting remains synchronous and can be visibly slow for dense images.
  Partial repaint is separate work and must preserve clipping and request data.
- Four compatible native task allocations and the shared 2,304-byte retained
  pool still bound coexistence. This build fits task 5 or task 3, unlike the old
  editor which required task 3. Four arbitrary large binaries will not all fit.

When editor work resumes, prioritize a useful export/persistence contract with
the filesystem, then thumbnails and richer editing. Do not quietly define
"Save" as a hardware update or pretend a session save survives closing.

## Verification

`make check` compiles the real editor on the host and tests dense/random
patterns, all 504 click targets, exact hitboxes, confirmation/cancel, slot
isolation, clear/invert and discard. Graphics-service tests exercise scales
1–8, MSB order and atomic rejection of unsupported versions/opcodes.

After building, run `make xsprdef-probe` from the host. The default VICE D64 probe
checks every pixel in the actual bank-1 VIC bitmap against the bank-0 shadow
and expected sprite, reopens saved/discarded edits, runs xclock/xcalc/xdraw
alongside the editor, uses the console, checks task stack guards and cleans up.
Evidence/screenshots go to `build/xsprdef-probe/`. It injects the compositor
click queue and a dense pattern in the app's own buffer; physical input,
1986 and real hardware are **not** qualified by that probe.

Review qualification (2026-10-07): **1,176 host tests pass**, all three disk
formats build, and both `graphics-apps-check` and `placement-check` pass.
The editor probe passes on D64/1541, D71/1571 and D81/1581; the existing
`four_native_probe.py` also passes on D64 (including xwave drag/resize,
calculator, unknown app names, pool/stack checks and slot reuse). Each probe
closes its own VICE instance. Results remain in `build/xsprdef-probe*/` and
`build/xsprdef-regression/`; no physical-C128 or 1986 result is claimed.

The executable is **3,329 bytes**, with **3,662 bytes image+BSS**. The linked
graphics module ends at `$12EA`, PATHS at `$9AA4`, and resident BSS at `$9698`,
all within the unchanged reservations. There is no new kernel BSS for tiles.

The original worktree's uncommitted partial-repaint experiment is untouched.
It independently used draft ABI minor 13: do not combine the two meanings.
Its proposed damage bytes are overwritten by retained-transfer scratch before
use, its clip needs client bounds, and its current build exceeds module/app
reservations. Revisit it as a separate, versioned feature if needed.
