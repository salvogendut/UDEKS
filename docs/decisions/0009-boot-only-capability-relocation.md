# ADR 0009: Boot-only `hardware_capability.o` relocation into application slot 1

- Status: accepted
- Date: 2026-09-27

## Context

At the start of reclaim step 4, `hardware_capability.o` (967 staged bytes, 968
runtime bytes) was budgeted as boot-only: it runs during capability probing
and service start, and its bytes are dead once the service has started. It was
still linked resident, so its bytes were budgeted reclaim rather than realized
reclaim.

[`docs/BOOT-STAGING-MAP.md`](../BOOT-STAGING-MAP.md) shows the free payload
holes total 805 bytes (largest contiguous 230), so the 967-byte object does not
fit the current delivery capacity, and the measured scheduler scatter ceiling
is 766 bytes after the manifest carve. Two capacity claims are explicitly
rejected:

- **Consumed staging containers are not delivery capacity.** After stage 1
  consumes a container (`$AD00-$CEC2` and friends), those bytes become runtime
  scratch, not payload capacity. Capability staging cannot overlap a container
  before it is consumed, and the delivery must not depend on a container's
  consumption order. No part of this plan counts consumed staging containers
  as free delivery capacity.
- **The unowned padding is not delivery capacity** until its ownership is
  frozen, per the staging map.

The real capacity comes from extracting the object itself. `_udeks_capability_start`
is linked at `$2CEB` inside `CODE`, and the packed segment order is `CODE`,
`RODATA`, `DATA`, `BSS`, `BOOTDELIVERY`, then `VICSHADOW`. The resident data
currently ends at `$AC3D` with the VIC shadow at `$AC3E-$CB7D`. Removing 968
bytes (967 initialized plus the one BSS byte) repacks every segment after the
object's contributions, moving the data end to approximately `$A875` and the
shadow to approximately `$A876-$C7B5`. That frees a contiguous source region
`$A876-$AC3D` (968 bytes) directly below the current shadow start: nearly
exactly the 967 bytes the image needs.

**The source budget is 968 minus every new resident byte.** The staged image is
967 bytes, so this change may add at most **one resident byte**. The re-entry
guard, any resident capability-delivery code, and any resident constant all
move the shadow upward one byte for one byte. In particular:

- a separate resident gather cannot fit under this premise;
- the capability copier and checksum logic must live outside the packed
  resident image;
- the measured `$F700` refactor did not fit, so the selected fallback stages
  that code in the scheduler-hole allocation immediately after the capability
  image and executes it before crt0 clears the shadow;
- if the guard adds a resident byte, that byte is recovered elsewhere or is
  charged against the post-extraction capacity proof.

The stack-independent assembly guard has a net cost of 31 resident bytes. The
final resident data ends at `$A894`, so extraction realizes 937 bytes below the
old `$AC3E` shadow start. The 967-byte image therefore uses those 937 bytes plus
30 bytes of the existing
first scheduler hole, and its 102-byte installer uses the following hole
bytes. The complete occupied source is `$A895-$ACC1`, still below the fixed
manifest at `$ACD9` and leaving a 634-byte scheduler-delivery ceiling.

The generated assembly already places `_udeks_capability_start` first in
`CODE`, so the image can link directly at `$0200`. A three-byte entry veneer
would make the image at least 970 bytes and exceed the 968-byte source, so the
veneer is rejected. Any future veneer requires an explicit code-size reduction
of at least the veneer's size.

The region is inside the new VIC shadow span, so crt0's shadow clear destroys
it. The image must therefore be copied out before crt0 runs, exactly like the
scheduler gather. The runtime home is application slot 1 (`$0200-$0AFF`, 2,304
bytes), which is free during boot; the gather destination bound already allows
it (`< $16` high byte).

## Decision

1. **Split the object from the resident link.** `hardware_capability.o` is
   removed from `cfg/8502-bootstrap.cfg`'s kernel link and linked separately by
   a new config at `$0200`: the `CODE` segment starts at `$0200`,
   `hardware_capability.o` is the first object in that segment, and the link
   asserts `_udeks_capability_start == $0200`. No veneer is added. The
   post-extraction linker map must measure every resident addition. If the
   extracted range alone is shorter than 967 bytes, the build may use only an
   explicitly allocated adjacent scheduler hole whose reduced ceiling still
   fits the scheduler; it may not fall back to consumed containers.

2. **Generated import bridge, private build binding.** The object has 32 import
   records resolving to 23 unique symbols (21 absolute, 2 zero-page; cc65
   runtime helpers and resident kernel functions). A generated `SYMBOLS` block
   resolves each one from the kernel map's export list. The
   bridge is a private build binding between the resident kernel and this one
   boot-only image, not a public ABI, and it is regenerated from the same build
   as the kernel map. The generator preserves each symbol's address type from
   the kernel map, in particular zero-page types, and a test locks the bridge
   against the map. The make step also emits linker force-import flags (`-u`)
   for the object's absolute imports into both resident links, so every
   provider is listed in both maps. Zero-page `ptr1` and `sp` remain natural
   resident imports because ld65's command-line force import is absolute.
   Declaration-only anchors were measured and rejected because ld65 omits
   providers that are only declared.

3. **Build dependency chain.** The make edges encode, in order: capability
   object, generated force-imports, resident kernel links and maps, generated
   typed bridge, capability image and its checksum constants, stage-1 gateway,
   then the disk images. No step may run
   before its inputs exist, so parallel clean builds are deterministic.

4. **Fixed address in the resident descriptor.** The resident capability
   descriptor contains the literal `$0200`; `src/services/table.s` continues to
   reference the resident descriptor and does not itself reference `$0200`.

5. **Exact-length delivery with a checksum.** The delivery copies the exact
   967-byte image from its single contiguous source to `$0200` and verifies a
   build-time checksum over those exact bytes. It does not use the scheduler's
   padded 1,024-byte page semantics, and it does not use the `USCT` scatter
   manifest. Source address, length, and checksum are build-time constants
   asserted against the linked image. A 102-byte one-shot installer follows
   the image, runs in place at `$AC5C-$ACC1`, records checksum failure in the
   boot-chain record, and is erased by crt0 with the rest of the shadow. The
   existing `$F700` FINAL and `$F7D8` scheduler copier remain unchanged. The
   one BSS byte is cleared at the runtime home.

6. **The scheduler protocol is unchanged; its allocator sees the new
   occupancy.** The existing manifest, gather, `$F7D8` copier, image format,
   and evidence path are unchanged. The capability image and installer are
   registered as an occupied `$A895-$ACC1` region. The current 297-byte
   scheduler still fits with a measured 634-byte delivery ceiling. The
   capability copy runs after ordinary stage-1 relocation and before the jump
   to the protected FINAL/crt0 chain.

7. **One-shot capability startup.** A stack-independent assembly veneer guards
   `udeks_service_start_all()` against re-entry before compiled C can adjust
   the active cc65 software stack. It reuses the existing registry-ready state
   and returns zero without reading the descriptor or application slot 1. The
   capability descriptor has no poll entry or later invocation path. Both
   facts are locked by tests.

## Consequences

- The VIC shadow start moves from `$AC3E` to `$A895` and its end to `$C7D4`;
  the 31-byte idempotence guard accounts for the difference from the initial
  estimate. The staging map, audit, shadow evidence, and
  placement tests are updated to the post-extraction map, and the exact ranges
  are asserted from the map.
- Realized reclaim includes the extracted object's runtime bytes; the
  `hardware_capability` budget is no longer merely prospective.
- Gates required before acceptance:
  1. the post-extraction map proves the exact contiguous source allocation
     after every resident addition and reports any scheduler-hole charge;
  2. the delivery cost is measured: 102 staged installer bytes and eight
     additional COMMON bytes (`509/512` used), with FINAL unchanged at 214
     bytes and SCHEDINSTALL unchanged at 35 bytes;
  3. clean-build determinism (identical artifacts and hashes across two clean
     builds, including parallel builds);
  4. identical `HCAP` records on D71, D64, VICE, and `1986` cold boots;
  5. shadow-clear evidence for the moved shadow start and the cleared
     capability region;
  6. an `xclock`-after-overwrite gate: after the capability code has been
     overwritten by `xclock`, explicitly invoke `udeks_service_start_all()` and
     verify the defined "already started" result without touching `$0200`, and
     the system stays alive.
- `boot_console.o` (1,450 bytes) remains budgeted; this ADR does not claim its
  capacity.

## Qualification

All acceptance gates passed on 2026-09-27. Two clean parallel builds produced
identical D71, D64, panic disk, resident images, maps, capability image,
installer, stage-1 gateway, and direct PRG hashes. `make placement-check`,
`make shadow-probe`, `make capability-probe`, the direct-PRG MMU smoke, and
534 host tests pass. VICE D71/D64 and 1986 revision `f9c6a24` produce identical
`HCAP` records and exact slot-1 images; the xclock overwrite/re-entry test is
byte-stable. The raw records and hashes are preserved in
`bench/results/2026-09-27-capability-relocation`.

## Alternatives considered

- **Scatter across the existing holes (805 bytes total, 766-byte ceiling).**
  Rejected: the object does not fit.
- **Stage in consumed payload containers (`$AD00-$CEC2`).** Rejected: those
  bytes are runtime scratch, the containers must stay intact until consumed,
  and the delivery must not depend on consumption order.
- **Freeze the unowned padding (236 bytes, minus the I/O-resident Z80 tail).**
  Rejected: still short of 967 bytes and it weakens ownership rules.
- **A three-byte entry veneer at `$0200`.** Rejected: the image would exceed
  the source by at least two bytes; only a code-size reduction of the same
  magnitude would make it viable.
- **A separate resident gather.** Rejected: any resident byte comes out of the
  968-byte source, and the image plus a gather cannot fit.
- **Refactor the `$F700` FINAL region.** Rejected after measurement: it could
  not contain the exact copier/checksum path without displacing protected
  delivery code. The scheduler-hole fallback retains 634 bytes of delivery
  capacity, more than the current 297-byte scheduler requires.
- **Use application slot 2 (`$1200-$1BFF`) as the runtime home.** Rejected:
  slot 2 is the scheduler gather temporary and `xwave`'s slot.
- **Shrink or relocate the VIC shadow.** Deferred: it changes runtime graphics
  ownership and is not needed if extraction yields the contiguous source.
