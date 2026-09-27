# xwave drag freeze: outline-mask corruption

Issue: [#8](https://github.com/salvogendut/UDEKS/issues/8).
The pre-fix disk is preserved in
`bench/artifacts/2026-09-27-xwave-responsive`; fixed D71/D64 images are in
`bench/artifacts/2026-09-27-xwave-drag-freeze`.

## Cause and correction

In `prepare_outline()`, the reference cc65 2.19 `-Oirs` compilation of
`OUTLINE_BUFFER[base + 6u] = (unsigned char)(0xFFu << (7u - (right & 7u)))`
emits `jsr tosshlax; tay; jsr staspidx`. The store's Y index is the mask,
not zero. Thus it corrupts memory beyond the two 15-byte outline records.
At x=25 with width=168, the second record's destination is `$F395` and its
mask is `$80`: the write lands at `$F415`, replacing the lifecycle
dispatcher's `JMP $C900` opcode `$4C` with `$80`.

The baseline bus-watch log captures that write at PC `$9267` (staspidx),
frame 9398, with kernel MMU `$3E`, ptr1 `$F395`, Y `$80`, and caller return
address `$8DB5` in prepare_outline. The immutable bank-1 service backup
remained correct. The CPU continued running the shell, but its YIELD request
no longer reached the scheduler; graphics/input service polling therefore
stopped, leaving the outline visible and making Ctrl+C ineffective.
This is an UDEKS compiled-code defect, not evidence of a stuck Z80 or a
1986 emulation defect.

The equivalent mask `~(0x7Fu >> (right & 7u))` avoids that unsafe generated
store. It saves eight CODE bytes; an explicit eight-byte resident reserve
keeps the frozen boot-delivery shadow at `$A1E0-$C11F` unchanged. The reserve
is outside all common-RAM transport copies. No ABI or runtime bank changes.

## Qualification

- The same native-input harness rejects the preserved baseline disk: its
  fourteenth drag does not finish and the captured dispatcher opcode is `$80`.
- Fixed D71 with a background xclock and fixed D64 without one each pass
  32 drags: 16 during partial painting, then 16 after completion. All eight
  horizontal bit alignments are exercised. There are exactly 21 successful
  Z80 row leases and no new leases during cached dragging. Native Ctrl+C
  stops the foreground wave; subsequent `echo console alive` is accepted.
- The stress harness checks the lifecycle JMP after drag preparation and
  release. Raw final pages retain `$4C $00 $C9` at `$F415`; baseline does not.
- Host C record tests exercise both records at every legal x coordinate and
  representative y/band boundaries, with surrounding guards. These test C
  semantics, **not** the cc65 optimizer; the linked native runs qualify that.
- Reference-container `make placement-check` passes. VICE cold boot,
  graphical apps/utility commands and cooperative input waits pass. The
  shadow probe clears all 8,000 bytes, preserves the 50-byte reclaimed-gap
  preimage, and compares the bank-0 shadow with the bank-1 bitmap exactly.
  These are VICE smoke/transport checks, not a native VICE drag-stress pass.

1986 was built in `my-distrobox` from revision
`0b1151c0b512f46c141cd961cd6735cbe30aa443`. The sibling tree contains
user-owned display/fullscreen edits; they were not altered. Compiled source
and header fingerprints are recorded in `1986-source-SHA256SUMS`.
No ROMs or complete ROM-containing snapshots are committed.

Reproduce in the reference container:

```sh
make -j8 boot all
python3 tools/1986_input_smoke_build.py --roms ../1986/roms \
  --drag-stress 32 --drag-clock --snapshot build/drag.vsf --log build/drag.log
python3 tools/1986_input_smoke_build.py --roms ../1986/roms \
  --disk build/boot/udeks.d64 --drag-stress 32 \
  --snapshot build/drag-d64.vsf --log build/drag-d64.log
```

For the negative control use the preserved baseline disk with the same
arguments. Manual SDL dragging and physical-C128 confirmation remain open.
The separate raster optimization checkpoint must be rebased and remeasured
on this fix before integration.
