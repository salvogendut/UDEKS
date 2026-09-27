# Window move pixel cache: placement spike

Status: **candidate design, not resident implementation**. This follows
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
2. Capture the *complete*, topmost, unoccluded window from the committed
   bank-1 bitmap **before** `begin_drag()` erases it. An incomplete plot or
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
   resident raster reserve has **not** been shown sufficient. Measure linked
   CODE, gateway-copy extent, and placement before enabling the path. If it
   cannot fit, make a service-placement decision; do not silently move the
   shadow or overwrite worker/task memory.
5. Gate against a saved no-cache disk: pixel equality at several unchanged
   move offsets, partial/occluded/raised windows, oversized resize fallback,
   exact shadow-versus-bank-1 equality after each release, background clock,
   Ctrl+C during drag/replay, console input and real-hardware behavior.
   Measure both release latency **and** time until the full image is visible.

The host spike proves the *format*, not machine timing or bank-safe transfer.
No cached image will be advertised until the resident path and these gates
pass. Current bounded replay remains the safe fallback.
