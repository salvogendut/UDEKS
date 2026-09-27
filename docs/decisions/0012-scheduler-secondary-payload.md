# ADR 0012: scheduler secondary boot payload

- Status: proposed
- Date: 2026-09-27

## Context

The lifecycle state and request-policy modules now link within the frozen
`$1C00-$1FFF` scheduler page and `$C120-$CEFF` tail. Their tail emits 3,359
bytes and reserves 71 bytes of BSS. The original native autoboot payload has
only 533 bytes of scatter capacity after all live staging is protected, so it
cannot deliver this tail without corrupting the bootfs, task loader, common
gateways, or boot-only service images.

The C128 KERNAL provides `SETBNK` (`$FF68`) and `LOAD` (`$FFD5`) specifically
for loading a file into a selected RAM bank. These calls remain available at
the start of stage 0, before UDEKS establishes its common-RAM map and stops
depending on the inherited KERNAL.

## Decision

Package the scheduler tail as a normal closed PRG named `SCHEDOVR` on side one
of both boot images. Its two-byte disk load address is `$5000` in bank 1. The
loaded bytes begin with a versioned `USOV` envelope containing the bank-0
destination, exact emitted length, BSS address/length, and a 16-bit checksum.

The implementation is deliberately incremental:

1. the disk builder installs the deterministic file and proves that its chain
   round-trips on the D71 and the side-one D64 view;
2. stage 0 will use `SETBNK`/`LOAD` to place it in bank 1 before changing the
   MMU/common-RAM contract;
3. a bounded one-shot installer will validate the envelope, copy the image to
   `$C120`, clear its BSS, and leave the existing 1 KiB scheduler-page scatter
   path intact for the first integration;
4. only after VICE, `1986`, and physical-hardware qualification may the older
   scatter delivery be consolidated.

No KERNAL entry is retained or called after stage 0. Failure to load or
validate the secondary payload is a boot-chain failure, never a partial
scheduler start.

## Consequences

- Scheduler delivery no longer competes with bootfs or common-RAM staging.
- D71 and D64 use the same side-one file and therefore the same load path.
- Stage 0 grows and becomes responsible for preserving the boot device number;
  its exact byte budget and ROM-call behavior require emulator and real-C128
  qualification before this ADR can be accepted.
- The on-disk envelope is a private boot ABI, not a user executable format and
  not a general filesystem service.
