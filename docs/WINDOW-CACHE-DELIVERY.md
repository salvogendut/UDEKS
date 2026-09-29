# Window cache: delivery and C state policy

Status: **experimental delivery/lifetime gate and host-tested policy**,
2026-09-28. No pixel-cache move path is installed. The ordinary boot images
still repaint moved windows; these experimental disks do not change that.

## Delivered row core

The secondary boot payload now has an experimental prefix loaded at bank-1
`$4200`. The qualified 213-byte row core occupies `$4200-$42D4`; its private
16-byte `VCC1` identity is at `$43F0-$43FF`. This header records the version,
entry, length and additive checksum. The qualification tools verify it and
all code/padding bytes; there is **no runtime validator or enabled caller**.

The canonical USOV 0.3 header and complete scheduler/activation payload stay
byte-for-byte at `$5000+`. The load ends at the same `$6229`; only the stage-1
secondary LOAD address changes, with a measured single-byte `$50`→`$42`
difference. No additional disk LOAD, resident code or staging copier is added.
The scheduler source overlaps the proposed image lease during boot; image
storage must not be used until scheduler installation completes.

Both D71 and D64 cold-boot in VICE and native 1986. Exact 512-byte slot
comparisons pass after startup, xinit, clock/wave launch, completed wave,
console utilities, graphics shutdown and restart. Native input tests also
pass 32 scripted drags per format with a background clock and console
cancellation. These are lifetime/smoke gates, **not execution of the delivered
core**, compositor acceptance, NMI safety or physical-hardware qualification.

Sources, experimental disks and captures are preserved under
`bench/{artifacts,results}/2026-09-28-window-cache-delivery`. The normal boot
disk hashes are checked before and after qualification. No ROM images or
complete emulator snapshots are preserved in the repository.

## C window-service state

`include/udeks/window_cache_state.h` and
`src/services/window/move_cache_state.c` provide a private, pure C policy:
EMPTY → CAPTURING → READY → PASTING → READY. It checks owner, generation,
geometry, capacity and row acknowledgements. Rejected requests leave state
and row output unchanged. Host tests exercise all bit alignments, exact
capacity boundaries, cancellation/invalidation and stale acknowledgements.

The caller must explicitly certify a **complete, topmost, unoccluded** image,
freeze the capture source across its continuation, and invalidate on painting,
resize, closure, shutdown or ownership change. The policy cannot infer those
facts from pixels or an arbitrary end-paint call. It does not access hardware,
poll, call applications, or switch banks, and is not an exposed ABI.

The subsequent [private C runtime proof](WINDOW-CACHE-C-RUNTIME.md) now
executes a separately linked dispatcher/policy/row module on the private stack
in both emulators. The earlier 2,567-byte measurement below remains historical;
the new standalone module adds 118 dispatcher bytes and 28 state bytes.
Production integration and cached moves remain disabled.

The historical measurement-only link contains:

| Material | Bytes |
| --- | ---: |
| Qualified ASM row core | 213 |
| C state-policy CODE | 1,828 |
| cc65 helpers | 526 |
| Total linked code | 2,567 |
| Caller-owned lease / row descriptor | 13 / 9 |

There is no policy-object BSS or zero-page allocation. Its helpers use the
published `$06-$1F` cc65 runtime addresses, so those must be saved/restored
across a future private dispatcher. The ordinary bank-1 `$E700-$EFF0` stack
belongs to the live shell and **cannot be borrowed**.

One measured planning candidate enlarges the code reservation to
`$4200-$4CFF`, with a private C stack at `$4D00-$4DEF`, identity at
`$4DF0-$4DFF` and packed image at `$4E00-$5BFF` (3,584 bytes). The current
link leaves 249 code bytes before dispatcher and state costs. These are not
frozen allocations or a demonstrated fit. The default 168×104 image needs
2,184 bytes and fits this candidate; a 220×160 image needs 4,480 and would
fall back to redraw. This candidate differs from the earlier row-only proof's
6,144-byte image area and is **not** the current delivery disk layout.

## Next gates

1. Measure and machine-test a private C dispatcher/stack, including runtime,
   mapping, hardware-stack and IRQ preservation, guards and an unsafe-map
   negative control. Keep the entire bank-1 interval bounded and IRQ-masked;
   return to kernel I/O between rows. NMI remains a separate gate.
2. Version an explicit completed-image notification while preserving existing
   UAPP vectors. Its current table ends at `$CFFF`, so appending a vector at
   `$D000` would enter I/O and is not acceptable. An extension needs an
   explicitly measured home; no public ABI change has been made here.
3. Integrate generation-owned capture/paste continuations in the C window
   service. Preserve redraw for incomplete, obscured or oversized windows.
4. Qualify the whole resident budget and production pixel/dirty-map equality,
   input, clock, cancellation, resize/overlap and physical C128 behavior before
   enabling cached moves or claiming a speed improvement.

Reproduce (normal production inputs must already be built):

```sh
distrobox enter my-distrobox -- python3 tools/graphics_cache_delivery.py build
distrobox enter my-distrobox -- python3 tools/graphics_cache_delivery.py measure-policy
distrobox enter my-distrobox -- python3 tools/graphics_cache_delivery.py 1986
python3 tools/graphics_cache_delivery.py vice
```

`preserve` creates a new immutable evidence directory and refuses overwrite.
All work outputs stay in `build/graphics-cache-delivery`; the VICE probe closes
only its own sessions.
