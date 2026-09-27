# Bank-0 boot staging and lifetime map

This byte-accurate map records the realized `hardware_capability.o` and
`boot_console.o` relocations.
The map is derived from `tools/boot_staging_map.py`, the linker
map, the emitted staging artifacts, the installer copy lengths, and the
payload staging containers in `tools/build_d71.py`; the numbers are locked by
`tests/test_boot_staging_map.py`.

The audit distinguishes three sizes per staged region:

- **emitted**: the live artifact bytes,
- **copied**: the range the installer actually transfers (a container page or
  the emitted length, whichever the installer uses),
- **container**: the padded `build_d71.py` reservation, which may extend past
  the copied range and leave a free hole.

## Lifetime phases

| Phase | Meaning |
|---|---|
| `load` | after the KERNAL loads the boot sector and the 212-sector payload, before stage 1 |
| `stage1` | during stage-1 relocation |
| `crt0` | during the crt0 BSS and VIC shadow clear |
| `boot` | after crt0 until `xinit`/apps: capability probing and console composition |
| `runtime` | `xinit` and managed applications active |

## Staged payload regions (bank 0)

| Region | Start | Emitted | Copied | Container | Live |
|---|---:|---:|---:|---:|---|
| boot-delivery gather | `$A1E0` | 267 | 267 | 267 | `load..crt0` |
| capability staging | `$A2EB` | 967 | 967 | 967 | `load..crt0` |
| capability installer staging | `$A6B2` | 102 | 102 | 102 | `load..crt0` |
| boot-console staging | `$A718` | 1,450 | 1,450 | 1,450 | `load..crt0` |
| task-switch activator | `$ACC2` | 42 | 42 | 42 | `load..crt0` |
| boot-console installer | `$0B50` | 99 | 99 | 99 | `load..probe-copy` |
| busy sprite | `$0BC0` | 63 | 63 | 63 | `load..stage1` |
| probe staging | `$AD00` | 209 | 256 | 256 | `load..crt0` |
| crt0 staging | `$AE00` | 207 | 256 | 256 | `load..crt0` |
| bootfs tail staging | `$AF00` | 4,283 | 5,120 | 5,120 | `load..stage1` |
| module staging | `$BFBB` | 836 | 836 | 836 | `load..stage1` |
| task request staging | `$C300` | 265 | 265 | 265 | `load..stage1` |
| scheduler-tail installer | `$C409` | 192 | 192 | 192 | `load..scheduler-entry` |
| bootfs request staging | `$C4EF` | 667 | 667 | 785 | `load..stage1` |
| task loader staging | `$C800` | 1,507 | 1,520 | 1,520 | `load..stage1` |
| task gate staging | `$CE00` | 192 | 192 | 192 | `load..scheduler-entry` |

The bootfs request container is `$0311` bytes, but the final installer copies
two pages plus `$9B` bytes (`$029B`, the linked reservation), so
`$C78A-$C7FF` is free. The bootfs tail copy covers its full container,
including the module staging bytes, so that overlap yields no hole. The VIC
shadow spans `$A1E0-$C11F`; the tail runs to the fixed `SYSCALLS` page at
`$CF00`. The boot sector is `$0B00-$0BFF`, of which stage 0 occupies
`$0B00-$0B4D`; the boot-console installer reserves `$0B50-$0BB2`, and the
busy sprite occupies `$0BC0-$0BFE` until stage 1 copies it to bank 1.

## Free payload holes

| Hole | Range | Size | Free |
|---|---:|---:|---|
| shadow prefix remainder | `$ACEC-$ACFF` | 20 | after crt0 |
| shadow mid | `$C4C9-$C4EE` | 38 | after crt0 |
| bootfs-request container tail | `$C78A-$C7FF` | 118 | after stage 1 |
| loader tail | `$CDF0-$CDFF` | 16 | after stage 1 |
| gate tail | `$CEC0-$CEFF` | 64 | after stage 1 |
| boot-sector gap | `$0B4E-$0B4F` | 2 | after stage 0 |
| installer/sprite gap | `$0BBE-$0BBF` | 2 | after stage 1 |
| boot-sector tail | `$0BFF` | 1 | after stage 1 |
| **total** | | **261** | largest contiguous **118** |

The boot-console checksum/copy covers one contiguous 1,492-byte delivery:
the 1,450-byte composer followed by the 42-byte task-switch activator.
The latter lands at `$1BAA-$1BD3`, after the composer, and the installer also
copies it to its `$F68A-$F6B3` common-RAM run address. The scheduler bootstrap
calls it after service startup to install the ABI 0.3 context-switch path.
The former `$ACD9` scatter-manifest reservation belongs to the superseded
inline scheduler-delivery path; a build that requests that compatibility path
must reject this overlapping placement rather than silently combining them.

## Boot-only objects

| Object | Staged | Runtime | Runs at | Profile |
|---|---:|---:|---|---|
| `hardware_capability.o` | 967 | 968 | `boot`, relocated to `$0200-$05C7` | bank 0, I/O visible |
| `boot_console.o` | 1,450 | 1,450 | `boot`, console start | bank 0, I/O visible |

Only initialized bytes need staging; the capability installer's exact copy
clears the service's one-byte BSS at `$05C7`. Both objects call resident kernel
functions, so they cannot run under the worker profile. The console has no
BSS and occupies `$1600-$1BA9`, above the scheduler gather at `$1200-$15FF`.

## Copied but dead padding (not available)

| Padding | Range | Size | Note |
|---|---:|---:|---|
| probe staging | `$ADD1-$ADFF` | 47 | copied to `$0B00`, dead |
| crt0 staging | `$AECF-$AEFF` | 49 | copied to `$1C00`, dead |
| task loader staging | `$CDE3-$CDEF` | 13 | copied to `$F910`, dead |
| stage-1 code | `$1FB6-$1FBA` | 5 | dead stage-1 page padding |
| Z80 tail | `$D297-$D2FF` | 105 | copied into bank 1 |

These bytes are copied but not live. They are reported for completeness and
are **not** counted as staging capacity until their ownership is explicitly
frozen.

## Collision analysis

Runtime homes free during `boot` and outside the step-4 exclusions
(`$1C00-$1FFF` scheduler reservation, `$E700-$EFF0` C stack, bootfs staging)
exist: application slot 1 `$0200-$0AFF` (2,304 bytes) and application slot 2
`$1200-$1BFF` (2,560 bytes).

- `hardware_capability.o` is realized reclaim. Its image and 102-byte
  installer occupy `$A2EB-$A717`, and the service runs once from application
  slot 1.
- `boot_console.o` is realized reclaim. Extraction supplies the contiguous
  `$A718-$ACC1` source; its 99-byte installer runs from `$0B50-$0BB2`, and the
  composer runs once from the upper part of application slot 2.
- `boot_delivery.o` is realized reclaim. It executes in place from
  `$A1E0-$A2EA` through the fixed `$2003` vector, gathers the scheduler, and is
  then erased by crt0. It needs neither a runtime copy nor resident storage.

The boot-console relocation deliberately does not consume the scheduler's
`$1200-$15FF` page buffer. Stage 1 installs the composer first, installs the
secondary scheduler payload second, then overwrites the console installer and
sprite with `probe.o`.

## Scheduler delivery (activated 2026-09-27)

The original step-5 scatter handoff remains preserved as historical evidence.
The production path now delivers the scheduler at `$1C00-$1FFF` and its
installed tail at `$C120-$CDBC`:

1. link the zero-padded scheduler page and lifecycle core tail; the pure
   request-policy C module remains host-tested and compile-qualified rather
   than occupying production RAM;
2. package both in the versioned `SCHEDOVR` side-one PRG;
3. load it at `$5000` in bank 1 through stage-0 KERNAL `SETBNK`/`LOAD`;
4. copy it through the exact 192-byte temporary task-gate installer into
   `$1200-$15FF` and `$C120-$CDBC`, validating its magic/checksum and clearing
   the 154-byte BSS;
5. crt0 clears BSS and the VIC shadow and returns to the fixed `$F7D8` copier;
6. the 35-byte copier in FINAL copies the page into `$1C00-$1FFF`; the
   scheduler entry restores the permanent `$FF05-$FFC4` task gate and
   continues through the fixed `$2000` kernel-main vector.

`bench/artifacts/2026-09-26-scheduler-delivery` preserves the sizing
measurement that motivated the resident gather: the self-contained gather plus
install measured 132 bytes against 50 free bytes in FINAL, an 82-byte
shortfall. Moving the gather into the resident image leaves only the 35-byte
copier in FINAL, with 15 bytes of headroom. The hardened gather bounds the
entry count, source ranges, and destination, so a malformed manifest cannot
write past `$15FF`.

The linked core occupies `$C120-$C70A` including BSS. The packaged tail pads
to the permanent 1,213-byte lifecycle handler at `$C900-$CDBC`; the context
binding follows immediately at `$CDBD-$CEFF`. The old `USCT` scatter builder and frozen
`$2003` entry remain available for compatibility and historical tests, but
production boot no longer consumes the fragmented holes. The active page is
1,018 bytes padded to 1 KiB, and the copied tail is 3,229 bytes including the
zero gap and handler; its 154-byte core BSS is cleared in place. D71/D64 cold boots install
both byte-exactly without touching the `$FFC5` IRQ trampoline. After the
installer clears BSS, the lifecycle bootstrap leaves the exact expected task-1
state while all unused task slots remain zero.

`bench/results/2026-09-26-scheduler-delivery` preserves the D71 and D64 cold
boot captures; both equal the linked scheduler image zero-filled to the
1,024-byte reservation.
