# Window move pixel cache: placement spike

Status: **machine transfer prototype qualified with IRQs masked; not resident**. This follows
[focused xwave replay](BOUNDED-REPLAY.md) on `graphics-window-cache-spike`
and is tracked by issue #6. The current boot disks still redraw xwave after a
move. Do not describe this note or its host model as a speed qualification.

## Why the wave reappears gradually

At drag start, the manager recomposes the old rectangle without the moving
window. That erases the only rendered copy in the bank-0 shadow; the live
bank-1 VIC bitmap is subsequently committed from that shadow. xwave retains
525 *heights*, not an image. The focused callback resets its draw cursor and
the existing four-vertex poll path reprojects the cached heights at the new
coordinates. The Z80 does not recompute the heights, but 8502 rendering and
commits still take time. Simply skipping that callback would leave a blank
client area (or stale pixels); keeping the old pixels visible during the drag
would violate the outline-only movement rule.

## Candidate surface and byte format

Physical bank-1 `$4200-$5BFF` is a 6,656-byte *candidate* scratch lease.
It lies after the `$4000-$40FF` transfer backup and `$4100-$417E` pointer
templates, before the `$5C00` screen matrix and `$6000` bitmap. `xinit`
does not initialize it as visible screen or sprite data. It is within the
currently reserved VIC window, not the Z80 `$2000-$3FFF` code, APP1/APP2,
`$8000-$89FF` task backup, or `$A000-$D0FF` bootfs. This is not yet a frozen
allocation; the installer and all future VIC-window consumers must be audited
before claiming ownership.

Use a compact, pixel-aligned 1-bpp image of a *topmost* window. For 168×104,
stride is 21 bytes and image size is 2,184 bytes; a 220×160 resized image
needs 4,480 bytes and also fits. Capture strips the source
x-coordinate's bit offset; paste merges the destination's bit offset and
masks both edge bytes so adjacent windows/background are not overwritten.
VIC high-resolution row interleave is used, not linear scanlines. The
independent host model `tools/window_move_cache_spike.py` passes every source
and destination bit alignment, randomized backgrounds, nonbyte widths and
the right screen edge against a per-pixel reference. It rejects oversize
geometry before mutation. A full 320×200 image needs 8,000 bytes and must
use the existing computed redraw path (or a later larger allocation).

## Required resident path before enabling moves

1. Prove the cache's bank-1 ownership over xinit, xinit -q, Z80 leases,
   task switching and bootfs access. Reserve it in the memory contract only
   after the qualification; one window owns the lease at a time.
2. Capture the *complete*, topmost, unoccluded window from the bank-0 shadow,
   known to match the committed bank-1 bitmap, **before** `begin_drag()` erases it. An incomplete plot or
   raised obscured window must fall back. The window service, not xwave,
   should own cache validity and generation.
3. At unchanged-size release, merge the packed image at the new coordinates
   into the bank-0 shadow under the compositor's damage clip, then commit
   dirty pages. Never write only the bank-1 bitmap: later shadow commits
   would erase the move. Restore the old background and compose higher
   windows in z order. Cancel/stale generations on resize, close, xinit -q,
   new damage, or a different window taking the lease.
4. The 8502 cannot execute ordinary bank-0 C while the worker-flat profile
   exposes bank-1 RAM. A small always-mapped transfer gateway must stage
   the packed image through common RAM, without crossing the frozen gateway,
   task-gate, UAPP or `$A1E0` VICSHADOW reservations. The current 49-byte
   resident raster reserve is insufficient for the measured C prototype. Measure linked
   CODE, gateway-copy extent, and placement before enabling the path. If it
   cannot fit, make a service-placement decision; do not silently move the
   shadow or overwrite worker/task memory.
5. Gate against a saved no-cache disk: pixel equality at several unchanged
   move offsets, partial/occluded/raised windows, oversized resize fallback,
   exact shadow-versus-bank-1 equality after each release, background clock,
   Ctrl+C during drag/replay, console input and real-hardware behavior.
   Measure both release latency **and** time until the full image is visible.

## Machine-level transfer qualification (2026-09-28)

`bench/window-cache/` is a standalone prototype, **not** a new OS service or
published ABI. It captures pixels from the bank-0 shadow into packed rows,
copies those rows into the candidate bank-1 cache, and pastes them back into
the bank-0 shadow with masked edges and dirty-page marking. The 99-byte
assembly gateway runs at `$F68A-$F6EC`, within the existing shared VIC
gateway workspace. Each transfer restores the kernel MMU profile before
returning to C.

`$F400` is live bootfs/lifecycle service code, not free buffer memory. The
prototype borrows it without yielding, restores all 256 bytes from the bank-1
`$4000` backup after every row, and invalidates the outline-gateway tag when
installing its own gateway. It uses private parameter bytes at `$F380-$F383`
only in the standalone program. None of those writes is enabled in UDEKS.
The service page contains a known synthetic pattern, not an executing bootfs
module; survival of real services remains an integration gate.
Active IRQs, concurrent service/task activity, cache generations and damage
clipping are **not** qualified by this test.

Eleven exact PRGs pass in both native 1986 and VICE: all eight source bit
offsets paired with all eight destination offsets, nonbyte width, a 1×1
bottom-right pixel, and a 220×160 image. An independent per-pixel decoder
checks all 8,000 shadow bytes and 32 dirty flags, before/after cache guards,
the capacity boundary, restored service bytes, rejected geometry and MMU
profile. A host harness executes the actual C over all 64 alignment pairs
for six sizes, including a near-capacity 320×166 image. Preserved binaries,
source snapshots, machine records, build sizes and provenance are in
`bench/{artifacts,results}/2026-09-28-window-cache-transfer/`.

The unoptimized **diagnostic driver** avoids a cc65 constant-pointer store
optimizer defect observed while publishing its completion record. The cache
code itself uses the production `-Oirs` flags. The record timers isolate
capture and paste; background setup, service validation and result copying
are outside the timed intervals. Display is disabled and IRQs are masked,
so these are primitive CIA timer counts, not drag-release or GUI timings.

For 168×104, VICE capture takes 1,154,116–1,623,844 ticks and paste takes
1,939,409–2,758,923 ticks. The 220×160 paste takes 5,186,369 ticks. Even
before screen commits, the C paste still takes roughly 2–3 seconds for the
default image at nominal 1 MHz. This is **not acceptable as the fast move
implementation**, and it is not an end-to-end comparison with bounded replay.

Measured cache C is 1,113 CODE + 30 BSS bytes; assembly installation and its
gateway image add 130 CODE bytes. Total prototype material is **1,273 bytes**,
1,224 more than the 49-byte raster reserve, before whole-link library changes,
window-manager bindings or ABI entries. The copied gateway fits common RAM,
but that does not make its resident source code fit. Existing module/app
spaces and published gates must not be silently repurposed.

Next: retain this C implementation and its exact machine records as the
correctness/timing baseline; build and measure a dedicated assembly byte
capture/paste path, reducing gateway installation and service-page restore
overhead under an explicit non-reentrant lease. Then make a measured graphics
service-placement decision before integrating it. The active-IRQ, compositor,
input/cancellation and hardware gates above remain mandatory. Current boot
images remain byte-identical and use bounded replay, not this prototype.

Reproduce from the repository root:

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_bench.py build
distrobox enter my-distrobox -- python3 tools/window_cache_bench.py run --engine 1986
python3 tools/window_cache_bench.py run --engine vice
python3 tools/window_cache_bench.py decode
```

These raw PRGs require monitor loading at `$2000` followed by entry at
`$2000`; they are not BASIC launchers or replacement boot disks. The tools
perform that setup and terminate their own VICE sessions.
