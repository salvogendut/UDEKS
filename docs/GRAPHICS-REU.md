# Optional REU graphics backing storage

Branch `graphics-reu`, worktree `build/graphics-reu`, based on the committed
packed-bitmap viewer (`fe57e7f`). The user selected REU and VICE for this
follow-up on 2026-10-09. The user has accepted the working desktop and authorized
commit/push/PR/merge, including the underlying packed-bitmap work. The README
shows the supplied screenshot. Root published disk snapshots are not refreshed;
the milestone's D71/D81 demos are preserved with its qualification evidence.

## Feature target

Let `xview /clock160.cbm &` coexist with `xclock &` and other windows without
application-specific exceptions. The current 2,304-byte retained pool has
only 296 bytes left after CLOCK160, less than the clock's 344-byte drawing.
Use optional REU memory for retained graphics while preserving all four task
allocations and the existing internal-RAM backend on stock machines.

Do not promise more task slots, larger executable allocations, full-screen
pictures, scaling, panning, or faster drawing as part of this feature.

## Integrated bitmap service — package 2

The owned-store component was committed/pushed as `3cb8ae0`; this worktree
now installs it behind UTRQ 0.20 BEGIN/WRITE/COMMIT/ABORT and the renderer.
Applications are unchanged. A committed REU bitmap retains only its 8-byte
header in the internal pool; command/path drawings keep their original backend.
Without a successfully discovered REU, the original full internal bitmap is
used. The store still offers only four 8 KiB extents, not all expansion memory.

Production ownership and delivery (normal and panic maps must agree):

| Physical region | Owner/lifetime |
| --- | --- |
| Bank 0 `$D000-$DFFF` | Bitmap policy/store/renderer/state; exposed only in kernel-flat mode, after Z80 boot staging is retired |
| Bank 1 `$7300-$82FF` | Boot-only 4 KiB source in the secondary payload; copied before VIC bitmap or native slot 5 can use it |
| Bank 1 `$4180-$419D` | Bounded 30-byte DMA buffer, after both sprite templates and before cache code |
| Common `$F400-$F4FF` | Borrowed only for bounded cross-bank copies; restored from existing immutable bank-1 `$4000` backup before returning |
| REU `$000000-$007FFF` | Four independent owned 8 KiB bitmap extents |

The hidden image has a checked identity and 16-bit checksum, explicit zero
state, and a linker-bounded trailer. No stage-1/common reservation grows.
Moving the existing bitmap handler/renderer funds the resident driver and
gates. Current measured sizes: **3,232 hidden CODE + 114 state bytes**, 16-byte
identity/trailer; ordinary BSS ends `$9397`, leaving 56 bytes before `$93D0`.
No app code allocation, software stack, retained pool or VIC shadow moves.

Long rendering calls keep IRQs enabled. The existing IRQ trampoline restores
the interrupted MMU configuration; the common NMI stub only queues an event.
Each short copy/DMA masks IRQs, drains pending NMI with I/O visible, then
returns to the hidden caller in kernel-flat mode. DMA uses the already-active
VIC bank 1; discovery runs before VIC graphics activation. The transport
preserves P, so the caller explicitly compares its returned errno instead of
branching on inherited Z. This distinction was caught by exact-pixel VICE
qualification (uploads alone were correct but fetched rows initially blank).

The shell/native foreground page initializers now skip `$00/$01`, matching
the graphical-app initializer: these are CPU ports, not task scratch. Their
old clear loop corrupted two hidden-code bytes during shell startup in VICE.
The live test compares installed code before and after applications run.

Owner cleanup releases REU state on close/cancel/slot reuse and on successful
replacement by a legacy command/path list. Rejected replacements leave the
old object intact; pending uploads remain invisible. Host tests cover four
maximum-size images, compaction, row padding, failed reads and stock fallback.

The user accepted the integrated desktop on 2026-10-09, without specifying a
hardware configuration or exhaustive checklist. Package 3 still includes
broader interaction and real C128/REU acceptance.
REU does **not** add task slots: clock + wave + CLOCK160 fills the existing
allocation set because wave needs the joined allocation. A new native CAT can
run after closing wave; the VDC shell itself remains interactive throughout.
The demo supports two independent CLOCK160 viewers without consuming two
full images in the 2,304-byte pool. Repaint is still pixel rendering from
backing storage, not a promised hardware blit or performance improvement.

Build candidates with container `make -j8 boot graphics-apps-check
retained-bitmap-check placement-check`; then host `tools/build_xview_demo.py
--output build/reu-graphics/demo-N`. Run `tools/reu_graphics_probe.py --disk
build/reu-graphics/demo-N/udeks-packed.d81 --picture
build/reu-graphics/demo-N/CLOCK160.CBM --reu 512` (repeat `--reu 0`). Only
disposable media/REU files are used and each owned VICE session is closed.
Native boot disks are required; the direct early-bring-up PRG does not deliver
the secondary image. Root published downloads remain untouched.

## Three implementation packages

1. **Transport and discovery — qualified.** Private 8502 DMA
   primitive, C capacity policy, bounded requests, absent-device behavior,
   bank/speed/processor-state preservation and reproducible failure controls.
   The standalone foundation is now bound into boot by package 2.
2. **Generic backing store and actual service integration — implemented.** Budget the code,
   metadata, boot delivery and transfer buffer from the real normal/panic
   maps. Add owned storage handles behind the existing bitmap operations;
   keep BEGIN/WRITE/COMMIT/ABORT semantics, pending invisibility, renderer
   clipping, retirement and allocation failure atomicity. Prefer moving the
   bulk bitmap payloads first, leaving small command/path lists internal.
   The existing public app API should not need REU-specific calls.
3. **Visible qualification and test disks — partly complete.** CLOCK160 + clock + wave where
   task allocations permit; independent viewers; move/resize/cover/uncover;
   input, Ctrl+C, RESTORE, Z80 work, load cancellation, exhaustion, close and
   slot reuse. Repeat without REU to prove stock fallback. Preserve VICE
   evidence and provide demo disks, then request real-C128/REU qualification.
   Coexistence, independent images, exact pixels, cleanup/reuse and stock
   fallback now pass VICE; broader interaction/hardware gates remain.

Keep these as feature-sized packages, not a new long sequence of unrelated
micro-optimizations. IPC remains the proposed architectural milestone after
this user-requested graphics-capacity extension.

## Foundation checkpoint: transport contract (private)

At the foundation checkpoint, `include/udeks/reu.h`, `src/services/memory/reu.s`
and `reu_capacity.c` were not in the normal or panic resident links. They are
now bound by the production integration above; their preserved candidate
source comments and standalone evidence describe that earlier checkpoint.
`make reu-probe-build` still links a separate
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

## Historical placement investigation (before integration)

The completed bitmap service leaves only **34 ordinary resident bytes**. The
candidate transport is 261 CODE + 15 BSS; C discovery is 600 CODE + 10 BSS,
plus 159 bytes of cc65 helpers in the standalone link (and its runtime ZP).
Some helpers may already be resident, but no saving is counted without a real
map. Discovery is boot-only; the transport must remain callable after boot.
No application allocation, time-service slot, stack guard, staging lifetime,
common-RAM reservation, or visible bitmap space may be silently appropriated.

The package-2 investigation confirmed that bank-0 `$0200-$0BFF` still serves
synchronous console programs, bank-1 `$4000-$40FF` is the live bootfs gateway
backup, and `$F68A-$F7EF` is shared gateway/stack workspace, not free storage.
None is appropriated by this increment. RAM under bank-0 I/O (`$D000-$DFFF`)
is a possible **unqualified** service home after bootstrap, not a selected
placement: ownership/delivery, flat-map entry, I/O calls, NMI and buffer homes
still need a complete production proof. Do not equate an unlisted range with
free RAM or load the standalone program into the live system.

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

## Foundation checkpoint: owned backing store component

`reu_store.c` / `reu_store.h` were qualified as a private C storage component
before bitmap integration. The production binding is described above.
The component reserves four independent 8 KiB
extents in REU `$000000-$007FFF`: 32 KiB offered on every supported REU.
This covers four maximum current bitmap objects (5,258 bytes each), without
allocating a large bitmap/page allocator in precious C128 RAM. It does not
claim to offer all detected expansion memory. The app-independent storage
policy knows owner IDs and byte counts, not `xview` or image filenames.

- One object per authenticated owner; service-private nonzero handles.
- Sequential writes of 1–256 bytes; pending objects cannot be read; commit
  requires every declared byte. The future bitmap adapter still validates
  geometry, row padding and the public <=19-byte request chunks.
- Reject ownership/state/size/offset errors before touching metadata or DMA.
  New allocations fail atomically and leave the output handle untouched.
- Four disjoint extents avoid compaction and preserve every peer on reuse.
  Release clears all metadata without reading stale expansion contents.
  New owners cannot read old contents: full upload/commit is required first.
- Owner retirement must release storage before recycling a task ID. Handles
  never repeat during a boot; after 65,535 successful allocations, fail with
  ENOMEM until reboot instead of accepting stale handles after wrap.
- A DMA error can mean a partial transfer. The entire store goes offline;
  no reads, writes or commits succeed, but cleanup remains available. Release
  every object and rediscover successfully before reinitialization. This is
  not a promise of atomic recovery from damaged physical memory.
- No REU returns ENODEV without any allocation or store DMA. Choosing the
  existing RAM backend remains the integration adapter's responsibility.

The module measures **1,372 CODE + 39 BSS bytes** with cc65 `-Os`, excluding
transport, compiler helpers and the production adapter/buffer. The store
accepts only trusted synchronous service calls; it is not a foreign-pointer
syscall, a scheduler, a general REU allocator, or a loadable service yet.

Host tests exercise CLOCK160-sized and maximum-size peers, ordered 19-byte
uploads, capacity/owner/handle rejection, random lifecycles, every failing
write position before/after a partial DMA, read failures and handle exhaustion.
The actual cc65 build passes VICE absent/128/256/512/1024 KiB cases. Each
present case verifies four full 8 KiB objects plus reuse (32,769 bytes),
1,861 bounded transfers, 14 rejections and injected partial-write recovery.
A deliberately corrupted read fails independent byte comparison.

The standalone fixture uses a bank-1 staging buffer and keeps RCR `$49`
during store transfers; guards and untouched bank-0 peers are checked. Its
`$6000` buffer and `$F100` copy gate are **scratch-only proof addresses**,
occupied by live services/display in UDEKS. Discovery still uses bank 0.
Interrupt sources are disabled: this is not live desktop, raster artifact,
RESTORE, scheduler, 1986 or physical-hardware qualification.

Evidence: [owned-store qualification](../bench/results/2026-10-09-reu-store/README.md).
Build with container `make reu-store-build`, run host
`python3 tools/reu_store_probe.py`. Its temporary VICE sessions mount no disks
and close automatically. Never run this destructive scratch probe inside
UDEKS. **1,721 host tests pass**; normal boot/layout builds pass and the three
`build/boot` disk images remain byte-identical to the foundation baseline.
Package 2 remains open for placement/delivery and bitmap-service
integration; package 3 remains the user-visible coexistence/fallback gate.

## Reproduce the foundation gate

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
