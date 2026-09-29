# Raster scratch integration — issue #10

Candidate branch `graphics-raster-integration`, based on PR #9's corrected
outline mask. This revision integrates static line/fill temporaries only;
arguments and raster algorithms are unchanged. The matching artifact directory
contains the exact integrated D71/D64 disks, eight standalone PRGs, the display
source and the native input harness. No ROMs or full snapshots are included.

## Results

- cc65 `V2.18 - Fedora 2.19-15.fc44`, production `-Oirs`: automatic reference
  CODE 4,339/BSS 0; static CODE 4,258/BSS 32. Copied arguments lose 45 bytes
  net and are not integrated.
- The net 49-byte saving is held in named resident CODE padding. Production
  CODE is 29,477 bytes, BSS 702; VICSHADOW stays `$A1E0-$C11F`. UAPP/common
  gates and the legacy row reservation are unchanged. The link report compares
  normalized automatic/static objects **with** that padding; its automatic
  reference shadow is `$A211`, not a bootable production layout.
- All 16 standalone result records match independent pixels and dirty flags.
  Line timer-count reductions are 11.709/12.481%; fills 23.589/23.859%.
  IRQs/display are disabled in these probes; these are not GUI latency tests.
  The raw CIA count discrepancy between engines remains recorded.
- Active-display native 1986 stress passes 32 drags on each integrated format
  with a background clock: partial then cached painting, edge positions,
  lifecycle JMP protection, exactly 21 row leases, no cached recomputation,
  foreground cancellation and subsequent console input.
- The same harness on the preserved PR #9 D71 (`baseline-drag.log`) versus
  integrated D71/D64 measures worst partial release 348 → 290 PAL frames,
  cached release 619 → 541. Ctrl+C-to-wave-stopped is **194 → 216** frames;
  the latter excludes subsequent shell-idle waiting but includes the native
  key helper's release sampling and six settling frames. Cancellation is not
  improved in this script. These are specific deterministic emulator runs,
  not a universal worst-case bound or hardware timings. Cached repaint still
  takes seconds; issue #6 performance acceptance stays open.
- Normal native console typing/backspace/history, pointer dragging, early
  foreground cancellation and background apps pass. VICE D71/D64 scheduler,
  graphics/utility and input-wait smokes pass (saved logs). VICE shadow clear
  and reclaimed-gap checks pass; saved `shadow-drawn.bin` equals all 8,000
  bytes of bank-1 `vic-bitmap.bin`.
- `make clean` followed by container `make -j8 boot all placement-check` passes;
  disk hashes before and after rebuild match the artifact manifests:
  D71 `bf6ac315e6453bc4fe5bd116c602315c9befe9adb743c8c90b4dae9416860240`,
  D64 `86e42d28d0650b123b1a5984e1712ac52528457e06b10f1e9db93e3389591948`.

The final 1986 reruns used tracked-clean revision
`39797864231dd0c52431df3ed9b4c724af2d19a9`; no sibling emulator files were
modified by this work. Compiled input fingerprints and tracked status are in
`1986-provenance.json`. VICE is the
installed Flatpak x128 (3.10). Static scratch is safe only under the audited
cooperative no-yield/no-callback drawing ownership; future preemption requires
serialization. Physical-C128 testing of this optimization is pending.

## Reproduction

In `my-distrobox`, build with `make -j8 boot all placement-check`, then run
`tools/graphics_raster_audit.py` and `tools/graphics_raster_bench_build.py`.
Run `tools/graphics_raster_bench_run.py --engine 1986` in that container and
`--engine vice` on the host, with a shared `--output`, and decode it using
`tools/graphics_raster_bench_decode.py`. The link audit takes explicit
`--baseline .../baseline.o --candidate .../static-scratch.o`.

For native disk checks use `tools/1986_input_smoke_build.py --roms ../1986/roms
--drag-stress 32 --drag-clock --disk <disk>` with separate output/snapshot/log
paths for each run. Compare against
`bench/artifacts/2026-09-27-xwave-drag-freeze/udeks.d71`, not the buggy PR #7 disk.
On the host, run `tools/task_yield_probe.py --timeout 90 --disk <disk>` and
`tools/shadow_boot_probe.py --vic-compare`. The tools terminate their owned
VICE sessions.
