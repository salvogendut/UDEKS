# Graphics cache placement audit

Status: measured on `graphics-window-cache-spike`, 2026-09-28; **no cache
installed**. This closes the placement inventory step in issue #6, not the
responsive-graphics acceptance gate. The current disks still use vertex replay.

Latest checkpoint: UAPP 0.3 explicit completion spends 158 CODE bytes from the
shared-raster reserve. Deferred NMI ownership spends another 77 CODE bytes,
and private window-manager C savings recover 221. Current total padding is
502 while preserving the shadow. The combined C-command candidate binding
measures 241 bytes, leaving 261 before manager/delivery integration. The real
resident controller experiment is still at least 739 bytes short; its
bank-1 image capacity in the previous combined-command proof is
3,072 bytes. This is not full-integration fit. See
[WINDOW-CACHE-COMMAND.md](WINDOW-CACHE-COMMAND.md) and
[WINDOW-CACHE-NMI.md](WINDOW-CACHE-NMI.md); earlier measurements below
remain historical evidence, not the current available budget.
Current sizing and next placement gate:
[WINDOW-MANAGER-BUDGET.md](WINDOW-MANAGER-BUDGET.md).

Newer standalone transport checkpoint: pre-C acceptance initially measured
553 resident bytes; loading the gateway source from the validated bank-1
module reduces the fully charged closure to371. This leaves131 aggregate
bytes before actual compositor hooks. Revised module delivery now passes in
both emulators/formats, and isolated normal/panic **transport-only** links
preserve every segment and runtime helper with131 residual padding bytes.
Full compositor integration is NOT yet linked/qualified; normal disks remain
unchanged. Those experimental links are not bootable because private import
bridges are stale. See [WINDOW-CACHE-COMPACT.md](WINDOW-CACHE-COMPACT.md) and
[WINDOW-CACHE-COMPACT-DELIVERY.md](WINDOW-CACHE-COMPACT-DELIVERY.md).

## Reproduce

```sh
distrobox enter my-distrobox -- make graphics-cache-placement
```

The target builds current prerequisites, assembles actual display listings and
the three cache prototype objects, and reconstructs `SCHEDOVR` byte-for-byte
from its page, tail, handler, context, vectors and common gate. It does not link
the cache into the kernel. Report/listings are in `build/graphics-cache-placement`.
Exact measured inputs, object dumps, listings and hashes are preserved in
`bench/artifacts/2026-09-28-graphics-cache-placement`. Host regression tests use
that snapshot, not whichever build directory happens to exist.

## Resident inventory

The primary map's apparent `$C120-$CEFF` gap is 3,552 bytes. Its runtime owners
account for **all** of it:

| Owner | Range | Bytes |
| --- | --- | ---: |
| Scheduler code, read-only data and live BSS | `$C120-$C872` | 1,875 |
| Scheduler envelope padding before the handler | `$C873-$C8FF` | 141 |
| Installed lifecycle handler | `$C900-$CD8A` | 1,163 |
| Remaining handler reservation | `$CD8B-$CDBC` | 50 |
| Context code/read-only data and live BSS | `$CDBD-$CEFF` | 323 |

The 141 bytes are zero-filled by the scheduler delivery envelope, including
the region after its BSS; they are not a second independent allocation.
The 50 bytes are unfilled handler capacity, not installed handler instructions.
Using either for graphics would require an explicit overlay-contract change,
separate installation and growth guards. Together they would still not fit
the cache. Do not call either “unowned” or count all 3,552 bytes as reclaim.

The low state region has only 3 unlinked bytes. High module BSS is full. The
current `MODULE` linker region `$E300-$E643` is exactly full (836 bytes), while
the memory contract includes one further module-owned byte at `$E644`.
`$E645-$E6FF` is the module/stack guard, not an available 187-byte code hole.
The resident C stack retains `$E700-$EFF0`. No shallow boot-stack observation
justifies shrinking that reservation.

The retired probe page `$0B00-$0BFF` overlaps the loader's bank-0 APP1 contract
`$0200-$0BFF`; startup-only probe lifetime does not grant permanent graphics
ownership there. The `$1C00-$1FFF` stage-1 region is now the scheduler page and
callback vectors. `$F700-$F7FF` is the transient task stack/guard, overlapped by
the shared VIC gateway workspace. The cache's copied 99-byte gateway fits at
`$F68A-$F6EC` only under serialized ownership; it does not provide a permanent
home for its source, C wrapper, state, or resumable operation.

The assembly prototype measures **1,005 CODE + 18 BSS = 1,023 bytes**, against
the 49-byte raster reserve. It needs at least **974 additional bytes** before
whole-link helper changes, manager bindings, IRQ protection or continuation
state. The separately retained eight-byte outline-mask reserve remains intact.
There is no currently qualified drop-in home. The bank-1 pixel-cache candidate
is storage, not executable bank-0 code, and its task/worker ownership still
requires the gates in [WINDOW-MOVE-CACHE.md](WINDOW-MOVE-CACHE.md).

## Next implementation: in-place raster replacement

Use compact assembly mechanisms **inside the display service**, retaining its
existing public C entry points, clipping semantics, dirty-page behavior and
cooperative serialization. Keep geometry/window policy in C. This follows
the existing assembly-mechanism/C-service architecture; it does not add
graphics policy to the microkernel or remove the compatibility shell.

The actual assembled C routines currently occupy:

| Routine | CODE bytes |
| --- | ---: |
| Clear | 109 |
| Pixel | 277 |
| Bresenham line | 580 |
| Rectangle | 410 |
| Clipped fill | 647 |
| Total | 2,023 |

Those bytes are **live code, not free space**. The new routines and their state
also need room; no saving of 2,023 bytes is claimed. Begin with a byte-span/fill
mechanism and shared clipped pixel/line mechanisms, measuring real objects and
whole-link helper effects after each increment. Retain the existing C routines
as immutable correctness oracles for standalone machine tests. Until measured
net savings cover cache **plus** binding/continuation state, keep any recovered
bytes as named padding so the `$A1E0` shadow and private generated bindings do
not drift. If replacement savings prove insufficient, stop for a service-arena
decision; do not silently shrink stacks or retire command functionality.

Only after that budget gate should cache integration proceed: bounded slices
must restore the borrowed `$F400` service page and kernel MMU profile before
any service poll, protect worker-flat intervals from IRQs, and retain the
single-owner/generation/complete-image rules. Input, cancellation, background
clock, compositor pixel equality, 1986/VICE and physical tests remain required.

This audit makes no new GUI timing or live-interrupt claim. It starts no VICE
session and changes no boot image.

The [fill/span experiment](GRAPHICS-SPAN.md) saves 86 net linked bytes; the
public ASM pixel entry saves another 87. Both now pass installed emulator gates
in [GRAPHICS-PRIMITIVES.md](GRAPHICS-PRIMITIVES.md). The measured 173 bytes stay
in named placement padding; total raster reserves are 222, leaving **at least
801 additional bytes** before bindings/state costs. The original inventory
above remains its saved baseline. The live audit measures both ASM objects,
checks them against the actual map, and rejects changed primitive padding.
No cache path has been enabled and no unowned post-shadow space has appeared.

The subsequent [shared-raster step](GRAPHICS-SHARED.md) saves another 294
linked bytes and retains them as a separate named reserve. The live audit now
measures the clear provider too and verifies both sets of placement padding:
516 bytes total, still **507 short** before bindings/bounded state. The saved
baseline inventory above remains historical; no scheduler or stack byte is
counted as newly available.

The [private bank-1 overlay experiment](WINDOW-CACHE-OVERLAY.md) is now a
measured alternative: 213 bytes in a candidate bank-1 display-code lease and
194 resident binding bytes including gateway source. The 322 remaining
reserve bytes are not yet proven sufficient for integration; the bank-1 code
and 6,144-byte image candidate also need delivery/lifetime qualification.
Current allocations and boot disks are unchanged by that standalone proof.
