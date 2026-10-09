# Shared retained-store qualification

Issue #55, after pushed compiler-profile checkpoint `97b8f70`. This increment
links shared pool address/resize/discard helpers into both boot variants.
**Bitmap request/renderer code remains unlinked; xview is unchanged.**

`report.json` binds source/build/disk hashes and compiler version. The target
program, map and output are preserved under `sim6502/`; it executes the actual
C request/renderer and assembly allocator against an independently compiled
portable C oracle, with the pool at the real `$1300-$1BFF` addresses. 22,462
checks cover bounded transactions, errors leaving all bytes untouched, pending
invisibility, MSB-first pixels, screen clipping, complete images, abort, peer
preservation, exact exhaustion and 512 nonempty grow/shrink replacements.
Host tests additionally verify client-rectangle clipping and 1,200 generated
valid/invalid transactions. Raster stubs verify coordinates/pixels, not VIC
timing. This is not a larger-picture emulator or physical-C128 qualification.

The 154-byte assembly helper replaces duplicate C allocation primitives and
keeps all four slots and the full 2,304-byte pool. Both real linker maps are
included. Net saving is 99 code + 3 scratch bytes: ordinary slack is 847,
GRAPHICSCODE has 80 free, GRAPHICSPATHS 22. The unlinked handler/renderer is
1,386 CODE + 29 BSS, at least 568 bytes beyond ordinary contiguous slack,
before new public dispatch or libraries. Separate holes are not combined or
treated as permission to change fixed reservations.

VICE/1571 D71 and native 1986/1581 D81 regressions use the report's disk hashes.
They exercise the linked allocator with **existing** command/path clients:
four apps, drag/resize, stack guards, console, cancellation and slot reuse.
Selected VICE shadow/bitmap pairs preserve actual canvas equality (each raw
file retains its distinct two-byte load-address header). The native
run uses unmodified sibling emulator `d360c114e33216bf38a086f65af27533f581f6ba`.
Neither report claims to exercise the unlinked bitmap producer. No VICE session
was left running. Root main/published disks and user images were not changed.

Reproduce from the feature worktree:

```sh
make check
distrobox-enter my-distrobox -- make -j8 boot retained-bitmap-qualification graphics-code-check
distrobox-enter my-distrobox -- python3 tools/build_graphical_example.py
python3 tools/four_native_probe.py --disk build/boot/udeks.d71 --drive 1571 --output build/bitmap-store/retained-vice
distrobox-enter my-distrobox -- python3 tools/1986_storage_smoke_build.py --emulator /var/home/salvogendut/Dev/1986 --roms /var/home/salvogendut/Dev/1986/roms --disk build/boot/udeks.d81 --drive 1581 --four-native --output build/bitmap-store/retained-1986
```

Never root `make clean`: build contains active worktrees. Local ROMs are not
redistributed. The next gates are fitting/enabling the public service and
streaming viewer, then larger-picture emulator and user tests.
