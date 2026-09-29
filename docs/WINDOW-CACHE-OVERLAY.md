# Private bank-1 display overlay: row qualification

Status: **standalone machine proof, not installed in UDEKS** (2026-09-28).
The current boot disks still replay xwave vertices after moves. This is the
next placement/IRQ increment for issue #6, not a GUI performance acceptance.

The previous 1,023-byte bank-0 cache prototype cannot fit the 516-byte raster
reserve. This experiment instead puts the packing/masked-merge mechanism in
the display service's bank-1 VIC reservation. It does not put window policy
in the microkernel, move the shadow, shrink a stack, or reuse scheduler space.

## Measured candidate layout

| Material | Candidate home | Measured bytes |
| --- | --- | ---: |
| Private 8502 row core and four scratch bytes | bank 1 `$4200-$43FF` | 213 |
| Packed image | bank 1 `$4400-$5BFF` | 6,144 capacity |
| Resident binding, including its common-gateway source | bank 0 | 194 CODE, zero BSS |
| Copied gateway code | common `$F68A-$F733` | 170 |
| Row parameters / captured tail diagnostic | common `$F780-$F789` | 10 |
| Raw interleaved row staging | common `$F7B0-$F7D7` | 40 |

These are **candidate leases, not frozen production allocations**. The core
has no cc65 imports or bank-0 code dependencies. It executes from bank 1;
common helpers briefly map bank 0 to read/write the shadow, then return to
bank 1. Capture packs the selected pixels; paste merges edges into the raw
destination row and writes it back, marking exact logical dirty pages.

One entry processes at most one legal scanline: up to 40 raw/packed bytes,
with shifts bounded to seven bits. The entry captures P before SEI/CLD,
keeps the complete worker-flat interval IRQ-masked, restores kernel I/O,
and only then restores P. The binding re-installs the gateway at every row,
invalidating the outline tag; no stale-gateway reuse is assumed. There is no
callback, C execution, task switch or service dispatch inside a row.
IRQ delivery and cooperative polling **can** happen between rows; a production
continuation and its input/cancellation behavior have not yet been implemented.

The binding actually runs in the proof, rather than merely being assembled.
Its 194 bytes leave **322 of the 516 reserve** before window policy, validation,
continuation, delivery bindings, helper effects and state. This is not a claim
that the whole integrated cache already fits. The diagnostic upload code and
embedded bank-0 copy of the core are excluded from that number because they
must not survive in a production resident link.

## Evidence and its limits

Exact sources, PRGs, split images, maps, compiler identity, emulator provenance,
run-to-program hashes and raw records are preserved under
`bench/{artifacts,results}/2026-09-28-window-cache-overlay`.

Both native 1986 and VICE pass:

- all 64 source/destination bit-alignment pairs with nonbyte width;
- full-width and bottom-right rows (66 images / 132 row calls);
- a complete 220×160 snapshot (320 row calls);
- independent comparison of all 8,000 shadow bytes and 32 dirty flags;
- packed-tail padding, hardware-stack balance, all four caller I/D states,
  stage guards and canaries just beyond each used packed image;
- unchanged synthetic command/console/service bytes at `$F3A0-$F67F`, except
  the intentionally invalidated display-owned `$F3ED` outline tag;
- active CIA IRQs, with no IRQ observing a non-kernel memory profile.

The alignment run records 1,347 IRQs in 1986 / 1,340 in VICE; the large image
records 16,070 / 16,014. Counts are diagnostic observations, not performance
or scheduling guarantees. A real negative-control PRG changes **only** the
live gateway's SEI opcode to NOP. A common-RAM diagnostic IRQ handler survives
the unsafe mapping and records the violation; both emulators produce the
violation and the normal decoder rejects the records. Pixel correctness alone
would not qualify that interval.

The display is disabled and the harness's loop/guard/parameter work is
unoptimized. There is **no GUI speed claim**, no real service invocation,
no Z80/task concurrency test, and no NMI or physical-hardware qualification.
The row primitive requires validated geometry, masks, counts and cache bounds;
it is not an exposed syscall or an untrusted-input validator.

## Next integration gates

The subsequent [delivery and C-policy increment](WINDOW-CACHE-DELIVERY.md)
now qualifies experimental core delivery/lifetime on both disk formats in
both emulators. It also measures an unexecuted C policy link. The ordinary
boot disks and the row proof's layout remain unchanged; private C runtime
ownership and compositor integration are still pending.

1. Specify and measure delivery of the bank-1 core, without retaining its
   bytes in bank 0. The scheduler's bank-1 `$5000+` source is live during boot
   and overlaps the candidate image area: image storage is usable only after
   scheduler installation. One delivery option to measure is a prefix in the
   secondary payload, with core at `$4200` and the existing USOV header kept
   at `$5000`; separate load/header addresses, checksums and disk capacity
   must be guarded. No loader change is implemented by this experiment.
2. Audit every bank-1 consumer over boot, xinit/-q, task and Z80 leases, then
   freeze the graphics code/image lease. Account for the existing common
   gateway/transient-stack overlap and NMI handling; standalone serialization
   does not prove a concurrently executing service is safe.
3. Add explicit completed-image notification and generation ownership to the
   window service. Do not infer completion from an arbitrary end-paint call,
   inspect xwave private globals, or cache a newly raised obscured window.
   Preserve the published application ABI or explicitly version its extension.
4. Bound capture/paste continuations, keep input/cancellation working, and
   invalidate on painting, resize, close, shutdown or another cache owner.
   Oversized, incomplete and occluded windows retain the existing redraw path.
   A 220×160 image fits (4,480 bytes); a full-screen 8,000-byte image does not.
5. Qualify full-link budget/placement and compare production moves against
   saved no-cache disks, with exact shadow/VIC equality, clock, console,
   Ctrl+C, overlap/resize and physical C128 gates. Only then enable moves.

Reproduce from the repository root:

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_overlay.py build
distrobox enter my-distrobox -- python3 tools/window_cache_overlay.py run --engine 1986
python3 tools/window_cache_overlay.py run --engine vice
python3 tools/window_cache_overlay.py decode
```

The PRGs require raw monitor loading at `$2000`; the tools do this and close
their own VICE sessions. `preserve` refuses to overwrite an existing evidence
snapshot. These are diagnostic programs, not replacement boot disks.
