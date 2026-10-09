# Packed bitmap surfaces — issue #55

Branch `graphics-packed-bitmaps`, worktree `build/packed-bitmap`, based on
`5a07408` (merged viewer PR #54).

## Outcome and scope

Allow larger pixel-exact pictures without representing every 8x5 pixels as an
eight-byte drawing command. Keep the existing 2,304-byte retained-display pool
and four task allocations. Graphics policy remains in services; file parsing
remains in `xview`. CBM version 1 does not change.

First visible targets: 128x80 and 160x100 pictures; independent windows where
the combined allocation fits; drag/uncover from retained RAM without disk
reads. Full 320x200 backing storage, expansion RAM, panning, scaling and an
allocator redesign are deferred. The first larger viewer should be a feature
increment, not an open-ended graphics optimization project.

## Current status

**Storage/transaction core implemented, not integrated into the OS.**
`src/services/window/bitmap_store.c` is pure C, tested on the host and with
real 6502 instructions under `sim65`. It is deliberately absent from both
resident link recipes. No public request ABI changes: existing graphics
operations extend through 0.17, while filesystem mutations and service control
already use 0.18 and 0.19. The prototype operations below are private proposals,
not available to disk applications.
`xview` and all boot images remain unchanged. There is no larger-picture
emulator or hardware result yet.

Completed:

- One shared pool, mixed packed-bitmap / command / path records, preserving
  peers when inserting or discarding a picture.
- Bounded ordered uploads, no partial picture publication, atomic rejection,
  complete commit, abort and owner-retirement discard primitives.
- Exact row padding, geometry/capacity checks, independent in-progress images.
- 12 host tests plus 4,149 6502 checks, including a 2,000-byte image, exact pool
  exhaustion, 16-bit flags/arithmetic, interleaved owners and buffer guards.

## Data contract (private prototype)

Each image consumes `8 + ceil(width/8) * height` bytes in the same shared pool.
No full image is required in application RAM: a future client uploads at most
19 bytes per request, yielding between disk chunks. The eight-byte service
header contains x LE16, y, width, height, stride, and received-byte count LE16.
The header is internal, not another on-disk file format.

| Picture | Tile representation | Proposed packed allocation, including header |
|---|---:|---:|
| 80x80 | 1,280 | 808 |
| 128x80 | 2,048 | 1,288 |
| 160x100 | 3,200 | 2,008 |

For the existing demos, ALEX + CLOCKWORK drop from 2,296 to **1,405 bytes**.
They would then leave room for the 344-byte clock. A 160x100 picture by itself
fits, but leaves only 296 bytes, insufficient for that clock. No combination
is promised merely because each program fits a task allocation.

Proposed graphics suboperations, retaining op 23 / 24-byte payload. Allocate a
new request minor during integration; do not reuse 0.18 or 0.19:

| Subop | Payload after opcode and owned window handle |
|---|---|
| BEGIN (8) | width LE16, height, x LE16, y; remaining bytes zero |
| WRITE (9) | sequential byte offset LE16, count 1..19, counted bytes; trailing bytes zero |
| COMMIT (10) | zeros; requires exactly all bytes received |
| ABORT (11) | zeros; discards only an in-progress upload |

Initial bounds: width 1..240, height 1..175, image rectangle within 320x200.
Windows still apply their client clip. Bits are MSB-first, black ink; unused
low row bits must be zero. BEGIN requires an empty retained image (`EBUSY`
otherwise), and charges its entire allocation immediately. Rejected requests
leave both the pool and all four records unchanged. COMMIT only changes
visibility after complete data; no partial display on a failed file read.

The caller must authenticate task/window ownership before selecting the
index. The store deliberately has no public pointers or unauthenticated
window lookup. Its view is borrowed only within a serialized service action;
never keep it across another request, allocation change or yield.

## Production integration gates

1. **Qualify code placement first.** The measured core object needs 1,845
   code bytes and 22 static-scratch bytes, excluding new library dependencies,
   request integration and renderer. That is not a complete installation
   budget or a final incremental size: integration should share address and
   compaction helpers with the existing retained store, not install two pool
   managers. The live graphics segment is already 1,792/1,792 bytes. The retired
   glyph code window has only 3 executable bytes left before live tile maps;
   GRAPHICSHELP has 6 and ordinary resident code/state has 40 before the
   time-service slot. These are not a viable home for this core. Keep the
   module unlinked until a separately measured service-code placement/reclaim
   passes both normal/panic links and lifetime gates. Do not steal an app
   slot, shrink the pool, or assume boot staging/stack guards are free.
2. Add the authenticated request adapter, generic clipped bitmap renderer and
   cleanup hooks. Every retained-length consumer must use the new length
   mask (`0x1fff`); bitmap/pending use bits 14/13 and existing paths bit 15.
   Old `0x7fff` arithmetic would corrupt peer placement. Pending images must
   not reach the old tile renderer. Reject PRESENT/PATHS/DELTA while an upload
   is pending. Close, cancellation, EXIT, reap and launch reuse must release
   it, including before COMMIT. Preserve legacy commands/paths unchanged.
3. Change `xview` to stream file bytes into the service; validate the CBM
   header first, then show at most an empty/loading frame. Check EOF and CLOSE
   before COMMIT. On any read, padding, cancellation or close failure, abort
   and close the frame; no partial picture. Remove its full tile array.
4. Qualify cold boot D71/D81, pixel identity (including odd dimensions), larger
   pictures, independent owners, malformed/truncated/extra bytes, OOM without
   peer damage, mid-upload Ctrl+C/close/EXIT, stream reuse, drag/uncover without
   reread, console input and the existing four-app regression. Only then offer
   new demo disks for 1986/C128 testing and advertise the new ABI minor.

## Reproduce the completed increment

```sh
make check
distrobox-enter my-distrobox -- make bitmap-store-check
distrobox-enter my-distrobox -- make -j8 boot graphics-apps-check
```

The last command qualifies the **unchanged production baseline**, not this
unlinked prototype. All three rebuilt disks match the published baseline
byte-for-byte. Never run `make clean` at the repository root (nested worktrees).
The complete host suite passes 1,661 tests, including the 12 new store tests.
