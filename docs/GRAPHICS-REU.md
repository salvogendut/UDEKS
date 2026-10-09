# Optional REU graphics backing storage

Branch `graphics-reu`, worktree `build/graphics-reu`, based on the committed
packed-bitmap viewer (`fe57e7f`). The user selected REU and VICE for this
follow-up on 2026-10-09. No PR, merge, issue creation or publication has been
performed for this slice. The viewer branch and root `main` remain unchanged.

## Feature target

Let `xview /clock160.cbm &` coexist with `xclock &` and other windows without
application-specific exceptions. The current 2,304-byte retained pool has
only 296 bytes left after CLOCK160, less than the clock's 344-byte drawing.
Use optional REU memory for retained graphics while preserving all four task
allocations and the existing internal-RAM backend on stock machines.

Do not promise more task slots, larger executable allocations, full-screen
pictures, scaling, panning, or faster drawing as part of this feature.

## Three implementation packages

1. **Transport and discovery — standalone VICE-qualified.** Private 8502 DMA
   primitive, C capacity policy, bounded requests, absent-device behavior,
   bank/speed/processor-state preservation and reproducible failure controls.
   This is a candidate service component, NOT a module installed at boot.
2. **Generic backing store and actual service integration.** Budget the code,
   metadata, boot delivery and transfer buffer from the real normal/panic
   maps. Add owned storage handles behind the existing bitmap operations;
   keep BEGIN/WRITE/COMMIT/ABORT semantics, pending invisibility, renderer
   clipping, retirement and allocation failure atomicity. Prefer moving the
   bulk bitmap payloads first, leaving small command/path lists internal.
   The existing public app API should not need REU-specific calls.
3. **Visible qualification and test disks.** CLOCK160 + clock + wave where
   task allocations permit; independent viewers; move/resize/cover/uncover;
   input, Ctrl+C, RESTORE, Z80 work, load cancellation, exhaustion, close and
   slot reuse. Repeat without REU to prove stock fallback. Preserve VICE
   evidence and provide demo disks, then request real-C128/REU qualification.

Keep these as feature-sized packages, not a new long sequence of unrelated
micro-optimizations. IPC remains the proposed architectural milestone after
this user-requested graphics-capacity extension.

## Implemented transport contract (private)

`include/udeks/reu.h`, `src/services/memory/reu.s` and `reu_capacity.c` are not
in the normal or panic resident links. `make reu-probe-build` links a separate
program at `$2800`; its addresses are **not** a production placement proposal.

- Serialized 8502 caller, kernel IO profile `$3E`; never called by IRQ/NMI or
  concurrently with another REC user. Caller must own the expansion and the
  physical host buffer. This private primitive is not a foreign-pointer ABI.
- Stash/fetch blocks of 1–256 bytes. Reject zero (the REC interprets a zero
  length as 64 KiB), oversized blocks, invalid direction/bank, host intervals
  outside `$0200-$CFFF`, and 24-bit expansion wrap **before IO writes**.
- Host bank is explicit, independently of the CPU's active bank. The driver
  selects it through RCR bit 6, preserves common-RAM configuration and does
  not switch the CPU mapping. It temporarily selects 1 MHz and disables IRQs.
  The original RCR, speed and processor status (including I/D) are restored.
- DMA executes immediately; it does not arm the `$FF00` trigger. Check the
  completion bit after the CPU resumes, with no unbounded software wait.
  This is not protection against hardware that physically holds DMA forever.
- Errors: EINVAL=22, absent device ENODEV=19, transfer/discovery failure EIO=5.
  REC registers are exclusively owned, not saved/restored or re-armed.
  Capacity and allocation bounds still belong to the higher-level service.

C discovery saves all eight probe-byte preimages before writing tags, checks
bank independence/aliasing and restores/verifies the contents before publishing
a capacity. It recognizes 128 and 256 KiB, and verifies a **512 KiB prefix** of
larger REUs; it does not claim to measure their full size. A hardware failure
during restoration can leave probe bytes damaged; the device remains offline.
This requires exclusive ownership, even though successful discovery restores
the contents. It is a sizing probe, not a full RAM integrity test.

The 1764's unpopulated upper banks can echo the REC bus latch, not a constant
`$FF`. Discovery primes that latch with a different known byte before checking
those banks. Initial assumptions of wrapping/constant-FF upper banks failed
the live 256 KiB gate and were corrected before this checkpoint.

## Placement and display gates for package 2

The completed bitmap service leaves only **34 ordinary resident bytes**. The
candidate transport is 261 CODE + 15 BSS; C discovery is 600 CODE + 10 BSS,
plus 159 bytes of cc65 helpers in the standalone link (and its runtime ZP).
Some helpers may already be resident, but no saving is counted without a real
map. Discovery is boot-only; the transport must remain callable after boot.
No application allocation, time-service slot, stack guard, staging lifetime,
common-RAM reservation, or visible bitmap space may be silently appropriated.

DMA and VIC use the same RCR bank selection. Restoring it after a transfer
does **not** prove an artifact-free active display while it was changed.
Prefer a service-owned staging buffer in the already VIC-selected bank and a
bounded existing bank-copy path, or explicitly qualify another display-safe
strategy. Freeze buffer placement and NMI/IRQ ownership before integration.
Standalone flag preservation is not a live scheduler/RESTORE qualification.
Do not launch DMA while the Z80 owns the machine.

The REC's address counter also has device-specific wrap behavior. Initial
allocations stay within the discovered prefix and each transfer must fit its
allocation and capacity; do not interpret the 24-bit field as permission to
cross a 512 KiB hardware counter boundary on a larger REU.

## Reproduce the current gate

From this worktree:

```sh
distrobox-enter my-distrobox -- make -j8 reu-probe-build
python3 tools/reu_probe.py
python3 -m unittest discover -s tests -p 'test_reu.py'
```

The host runner creates six temporary VICE sessions, attaches no disks, and
closes each owned session. It tests no REU, 128/256/512/1024 KiB, and a deliberately
misbanked transport. **Never load this standalone probe into a running UDEKS:**
it owns scratch areas in both RAM banks and deliberately overwrites selected
REU locations for transport tests (unlike the restoring discovery routine).

Each present-device run covers 128 round trips: both host banks, both original
VIC banks, initial 1/2 MHz, all I/D combinations, and lengths 1/19/255/256.
Checks include peer bytes, adjacent guards, partial-block tails, cross-64K REU
transfers, the final configured expansion page, eight invalid requests without
request/register mutation, unique per-bank tags and independent verification
of those tags after a second discovery. The absent case returns cleanly.
The negative control forces bank-1 DMA into bank 0 and must fail comparison.

Host tests cover aliasing and unpopulated banks, absent/unknown geometry,
every one of 48 transfer-failure positions before/after mutation, corrupted
reads, withheld capacity on failure and strict result decoding.

Preserved evidence: [REU transport/discovery](../bench/results/2026-10-09-reu/README.md).
Final checks: 1,707 host tests pass, a fresh container boot/layout build passes,
and D64/D71/D81 candidates match the packed-bitmap branch byte-for-byte.
There is no UDEKS live-desktop, 1986 or physical-REU pass yet and **no new boot
disk to test** in this package. The graphics pool has not expanded yet.

## References

- [Commodore 128 Programmer's Reference Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf), MMU RAM configuration and REC programming. RCR bit 6 selects the bank on stock 128 KiB systems.
- [VICE REU implementation](https://github.com/VICE-Team/svn-mirror/blob/main/vice/src/c64/cart/reu.c), REC registers, 1700/1764/1750 geometry, bus latch and counter wrap. Used as hardware-behavior reference, not copied implementation.
- [VICE options](https://vice-emu.sourceforge.io/vice_7.html): `-reu -reusize 512` for the primary development target.
