# First packed-bitmap placement increment

Issue #55, branch `graphics-packed-bitmaps`, after storage checkpoint `482c8b8`.
**No packed-bitmap API, renderer or larger-picture viewer is installed yet.**

The only production change is compiling the unchanged
`src/services/window/window_manager_cached.c` with `-Ors`, formerly `-Oirs`.
Window-manager state and all fixed reservations remain unchanged. Object CODE
saves 913 bytes; 109 additional linked helper bytes leave **804 bytes net**.
Both included maps put the resident BSS end at `$9083`, leaving 844 bytes
before the time-service slot. This is not enough for the standalone bitmap
core: deduplicate the retained-store helpers and measure full integration next.

`budget.json` binds source/map/disk hashes and compiler version. The unchanged
WM source is in parent `482c8b8`; the new test sources are under
`bench/packed-bitmap/`. The two simulator executables produce identical
60,702-byte traces, preserved in full, covering drawing calls, cache transport,
public window state, geometry, moves, resize, clicks and lifecycle operations.
The fixture supplies trace-only raster functions; cycle totals include those
stubs and must not be represented as real mouse latency.

`vice/d71.json` records the completed four-native test on VICE/1571. The native
1986 result and log record the D81/1581 keyboard/1351 test against unmodified
emulator revision `d360c114e33216bf38a086f65af27533f581f6ba`. These exercise
actual drawing and canvas/shadow equality, four apps, drag/resize, no redundant
worker work, console recovery, cancellation, slot reuse and stack guards.
Both results bind the same candidate disk hashes as `budget.json`.

The first native-D71 attempt failed during fixture packing, before emulator
launch: the smoke helper still puts EMPTY/ONE on side one only. It is not
represented as a passed test. No new real-hardware test is claimed.

Reproduce in this worktree (never root `make clean`):

```sh
make check
distrobox-enter my-distrobox -- make -j8 graphics-code-check
distrobox-enter my-distrobox -- python3 tools/build_graphical_example.py
python3 tools/four_native_probe.py --disk build/boot/udeks.d71 --drive 1571 --output build/bitmap-store/vice-four-d71
distrobox-enter my-distrobox -- python3 tools/1986_storage_smoke_build.py --emulator /var/home/salvogendut/Dev/1986 --roms /var/home/salvogendut/Dev/1986/roms --disk build/boot/udeks.d81 --drive 1581 --four-native --output build/bitmap-store/1986-four-d81
```

ROMs are local/user-owned and are not part of these artifacts. Published
`build/udeks.*` downloads and `main` are untouched; branch candidates are
under this worktree's `build/boot/`.
