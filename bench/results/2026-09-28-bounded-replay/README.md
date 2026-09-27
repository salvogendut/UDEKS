# Focused cached xwave replay — issue #6

Built on `graphics-bounded-replay`, based on the unmerged raster-integration
branch (issue #10). Exact D71/D64 disks and source snapshots are in the
matching artifact directory. The linked resident placement remains frozen:
`VICSHADOW $A1E0-$C11F`, with no UAPP or common-RAM gate changes. The xwave
binary is 1,701 emitted bytes and its bootfs fits the existing limit.

The real application host harness passes bounded poll, obscured synchronous
clip, geometry changes, full-grid bitmap comparison, cache reuse and
stop/relaunch. A focused repaint callback performs no vertex rendering;
normal polls paint at most four vertices. The native 1986 runner used the
same user-facing 1351/keyboard APIs and 32 drags on D71 and D64, with a
background xclock. Both pass lifecycle guard, clock survival, Ctrl+C and
subsequent console input. Last replay finishes after 674 additional PAL
frames with exactly 21 Z80 row leases and no fallback. All 32 drag releases
are recorded, including position and progress.

Against the integrated-raster disk, tested worst partial release changes
290 → 279 PAL frames and cached release 541 → 266. However, final visual
completion after the last release takes ~13.5 more seconds in 1986; this
trade-off must be evaluated on physical hardware. This is not an overall
compositor acceptance result: obscured-window content, background clock,
damage clearing and window chrome remain synchronous. No benchmark of
full-image completion against a same-position baseline is claimed.

VICE D71/D64 scheduler, app, utility and input-wait smoke logs pass. The VICE
shadow clear and installed-tail checks pass; saved `shadow-drawn.bin` and
`vic-bitmap.bin` have different two-byte load-address headers but identical
8,000-byte bitmap payloads. Physical hardware has not yet been tested with
these disks. Native 1986 was the tracked-clean revision and input fingerprints
in `1986-provenance.json` (the same emulator inputs as the raster-integration
comparison). No sibling files were edited.

Reproduce from the repository root in `my-distrobox`:

```sh
make -j8 boot all placement-check
python3 tools/1986_input_smoke_build.py --roms ../1986/roms \
  --drag-stress 32 --drag-clock --disk build/boot/udeks.d71 \
  --snapshot build/bounded-d71.vsf --log build/bounded-d71.log
python3 tools/1986_input_smoke_build.py --roms ../1986/roms \
  --drag-stress 32 --drag-clock --disk build/boot/udeks.d64 \
  --snapshot build/bounded-d64.vsf --log build/bounded-d64.log
```

On the host, run `python3 tools/task_yield_probe.py --timeout 90 --disk
build/boot/udeks.d71` (and `.d64`), and
`python3 tools/shadow_boot_probe.py --vic-compare`. Owned VICE processes are
terminated by the probes.
