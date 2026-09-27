# ADR 0011: Execute the scheduler gather from the lower VIC shadow

- Status: proposed; VICE qualified, independent-emulator gate pending
- Date: 2026-09-27

## Context

After capability and boot-console extraction, `boot_delivery.o` was the last
one-shot object in the resident kernel. Its 267-byte assembly routine validates
the `USCT` manifest, gathers the scheduler into `$1200-$15FF`, verifies the
image checksum, and returns before crt0 clears the VIC shadow.

Removing it from the packed resident segments moves `VICSHADOW` from
`$A2EB-$C22A` to `$A1E0-$C11F`, exposing exactly 267 bytes at the new lower
edge. The gather has no BSS, cc65 runtime state, or resident-symbol imports, so
it can execute directly from that boot preimage.

## Decision

1. Link the exact 267-byte gather as a split image at `$A1E0-$A2EA` and stage
   it at the bottom of `VICSHADOW`.
2. Keep the published `$2003` entry fixed. Its resident six-byte entry table
   now jumps to the absolute `$A1E0` binding; link and placement assertions
   reject drift in either address or image size.
3. Execute the gather in place before probe/crt0 installation. Capability
   staging continues immediately afterward at `$A2EB`, so the accepted
   capability and boot-console source addresses remain unchanged.
4. Let crt0 erase the gather after it returns. No copier, manifest revision,
   common-RAM byte, or resident state is added.

## Consequences

- The post-shadow tail becomes `$C120-$CEFF`, exactly 3,552 bytes.
- Together with the installed `$1C00-$1FFF` scheduler page, the final bank-0
  scheduler budget is 4,576 bytes. No measured boot-only object remains in the
  resident link.
- The current scheduler staging geometry and 533-byte scatter ceiling are
  unchanged because the new shadow prefix is occupied by the gather image.
- The frozen `$2000` kernel-main and `$2003` gather entries retain their
  published addresses.
- The direct development PRG carries the already gathered scheduler at
  `$1200`; it does not invoke the boot-only `$2003` path.

## Qualification

The split image is exactly 267 bytes at `$A1E0-$A2EA`; normal and panic maps
both place `VICSHADOW` at `$A1E0`. The following gates pass in VICE 3.10:

- D71 and D64 cold boot through the scheduler checksum gate;
- capability image equality and post-xclock service re-entry;
- boot-console image equality and xwave reuse of slot 2;
- complete 8,000-byte shadow clear, 3,552-byte tail preservation, and bank-0
  shadow/bank-1 bitmap equality;
- the real-map placement audit and host contract tests.

An independent `1986` cold boot remains the acceptance gate. Until it is
recorded, this ADR remains proposed.

## Alternatives considered

- **Keep the gather resident.** Rejected: it leaves a one-shot object in the
  exact window needed by lifecycle and scheduling policy.
- **Copy it to a temporary execution page.** Rejected: direct shadow execution
  needs no copier and the routine is already self-contained.
- **Move it into stage-1 COMMON or FINAL.** Rejected: COMMON is full at 512
  bytes, and FINAL lacks space for the 267-byte routine.
- **Change the `$2003` entry.** Rejected: that address is already qualified and
  frozen as part of scheduler delivery.
