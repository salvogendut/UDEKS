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
   task-gate, UAPP or `$A1E0` VICSHADOW reservations. The original 516-byte
   raster reserve is now 358 after the explicit-completion seam; neither
   budget fits the original prototype. Measure linked
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

The C implementation and its exact machine records remain the immutable
correctness/timing baseline for the assembly increment below. The active-IRQ,
compositor, input/cancellation and hardware gates above remain mandatory.
Current boot images remain byte-identical and use bounded replay, not either
prototype.

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

## Assembly byte blitter qualification (2026-09-28)

The `--variant asm` build keeps range/capacity validation and row ownership
in `cache-fast.c`, uses `rows.s` for byte packing and masked paste, and uses
`transfer-lease.s` to install the same 99-byte common gateway once per complete
operation. Mask shifts are prepared per row rather than repeated for every
byte; the live pixel shift uses the accumulator. Dirty flags cover the exact
logical shadow pages touched, accounting for the unaligned `$A1E0` base.

Unlike the reference C path, this variant restores the synthetic service
page **once at the end of the complete capture or paste**, not after every
row. Its non-reentrant lease covers both the gateway and `$F400`/parameters;
no yielding, callbacks, service calls or nested drawing are permitted while
borrowed. It is not a bounded-input compositor yet. Do not enable the full
operation as a production poll without the live-IRQ, ownership and input
gates or a qualified bounded continuation that releases the lease between
slices.

Both 1986 and VICE pass the eleven full-image bank-transfer cases plus a
separate row-matrix PRG. The latter exercises all 64 source/destination bit
alignment pairs with a nonbyte 17-pixel width, every VIC row phase, a full
320-pixel row and the bottom-right pixel: 66 row checks per engine. The
decoder independently compares every resulting shadow byte and dirty flag;
matrix staging/shadow guards, counts, failure state and reserved bytes are
also checked, including zero padding in captured tail bytes. A negative-control
PRG replaces only the capture tail-mask instruction with three NOPs: displayed
pixels and dirty flags still match, but both emulators report failure 3 and
the decoder rejects the record. Masked final paste alone cannot qualify the
captured format. A host harness executes the real C wrapper with mocked row
primitives to verify geometry rejection, old-cache invalidation, lease release
and all 64 alignment pairs for six sizes. It is not used to claim that ASM
instructions ran on the host.

The unchanged probe driver, compiler flags, exact PRGs, raw records, run-to-PRG
hash manifests and source snapshots are in
`bench/{artifacts,results}/2026-09-28-window-cache-asm/`. The comparison uses
the same 1986 input fingerprints and VICE Flatpak build as the C reference.
Program hashes are verified before each run and again after the batch;
preservation rejects records tied to a different build.

| VICE primitive | C reference ticks | ASM ticks |
| --- | ---: | ---: |
| 168×104 capture, eight alignments | 1,154,116–1,623,844 | 280,801–523,225 |
| 168×104 paste, eight alignments | 1,939,409–2,758,923 | 325,486–593,322 |
| 220×160 paste | 5,186,369 | 968,935 |

Default paste is **4.56–6.87× faster** by paired case, roughly 0.33–0.59
seconds at nominal 1 MHz. Those counts exclude screen commits, old-background
restoration, chrome, input servicing and other windows. They are not a promise
of subsecond GUI release or real-hardware performance; both capture and paste
still block this standalone caller.

The wrapper is 607 CODE + 13 BSS, rows are 267 CODE + 5 BSS, and installer plus
gateway image are 131 CODE. Total is **1,023 bytes**, 250 fewer than C but
still **974 beyond the 49-byte resident raster reserve**, before whole-link
helper changes, manager/ABI bindings and continuation state. Nothing has been
linked into production to manufacture a fit. The post-shadow region is not
free merely because the primary kernel map labels it as a gap: scheduler,
lifecycle handler and context overlays occupy it at runtime.

The [runtime placement audit](GRAPHICS-CACHE-PLACEMENT.md) now reconstructs
the real scheduler payload and accounts for every post-shadow byte. There is
no qualified drop-in home. Next: measure in-place assembly replacements of
selected display-service raster routines (2,023 live C CODE bytes, **not**
reclaimed space), then integrate a bounded, serialized cache lease only after
whole-link savings cover its code, bindings and continuation state. Keep the
shadow, UAPP/task gates and stack reservations fixed unless a separately
qualified architectural change is explicitly accepted. Do not silently delete
the retained compatibility shell or shrink stacks to recover the missing KiB.
The prototype gateway assumes masked IRQs. A live path must protect the
worker-flat MMU interval and restore the kernel I/O map before delivering IRQs;
bank-flat access with I/O hidden is not a safe interrupt-service profile.

Reproduce with `--variant asm` on all four commands above; compare preserved
results with `python3 tools/window_cache_compare.py`. The standalone cache
increment above did not change boot disks. Subsequent
[display-service span/pixel integration](GRAPHICS-PRIMITIVES.md) now provides
a testable image: it holds 173 additional bytes as padding, making 222 total
and leaving at least 801 still needed before cache bindings/bounded state.
The [shared-raster follow-on](GRAPHICS-SHARED.md) adds another 294 reserved
bytes: 516 total, at least 507 short before bindings/bounded state. The cache
itself remains uninstalled; unchanged-size moves still replay pixels.

The subsequent [private bank-1 row-overlay proof](WINDOW-CACHE-OVERLAY.md)
addresses code placement rather than assuming more bank-0 savings. It measures
213 bank-1 core bytes and a 194-byte resident binding, with 6,144 bytes left
for the image. Active-IRQ row tests and a real SEI-removal negative control
pass both emulators. This does **not** qualify production delivery, cache
ownership or bounded compositor integration, and does not enable pixel moves.

Latest: [bounded C command and completion seam](WINDOW-CACHE-COMMAND.md).
The application completion notification is installed, while the combined
bank-1 command remains standalone-qualified. After installed
[NMI deferral](WINDOW-CACHE-NMI.md) and
[private manager savings](WINDOW-MANAGER-BUDGET.md), current padding is 502 bytes;
its 241-byte binding would leave 261 before manager/delivery costs. A real
bank-0 controller/link experiment is still at least 739 bytes short.
No pixel-cache move is enabled.

The later [integrated live candidate](WINDOW-CACHE-LIVE.md) now enables bounded
cached moves on **separate test disks**, with unchanged normal boot outputs.
This supersedes the preceding standalone checkpoints, not their preserved
historical evidence. Manual visual/input and physical/performance gates remain.
