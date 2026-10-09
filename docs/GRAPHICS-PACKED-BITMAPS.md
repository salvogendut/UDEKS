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

**All four steps complete; user-tested, commit/push authorized, merge pending.**
UTRQ **0.20**, operation 23, suboperations 8–11 are available to independent
native applications through the existing `$FF16` gate. The C handler uses
the real request record and shared pool; a small graphics-service assembly
renderer calls the ordinary clipped pixel primitive. `bitmap_store.c` remains
an independent portable reference, not a duplicate production allocator.

`xview` now streams <=19-byte chunks through the public boundary, validating
header/rows/EOF/CLOSE before publishing. Its runtime drops to 2,519 bytes
(2,455 image + 64 BSS); the relocatable file is 3,217 bytes and fits slots 3/5.
VICE D71/D81 and native 1986 D81 pass exact 128x80, 160x100 and odd-width
pictures, failed-file cleanup, OOM isolation, paired viewers, drag/uncover,
clock/wave coexistence, input, mid-load Ctrl+C/close and stream reuse.
[Viewer evidence and manual checklist](../bench/results/2026-10-09-packed-viewer/README.md).
Root downloads and `main` are untouched; no new physical-hardware result.

Steps 3–4 are packaged as `build/xview/demo/udeks-packed.d71` and `.d81` in
the feature worktree. Reproduce with `make xview` in the toolchain container,
then `python3 tools/build_xview_demo.py` after building the matching boot
candidates. The full D64 is not modified to make room. User testing passed
(platform unspecified); the user authorized commit/push, not
PR/merge. Their CLOCK160/clock observation confirms the known display-pool
limit. Expanding generic retained storage and adding clear allocation errors
are follow-up work; the clock currently exits silently on failed presentation.

## Integrated placement and boundary (2026-10-09)

The former space shortfall is resolved without changing fixed reservations:

- C handler: 978 code + 16 scratch bytes; assembly renderer: 196 + 13.
  The original C renderer remains a pixel reference. Row geometry and full
  chunk padding are validated in C before any retained-byte mutation.
- The unchanged VDC console and line-editor C sources use `-Ors` with static
  locals (serialized/nonrecursive, no callbacks/yields); VIC glue uses `-Ors`
  with its existing static locals. Total object saving: 611 code bytes, with
  29 additional scratch bytes charged to the link, not ignored.
- The one-shot graphics installer and the pending-upload PRESENT guard live
  in resident service CODE. The legacy path body stays in GRAPHICSPATHS; the
  audit verifies both entry locations. No kernel policy or new overlay.
- Complete normal/panic BSS ends at `$93AD`: **34 resident bytes free**.
  GRAPHICSCODE has 69, GRAPHICSPATHS 22 and GRAPHICSHELP 6. The integration
  qualification requires 16 resident bytes after all dependencies are linked.
  The old 800-byte reclaim floor was deliberately spent on the new service.

The adapter authenticates task/window ownership, checks version/envelope,
skips pending pictures on every repaint and rejects legacy replacements while
an upload is pending. COMMIT returns EAGAIN during drag/cache transfers so an
app can yield/retry without silently losing damage. Abort, close, exit,
cancellation and subsequent slot reuse release allocations and preserve peers.
The normative wire contract is [UTRQ 0.20](../abi/window.md#packed-bitmap-surfaces-utrq-020).

Qualification includes 1,685 host tests and 22,462 actual 6502 checks (production handler, allocator
and assembly renderer), five host boundary tests in addition to the earlier
storage/pixel tests, and the unchanged 60,702-byte WM trace. Independent VICE
clients also verify versions 19/21 are rejected for the new operation, exact
pixels after move/uncover, independent owners, OOM isolation, pending
invisibility, abort/exit/Ctrl+C/close, slot reuse, console and stack guards.
Preserved reports, maps, fixture and selected pixel captures:
[integration evidence](../bench/results/2026-10-09-bitmap-integration/README.md).

Completed:

- One shared pool, mixed packed-bitmap / command / path records, preserving
  peers when inserting or discarding a picture.
- Bounded ordered uploads, no partial picture publication, atomic rejection,
  complete commit, abort and owner-retirement discard primitives.
- Exact row padding, geometry/capacity checks, independent in-progress images.
- 12 host tests plus 4,149 6502 checks, including a 2,000-byte image, exact pool
  exhaustion, 16-bit flags/arithmetic, interleaved owners and buffer guards.
- First service-code reclaim: the unchanged C window manager uses `-Ors`
  rather than `-Oirs`. Normal/panic maps, a complete 6502 call/state trace,
  VICE four-app tests and 1986 native-input regression pass (details below).
- Fixed service binding and clipped rendering, checked against the independent
  portable C core and a pixel oracle. The production shared allocator now
  supports all three format bits; ordinary command/path clients pass VICE and
  1986 regressions. Four host tests and 22,462 target checks cover this increment.

## Previous checkpoint: shared retained store (2026-10-09)

The measurements below describe the pre-integration checkpoint. Its space
shortfall and unlinked status are superseded by the completed integration above.

Following pushed checkpoint `97b8f70`, the private C transaction handler uses
the existing service-owned request and pool directly. It introduces no second
pool or four-entry allocation table. Ordered uploads, atomic errors, odd-row
padding, commit and abort match the independently compiled portable core.
The generic C renderer reads committed bits, uses the current window origin
and clipped pixel primitive, and never paints a pending image. It reacquires
the image address after compaction instead of retaining a stale pointer.

Shared address/resize/discard primitives now live in a 154-byte assembly
service helper, not the microkernel. The C equivalents remain test references.
The caller still validates index, length and total capacity before mutation.
Target tests cover 512 nonempty replacements (growth/shrink with peers), all
format flags, pool-end guards and cc65 calls as well as bitmap transactions.
Both normal/panic builds use the same helper; existing commands and paths are
unchanged apart from using the new length mask and shared resize seam.

Measured placement:

| Region/object | Before shared helper | Now |
|---|---:|---:|
| Free ordinary resident bytes | 844 | 847 |
| Free GRAPHICSCODE bytes | 0 | 80 |
| Free GRAPHICSPATHS bytes | 3 | 22 |
| Fixed-bound C handler + renderer (unlinked) | — | 1,386 CODE + 29 BSS |

This saves 99 code bytes and 3 scratch bytes. The handler alone is 1,043 code
bytes, versus the standalone core's 1,845; rendering adds 343. **It still does
not fit:** installing the 1,415-byte object entirely in ordinary resident RAM
is at least 568 bytes short, before the public adapter or any new library
helpers. The 80/22-byte holes are separate, not one contiguous reservation.
No app slot, pool bytes, stack guard, service slot or display memory was taken.

`make retained-bitmap-qualification` runs the actual 6502 code at the real
`$1300-$1BFF` pool addresses, checks normal/panic layout, and binds object,
source, simulator and disk hashes to its report. The full host suite passes
1,674 tests. VICE D71 and native 1986 D81
four-app regressions pass with the linked shared allocator; they exercise
legacy graphics, **not** the unlinked bitmap renderer. Preserved evidence:
[shared-store qualification](../bench/results/2026-10-09-retained-bitmap/README.md).

Next is a bounded service-code placement change, followed by the authenticated
request/paint dispatch and cleanup in one integration increment. The user-facing
target remains streaming `xview` at 128x80/160x100, not general optimization.

## First placement increment (2026-10-09)

Only the window-manager compile rule changes. It retains register allocation
and ordinary automatic locals, but stops inlining cc65 runtime helpers.
No C algorithm, public address, app slot, display reservation, polling budget
or static-state size changes. The Makefile is a prerequisite so an existing
build cannot silently retain the old object.

| Measurement | Before | After |
|---|---:|---:|
| Window-manager CODE | 8,055 | 7,142 |
| Window-manager RODATA / BSS / HIGHBSS | 130 / 4 / 88 | 130 / 4 / 88 |
| Resident BSS end (inclusive) | `$93A7` | `$9083` |
| Free before fixed service slot `$93D0` | 40 | 844 |

The object saves 913 bytes, but additional linked runtime helpers cost 109:
**net reclaim is 804 bytes**. No other gap, overlay or stack guard is counted.
This is useful room, **not yet enough for the standalone 1,845-byte core**.
Next integrate the shared address/compaction helpers and measure the complete
request/renderer cost before deciding whether more code reclaim is needed.

`make graphics-code-check` compiles both profiles from the same production
source, checks unchanged non-code segment sizes, matches the compact object
against the actual kernel map, and runs both under sim65. Their complete
60,702-byte drawing/transport/public-state traces are identical. The driver
and cache lease implementation are compiled once and shared between runs.
The simulated cycle totals include trace stubs; **they are not a claim about
real mouse latency**. VICE/1986 additionally exercise the actual rasterizer,
cache transport, task runtime and input path.

Qualification:

- Full host suite: 1,667 tests. Normal/panic placement and all three disk builds
  pass. The pure-C bitmap core remains unlinked.
- VICE 1571/D71: four native apps, wave drag/resize and exact pixels, independent
  unknown apps, bad-load rejection, slot reuse, Ctrl+C and console cleanup.
- Native 1986 `d360c114`, 1581/D81: actual keyboard/1351 input, four-app
  drag/resize, no extra Z80 work on moves, arithmetic/drawing, console,
  cancellation, reload, stack guards and shadow/VIC equality.
- The initial 1986 D71 attempt failed **before boot**: the harness's extra
  EMPTY/ONE files still use side-one-only packing. It is not a D71 runtime
  failure or a passed native-D71 test; VICE D71 and native D81 are the gates
  actually run. No new real-C128 qualification is claimed.

Preserved maps, simulator programs/traces and emulator reports are in
[the qualification record](../bench/results/2026-10-09-graphics-code-budget/README.md).
Host tests verify its checksums and bind both emulator results to the build.

## Data contract (now exposed through UTRQ 0.20)

Each image consumes `8 + ceil(width/8) * height` bytes in the same shared pool.
No full image is required in application RAM: a client uploads at most
19 bytes per request, yielding between disk chunks. The eight-byte service
header contains x LE16, y, width, height, stride, and received-byte count LE16.
The header is internal, not another on-disk file format.

| Picture | Tile representation | Packed allocation, including header |
|---|---:|---:|
| 80x80 | 1,280 | 808 |
| 128x80 | 2,048 | 1,288 |
| 160x100 | 3,200 | 2,008 |

For the existing demos, ALEX + CLOCKWORK drop from 2,296 to **1,405 bytes**.
They now leave room for the 344-byte clock. A 160x100 picture by itself
fits, but leaves only 296 bytes, insufficient for that clock. No combination
is promised merely because each program fits a task allocation.

Graphics suboperations, retaining op 23 / 24-byte payload, require minor 0.20.
Minors 0.18 and 0.19 remain assigned to filesystem mutations and service control:

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

1. [x] **Code placement:** complete normal/panic links and lifetime gates pass;
   no app slot, pool, guard or fixed reservation changes.
2. [x] **Public service:** authenticated adapter, clipped rendering, pending
   guards, shared `0x1fff` length mask and lifecycle cleanup are implemented
   and emulator-qualified. Existing command/path clients still pass.
3. [x] Change `xview` to stream file bytes into the service; validate the CBM
   header first, then show at most an empty/loading frame. Check EOF and CLOSE
   before COMMIT. On any read, padding, cancellation or close failure, abort
   and close the frame; no partial picture. Remove its full tile array.
4. [x] Qualify cold boot D71/D81, pixel identity (including odd dimensions), larger
   pictures, independent owners, malformed/truncated/extra bytes, OOM without
   peer damage, mid-upload Ctrl+C/close/EXIT, stream reuse, drag/uncover without
   reread, console input and the existing four-app regression. Only then offer
   new viewer demo disks for 1986/C128 testing. The completed viewer and
   file paths now pass VICE and native 1986. The user accepted the demos;
   their test platform was not specified, so no new physical result is inferred.

## Reproduce the completed increment

```sh
make check
distrobox-enter my-distrobox -- make bitmap-store-check
distrobox-enter my-distrobox -- make -j8 boot graphics-apps-check
distrobox-enter my-distrobox -- make graphics-code-check
distrobox-enter my-distrobox -- make retained-bitmap-qualification
```

The boot/layout commands qualify the **integrated bitmap service**; viewer
qualification commands are in the linked evidence README. Branch disks are rebuilt under `build/boot/`;
published `build/udeks.*` remain the accepted baseline. Never run `make clean`
at the repository root (nested worktrees).
