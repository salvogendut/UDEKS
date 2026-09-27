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
| boot-console installer | `$0B40` | 99 | 99 | 99 | `load..probe-copy` |
| probe staging | `$AD00` | 209 | 256 | 256 | `load..crt0` |
| crt0 staging | `$AE00` | 207 | 256 | 256 | `load..crt0` |
| bootfs tail staging | `$AF00` | 4,283 | 5,120 | 5,120 | `load..stage1` |
| module staging | `$BFBB` | 836 | 837 | 837 | `load..stage1` |
| task request staging | `$C300` | 265 | 265 | 265 | `load..stage1` |
| bootfs request staging | `$C4EF` | 667 | 667 | 785 | `load..stage1` |
| task loader staging | `$C800` | 1,507 | 1,520 | 1,520 | `load..stage1` |
| task gate staging | `$CE00` | 203 | 203 | 203 | `load..stage1` |

The bootfs request container is `$0311` bytes, but the final installer copies
two pages plus `$9B` bytes (`$029B`, the linked reservation), so
`$C78A-$C7FF` is free. The bootfs tail copy covers its full container,
including the module staging bytes, so that overlap yields no hole. The VIC
shadow spans `$A1E0-$C11F`; the tail runs to the fixed `SYSCALLS` page at
`$CF00`. The boot sector is `$0B00-$0BFF`, of which stage 0 occupies
`$0B00-$0B3D`; the boot-console installer reserves `$0B40-$0BA2` even when
its linked tail bytes are zero.

## Free payload holes

| Hole | Range | Size | Free |
|---|---:|---:|---|
| shadow prefix remainder | `$ACC2-$ACFF` | 62 | after crt0 |
| shadow mid | `$C409-$C4EE` | 230 | after crt0 |
| bootfs-request container tail | `$C78A-$C7FF` | 118 | after stage 1 |
| loader tail | `$CDF0-$CDFF` | 16 | after stage 1 |
| gate tail | `$CECB-$CEFF` | 53 | after stage 1 |
| boot-sector gap | `$0B3E-$0B3F` | 2 | after stage 0 |
| boot-sector tail | `$0BA3-$0BFF` | 93 | after the console installer |
| **total** | | **574** | largest contiguous **230** |

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
| module staging | `$C2FF` | 1 | copied to `$E300`, dead |
| task loader staging | `$CDE3-$CDEF` | 13 | copied to `$F910`, dead |
| stage-1 code | `$1FAB-$1FBF` | 21 | dead stage-1 page padding |
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
  `$A718-$ACC1` source; its 99-byte installer runs from `$0B40-$0BA2`, and the
  composer runs once from the upper part of application slot 2.
- `boot_delivery.o` is realized reclaim. It executes in place from
  `$A1E0-$A2EA` through the fixed `$2003` vector, gathers the scheduler, and is
  then erased by crt0. It needs neither a runtime copy nor resident storage.

The boot-console relocation deliberately does not consume the scheduler's
`$1200-$15FF` gather buffer. Stage 1 installs the composer first, gathers the
scheduler second, then overwrites the console installer with `probe.o`.

## Scheduler delivery (implemented 2026-09-26)

The step-5 handoff delivers the scheduler segment at `$1C00-$1FFF`:

1. link the scheduler image (`cfg/8502-scheduler.cfg`);
2. splice it into the free payload holes with a `USCT` scatter manifest at
   `$ACD9` (`tools/build_d71.py --scheduler --map`);
3. gather it into the temporary application slot `$1200-$15FF` before crt0
   through the fixed `$2003` kernel entry vector; the boot-only `BOOTDELIVERY`
   routine (267 staged bytes at `$A1E0`, no BSS or cc65 state) validates the
   manifest magic and the 16-bit image checksum and
   records failures in the boot-chain record;
4. crt0 clears BSS and the VIC shadow and returns to the fixed `$F7D8` copier;
5. the 35-byte copier in FINAL copies the gathered page into `$1C00-$1FFF`
   and enters the scheduler, whose entry continues through the fixed `$2000`
   kernel-main vector into `_kernel_main`.

`bench/artifacts/2026-09-26-scheduler-delivery` preserves the sizing
measurement that motivated the resident gather: the self-contained gather plus
install measured 132 bytes against 50 free bytes in FINAL, an 82-byte
shortfall. Moving the gather into the resident image leaves only the 35-byte
copier in FINAL, with 15 bytes of headroom. The hardened gather bounds the
entry count, source ranges, and destination, so a malformed manifest cannot
write past `$15FF`.

The measured scatter ceiling was **766 bytes** before capability relocation.
Registering `$A2EB-$ACC1` and the complete `$0B40-$0BA2` installer extent as
occupied reduces the current ceiling to **533 bytes**. The two-byte
`$0B3E-$0B3F` gap is below the later installer and is intentionally not used
by the monotonic scatter allocator. A larger scheduler image is rejected by
`tools/build_d71.py` until more staging is freed. The 297-byte linked scheduler
spans three chunks and both cold boots install it byte-exactly.

`bench/results/2026-09-26-scheduler-delivery` preserves the D71 and D64 cold
boot captures; both equal the linked scheduler image zero-filled to the
1,024-byte reservation.
