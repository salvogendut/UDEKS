# ADR 0010: Boot-only console composition in application slot 2

- Status: proposed; VICE qualified, independent-emulator gate pending
- Date: 2026-09-27

## Context

`boot_console.o` contributes 911 bytes of code and 539 bytes of read-only data
to the resident kernel, but it runs only once while the bordered VDC root
console is composed. Keeping those 1,450 bytes resident would consume nearly
half of the post-shadow scheduler window.

The earlier capability extraction moved the VIC shadow to `$A895`. Removing
`boot_console.o` repacks the resident segments and moves it again to
`$A2EB-$C22A`. After the capability image and installer, this creates an exact
1,450-byte contiguous source at `$A718-$ACC1`. Application slot 2 provides a
contiguous boot-time runtime home, but its lower `$1200-$15FF` page is already
the scheduler gather buffer.

## Decision

1. Link `boot_console.o` as an exact 1,450-byte private image at
   `$1600-$1BA9`. It has no BSS. A zero-size resident binding publishes
   `_udeks_boot_console_build = $1600` to the console service.
2. Generate a private typed import bridge from the object's 18 import records,
   canonicalized to 14 symbols: 12 absolute and two zero-page. Normal and
   panic maps must agree on every address and type. The bridge asserts the
   entry, code, rodata, and BSS layout at link time.
3. Stage the image at `$A718-$ACC1`. A 99-byte one-shot installer at
   `$0B50-$0BB2` copies the exact image to `$1600`, verifies its 16-bit build
   checksum, and publishes a boot-chain failure before halting on mismatch.
4. Run the console installer after capability installation and before entering
   the protected final installer. The final installer installs the scheduler
   page through `$1200-$15FF`, then replaces the complete `$0B00` page with
   `probe.o`.
5. Reserve the installer's complete linked extent when allocating scheduler
   scatter chunks. Last-nonzero-byte inference is insufficient because a
   valid linked checksum may end in zero bytes.
6. Treat `$1600-$1BA9` as boot-only. After service startup, managed application
   slot 2 may overwrite it; no resident descriptor or poll path may call the
   composer again.

## Consequences

- The initial extraction grows the free post-shadow tail from 1,835 bytes at
  `$C7D5-$CEFF` to 3,285 bytes at `$C22B-$CEFF`. The following boot-delivery
  extraction grows it again to 3,552 bytes at `$C120-$CEFF` without changing
  this ADR's console placement.
- No measured boot-only object remains resident. Total reclaim remains 4,576
  bytes, with 1,024 assigned to the installed scheduler page.
- Stage-1 COMMON now uses all 512 bytes. FINAL remains 214 bytes and the fixed
  scheduler copier remains 35 bytes at `$F7D8`.
- The later `SCHEDOVR` path retired production scheduler scatter delivery;
  the 574-byte/533-byte figures remain historical measurements of the earlier
  boot path.
- The direct development image carries the console composer at `$1600`, so it
  preserves the same runtime binding without executing the disk installer.

## Qualification

The following gates pass in VICE 3.10:

- D71 and D64 cold boots reach the root terminal;
- both retain an exact copy of the linked image at `$1600-$1BA9` after service
  startup;
- `xinit` followed by `xwave &` overwrites slot 2 and reaches the running state;
- capability relocation and its post-xclock re-entry gate remain valid;
- all 8,000 shadow bytes clear, the current 3,552-byte tail preimage survives, and the
  bank-0 shadow equals the bank-1 VIC bitmap after repaint.

`1986` cold boot plus slot-reuse qualification remains the acceptance gate.
Until that independent run is recorded, this ADR remains proposed.

## Alternatives considered

- **Keep the object resident.** Rejected: it spends 1,450 scarce bytes on a
  one-shot presentation operation.
- **Run from `$1200`.** Rejected: it collides with the scheduler page buffer.
- **Use the resident scheduler gather.** Rejected: a contiguous extraction
  source and a direct exact-length copier are simpler, and the scheduler
  manifest capacity was only 533 bytes after reservations; this remains a
  rejection rationale for the historical scatter path.
- **Infer free boot-sector bytes by scanning for nonzero data.** Rejected: it
  caused a real scheduler checksum failure when the linked installer ended in
  two zero bytes.
