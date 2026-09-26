# Bank-0 boot staging and lifetime map

Reclaim step 4 requires a byte-accurate map before `hardware_capability.o`
(968 bytes) or `boot_console.o` (1,450 bytes) can be relocated. The map is
derived from `tools/boot_staging_map.py`, the linker map, the payload staging
constants in `tools/build_d71.py`, and the boot-sector image; the numbers are
locked by `tests/test_boot_staging_map.py` and `--check` fails when a staged
object would suddenly fit.

## Lifetime phases

| Phase | Meaning |
|---|---|
| `load` | after the KERNAL loads the boot sector and the 212-sector payload, before stage 1 |
| `stage1` | during stage-1 relocation |
| `crt0` | during the crt0 BSS and VIC shadow clear |
| `boot` | after crt0 until `xinit`/apps: capability probing and console composition |
| `runtime` | `xinit` and managed applications active |

## Staged payload regions (bank 0)

| Region | Range | Size | Live | Notes |
|---|---:|---:|---|---|
| probe staging | `$AD00-$ADFF` | 256 | `load..crt0` | copied to `$0B00` by the final installer |
| crt0 staging | `$AE00-$AEFF` | 256 | `load..crt0` | copied to `$1C00` by the final installer |
| bootfs tail staging | `$AF00-$BFBA` | 4,283 | `load..stage1` | moved to bank-1 `$BD00-$D0FF`; ends at the module boundary |
| module staging | `$BFBB-$C2FF` | 837 | `load..stage1` | installed at `$E300` |
| task request staging | `$C300-$C408` | 265 | `load..stage1` | installed at `$F800` |
| bootfs request staging | `$C4EF-$C7FF` | 785 | `load..stage1` | installed at `$F3EF` |
| task loader staging | `$C800-$CDEF` | 1,520 | `load..stage1` | installed at `$F910` |
| task gate staging | `$CE00-$CECA` | 203 | `load..stage1` | installed at `$FF05` |

The VIC shadow spans `$AB2D-$CA6C`; the tail runs to the fixed `SYSCALLS` page
at `$CF00`. The boot sector is `$0B00-$0BFF`, of which stage 0 occupies
`$0B00-$0B3D`.

## Free payload holes

| Hole | Range | Size | Free |
|---|---:|---:|---|
| shadow prefix | `$AB2D-$ACFF` | 467 | after crt0 |
| shadow mid | `$C409-$C4EE` | 230 | after crt0 |
| loader tail | `$CDF0-$CDFF` | 16 | after stage 1 |
| gate tail | `$CECB-$CEFF` | 53 | after stage 1 |
| boot-sector tail | `$0B3E-$0BFF` | 194 | after stage 0 |
| **total** | | **960** | largest contiguous **467** |

## Boot-only objects

| Object | CODE | RODATA | BSS | Total | Runs at | Profile |
|---|---:|---:|---:|---:|---|---|
| `hardware_capability.o` | 967 | 0 | 1 | 968 | `boot`, capability service start | bank 0, I/O visible |
| `boot_console.o` | 911 | 539 | 0 | 1,450 | `boot`, console start | bank 0, I/O visible |

Both call resident kernel functions, so they cannot run under the worker
profile.

## Collision analysis

Runtime homes that are free during `boot` and outside the step-4 exclusions
(`$1C00-$1FFF` scheduler reservation, `$E700-$EFF0` C stack, bootfs staging)
exist: application slot 1 `$0200-$0AFF` (2,304 bytes), application slot 2
`$1200-$1BFF` (2,560 bytes), and the reclaimed tail after stage 1. The blocker
is the **staged source image**:

- neither object fits a contiguous payload hole (largest 467 bytes);
- `hardware_capability.o` is 8 bytes larger than the entire free payload
  (960 bytes), so even a split-source staging cannot carry it;
- `boot_console.o` needs 1,450 bytes and additionally needs a contiguous
  runtime home, which only the application slots provide.

`tools/boot_staging_map.py --check` fails if the free payload grows enough for
either object to fit, forcing this map and the relocation plan to be updated
before the layout drifts.

## Prerequisite for relocating these objects

Relocation is blocked by staging capacity, not by runtime placement. The next
increment must first free a contiguous staging region. Candidate mechanisms:

1. **Bank-1 staging round trip.** Carry the object in unused bank-1 RAM
   (`$4200-$5BFF` is VIC-visible but otherwise unused during boot) and copy it
   into an application slot from a common-RAM bank copy at `boot`. Requires a
   small audited bank-copy primitive; it also gives the future scheduler a
   staging mechanism.
2. **Free a payload region.** Shrink the bootfs by one program or move the
   module staging so a contiguous hole of at least 968 bytes opens before the
   module. This is the smallest code change but couples the map to the bootfs
   content.
3. **Overlay at scheduler install time.** Keep the objects resident, then copy
   the scheduler over them once they have run, staging the scheduler in bank 1
   or an application slot.

Until one of these lands, `hardware_capability.o` and `boot_console.o` stay
resident and their bytes remain budgeted reclaim, not realized reclaim.
