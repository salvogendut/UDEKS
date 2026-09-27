# ADR 0012: scheduler secondary boot payload

- Status: proposed
- Date: 2026-09-27

## Context

The lifecycle state and scheduler modules link within the frozen
`$1C00-$1FFF` scheduler page and the bank-0 tail. The host-tested policy module
was subsequently removed from the resident image; the production payload now
copies 3,045 tail bytes through `$CD04`, including the permanent request
handler, and clears 151 bytes of core BSS. The original native autoboot payload has
only 533 bytes of scatter capacity after all live staging is protected, so it
cannot deliver this tail without corrupting the bootfs, task loader, common
gateways, or boot-only service images.

The C128 KERNAL provides `SETBNK` (`$FF68`) and `LOAD` (`$FFD5`) specifically
for loading a file into a selected RAM bank. These calls remain available at
the start of stage 0, before UDEKS establishes its common-RAM map and stops
depending on the inherited KERNAL.

## Decision

Package the scheduler page and tail as a normal closed PRG named `SCHEDOVR` on
side one of both boot images. Its two-byte disk load address is `$5000` in bank
1. The loaded bytes begin with a versioned `USOV` envelope containing both
destinations, exact emitted lengths, BSS address/length, and a combined 16-bit
checksum. The page is zero-padded to exactly 1 KiB so the later fixed copier
never propagates uninitialized bytes.

The implementation is deliberately incremental:

1. the disk builder installs the deterministic file and proves that its chain
   round-trips on the D71 and the side-one D64 view;
2. stage 0 uses `SETBNK`/`LOAD` to place it in bank 1 before changing the
   MMU/common-RAM contract, and rejects a load error or wrong end address;
3. a 192-byte one-shot installer occupies only the legacy task-gate reservation
   `$FF05-$FFC4`, validates the magic and checksum, copies the page to `$1200`,
   copies the tail to `$C120`, and clears its BSS;
4. the existing `$F7D8` copier installs the page at `$1C00`, whose entry then
   replaces the one-shot installer with the permanent task gate from `$CE00`;
5. the IRQ trampoline at `$FFC5-$FFCF` and CPU handoff at `$FFD0` remain
   untouched. The older `$2003` scatter gather stays published for compatibility
   but is no longer used by the production boot path.

No KERNAL entry is retained or called after stage 0. Failure to load or
validate the secondary payload is a boot-chain failure, never a partial
scheduler start. VICE qualification covers D71 and D64 cold boot, exact linked
page/tail installation, the exact post-clear task-1 lifecycle BSS image,
permanent task-gate replacement, VIC shadow equality, and application-slot
reuse. The ADR remains proposed until the same boot path passes in `1986` and
on physical hardware.

## Consequences

- Scheduler delivery no longer competes with bootfs or common-RAM staging.
- D71 and D64 use the same side-one file and therefore the same load path.
- Stage 0 grows and becomes responsible for preserving the boot device number;
  its exact byte budget and ROM-call behavior require emulator and real-C128
  qualification before this ADR can be accepted.
- The on-disk envelope is a private boot ABI, not a user executable format and
  not a general filesystem service.
