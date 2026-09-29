# Bounded prefix and row-range repair

The 2026-09-29 follow-up to the occlusion candidate adds a private banked copy
operation for partial overlaps. It does not enable caching in normal images or
change the public window/module ABI.

The retained image keeps its full capture geometry and packed row stride.
Private command protocol 0.2 adds operation 6: restore rows `[first,end)` and
only a prefix of each row. The prefix starts at the image's original left edge;
this deliberately avoids arbitrary source-bit alignment. Restoring unchanged
cached pixels to the left of the actual damage is harmless. Pixels beyond the
prefix and outside the selected rows must remain untouched.

Operation 6 uses the existing serialized VIC workspace: `$F78A` first row,
`$F78B` exclusive end, `$F78C-$F78D` little-endian prefix width. Validation
precedes state mutation: nonempty range within image height, nonzero width no
larger than the image, current owner, READY phase, valid full destination
geometry and capacity. STEP still validates ownership and generation. An
invalid persistent range is rejected before row parameters or pixels change;
the flow's existing failure path cancels the image. Normal PASTE restores full
width/height; capture, invalidation and cancellation reset the range metadata.

The new module holds exactly three initialized DATA bytes (end/width) within
the already allocated, checksummed module image. It uses the same lease, row,
flow, software stack, guard and 2,224-byte image allocations. Specializing the
pure policy to its one fixed lease saves enough code for the extension. Wrong
lease pointers reject without mutation in the host tests. The public generic
policy source remains unchanged.

Measured closure: 3,971 bytes, 141 bytes before the identity at `$5210`.
The 213-byte assembly row core and 196-byte common gateway match the qualified
compact provider exactly. The gateway source moves to `$50BF`; callers derive
its location from the preserved loader constants, not the old `$5146` literal.
The VCC2 envelope **layout** stays 0.1; its exact module length and checksum
change and are regenerated together with the acceptance validator. There is
no claim that an old validator can accept the new provider.

## Standalone qualification

`tools/window_cache_partial.py` builds only isolated probes. Preserved source,
maps, binaries, executable hashes and both emulator runs are under
`bench/{artifacts,results}/2026-09-29-window-cache-partial`.

- Host oracle: all eight source/destination bit alignments; 1/7/8/9/17/52/168
  widths and bounded full-screen-width cases; full, interior and last-row
  ranges; surrounding pixel preservation; bad ranges/owners/tickets/pointers;
  corrupted range metadata; full paste after prefix; cancellation/recapture.
- Compiled case 0: all 64 bit alignments with short prefixes, plus right edge
  and full-screen-width source cases. 132 rows, 480 requests, 66 presentations.
- Compiled case 1: 168x104 capture, 52-pixel prefix over rows 17..66, six rejected
  requests, then a full paste. 258 rows, 289 requests, two presentations.
- 1986 and VICE agree on every canvas and dirty-map byte. IRQs, all four caller
  I/D modes, hardware/software stack, zero page, shell low-water mark and all
  guards pass. Both worker/kernel NMI classes are observed and exactly drained.
- Bad code/header checks reject before C execution. Deliberate IRQ, zero-page,
  shell-stack and NMI faults are detected. Decoder mutation tests reject
  failures; its reuse of existing runtime checks cannot hide bad counts/pixels.

Reproduce compilation/native runs in `my-distrobox`; VICE uses the host Flatpak:

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_partial.py qualify
distrobox enter my-distrobox -- python3 tools/window_cache_partial.py run --engine 1986
python3 tools/window_cache_partial.py run --engine vice
```

## Compositor integration

The separate `tools/window_cache_partial_manager.py` candidate reuses the
damage intersection's bounded top/bottom/right to marshal a prefix. It does
this **after** composition/callbacks finish, immediately before the banked
request, because those callbacks can overwrite the shared VIC workspace.
It resets the drawing clip before handing off. There is no app-ID policy.

The private C manager measures 7,750 CODE bytes (+55), unchanged RODATA 130 and
HIGHBSS 88. The complete resident transport stays 377 bytes; 32 held padding
bytes remain. Both normal/panic segment boundaries and resident runtime helper
closures must match the normal link. The four-row poll budget, cancellation,
input handling, resize fallback and hidden/upper-strip fast paths remain.

Host tests compare every screen pixel across 117 placements, repeated lower
updates, uncovering, high-X/disjoint and three-layer cases. They deliberately
clobber the shared prefix arguments in callbacks.

## Integrated candidate results

The separate D64/D71 build is qualified in native 1986 and VICE. Clean parallel
rebuilding the generated private repository produces identical disk bytes:

- D64: `13433b995d38905916ef88dde98eb66e8629d3eea61b762eb74793d3468d519d`
- D71: `fded272e8ec0b08b69a1e0cb449d6bd002fc336071a4c4cd0c93baf73e53fbc9`

Native 1986 uses real mouse/key events, early-drag fallback, 16 retained moves,
Ctrl+C during a partial paste, console typing, oversized resize fallback and
shutdown/restart. Every retained-image pixel and the whole shadow/VIC bitmap
match. Neither retained moves nor lower-window clock updates call the wave
painter or acquire the Z80. Guards and the installed NMI handler pass. VICE
qualifies both formats for cold boot, capture, bitmap equality, NMI and graphics
restart; it is **not** the native mouse-drag qualification.

Compared with the preserved occlusion candidate, on the same 1986 inputs and
exact native-drag geometries, both disk formats measure:

| Clock damage case | Previous frames/pages | Prefix frames/pages |
| --- | --- | --- |
| Fully hidden, wave at 109,40 | 119 / 0 | 119 / 0 |
| Exposed upper strip, wave at 109,65 | 126 / 2 | 126 / 2 |
| Partial overlap, wave at 144,88 | 254 / 33 | 195 / 23 |

All 8,000 canvas bytes match across variants/surfaces. Every forced minute
update calls the clock painter once, with no repeated updates over the next
120 frames. Completion requires READY, an empty dirty map and return from the
final measured page copy. The partial-overlap case improves about 23%, but
195 PAL frames is still about 3.9 seconds: this is not general interactive
responsiveness qualification. Background composition itself remains synchronous.

Artifacts and results: `2026-09-29-window-cache-partial-manager`, including the
comparison and clean-build proof. The normal D64/D71 remain unchanged. Physical
C128/input/RESTORE testing and normal-cache promotion remain separate gates.

To test the candidate, boot its D64 or D71, then run `xinit`, `xclock &` and
`xwave &`. With the default overlapping windows, `date 121000` followed by
`date 121100` forces visible clock repairs. Check clock pixels, drag/uncovering,
console typing and graphics shutdown/restart. Use foreground `xwave` when
checking Ctrl+C during a move/paste.
