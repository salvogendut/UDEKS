# Packed bitmap service integration — steps 1 and 2

Issue #55, `graphics-packed-bitmaps`, 2026-10-09. The UTRQ 0.20 service is
linked into normal and panic builds. **`xview` is unchanged.** This qualifies
the public bitmap boundary, not file streaming or a physical C128 run.

`report.json` records source/build hashes, compiler version and all three
candidate disk hashes. Actual normal/panic maps preserve four app allocations,
the 2,304-byte retained pool and all fixed reservations. Resident slack is 34
bytes; GRAPHICSCODE/GRAPHICSPATHS/GRAPHICSHELP have 69/22/6 bytes free.
The C handler is 978 CODE + 16 BSS, the assembly painter 196 CODE + 13 BSS.
Shared allocation costs 154 GRAPHICSCODE + 5 BSS. Compiler-profile changes
to unchanged serialized console/editor/VIC services recover 611 code bytes
at a cost of 29 additional scratch bytes. The layout gate requires at least
16 ordinary resident bytes after the full link.

`sim6502/check` executes 22,462 checks using the actual C handler and assembly
allocator/painter against an independent portable C oracle and pixel checks.
Its linker map places the pool at $1300. `wm-report.json` records the unchanged
60,702-byte window-manager trace comparison with the integrated layout.

`client/BMAP.BIN` is an independent relocatable native program, loaded from
a disposable test disk, with no resident imports or application-name special
case. It is **not installed in ordinary boot images**. VICE 1571/D71 and
1581/D81 runs use this same binary. Their reports identify both base and
augmented disk hashes. The input driver injects keyboard events and patches
map-checked pointer getters; it does not forge task/request replies or pixels.

Both complete VICE runs prove:

- Exact 128x80, 160x100 and 9x7 MSB-first pixels through BEGIN/WRITE/COMMIT.
- Pending uploads invisible; legacy ABI 19 rejected for bitmap operations and
  future minor 21 rejected at the request gate.
- Move/uncover from unchanged retained bytes, independent owners, failed
  allocation without peer damage, and peer preservation after compaction.
- Abort, pending exit, foreground Ctrl+C, close-box retirement and slot reuse.
- Console commands still execute and native stack guards remain intact.

Selected raw captures retain their two-byte VICE load-address headers.
Shadow and VIC headers differ ($A1E0/$6000); their 8,000 pixel bytes agree.
Host tests independently recalculate each captured picture's expected pixels.
Only the completed D71 rerun is preserved: the first driver used the wrong
close-box coordinate; that driver error was corrected before both final runs.

Legacy four-native regression reports additionally cover VICE D71 and
unmodified 1986 `d360c114e33216bf38a086f65af27533f581f6ba`, D81. These exercise
existing applications, real native keyboard/mouse paths in 1986, drag/resize,
console, cancellation, reload and guards. They are not new-bitmap tests on
1986. No new real-hardware qualification is claimed.

Reproduce from the feature worktree (never root `make clean`):

```sh
make check
distrobox-enter my-distrobox -- make -j8 boot retained-bitmap-qualification graphics-code-check
distrobox-enter my-distrobox -- python3 tools/build_graphical_example.py --source bench/packed-bitmap/client.c --name BMAP --arguments --graphics-abi 20 --static-locals --require-slot 6 --output build/bitmap-store/client --export _bitmap_stage --export _bitmap_error --export _bitmap_protocol --export _bitmap_handle --export _bitmap_uploaded
python3 tools/bitmap_service_probe.py --disk build/boot/udeks.d71 --drive 1571 --output build/bitmap-store/api-vice-d71
python3 tools/bitmap_service_probe.py --disk build/boot/udeks.d81 --drive 1581 --output build/bitmap-store/api-vice-d81
distrobox-enter my-distrobox -- python3 tools/build_graphical_example.py
python3 tools/four_native_probe.py --disk build/boot/udeks.d71 --drive 1571 --output build/bitmap-store/integrated-vice
distrobox-enter my-distrobox -- python3 tools/1986_storage_smoke_build.py --emulator /var/home/salvogendut/Dev/1986 --roms /var/home/salvogendut/Dev/1986/roms --disk build/boot/udeks.d81 --drive 1581 --four-native --output build/bitmap-store/integrated-1986
```

Next: convert `xview` to bounded CBM uploads (step 3), then qualify file/error
handling and package the larger-picture demo disks for user tests (step 4).
