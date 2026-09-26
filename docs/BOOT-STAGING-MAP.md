# Bank-0 boot staging and lifetime map

Reclaim step 4 requires a byte-accurate map before `hardware_capability.o`
(967 staged bytes, 968 runtime bytes) or `boot_console.o` (1,450 bytes) can be
relocated. The map is derived from `tools/boot_staging_map.py`, the linker
map, the emitted staging artifacts, the installer copy lengths, and the
payload staging containers in `tools/build_d71.py`; the numbers are locked by
`tests/test_boot_staging_map.py` and `--check` fails if a contiguous hole ever
becomes large enough for a staged object.

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
shadow spans `$AB2D-$CA6C`; the tail runs to the fixed `SYSCALLS` page at
`$CF00`. The boot sector is `$0B00-$0BFF`, of which stage 0 occupies
`$0B00-$0B3D`.

## Free payload holes

| Hole | Range | Size | Free |
|---|---:|---:|---|
| shadow prefix | `$AB2D-$ACFF` | 467 | after crt0 |
| shadow mid | `$C409-$C4EE` | 230 | after crt0 |
| bootfs-request container tail | `$C78A-$C7FF` | 118 | after stage 1 |
| loader tail | `$CDF0-$CDFF` | 16 | after stage 1 |
| gate tail | `$CECB-$CEFF` | 53 | after stage 1 |
| boot-sector tail | `$0B3E-$0BFF` | 194 | after stage 0 |
| **total** | | **1,078** | largest contiguous **467** |

## Boot-only objects

| Object | Staged | Runtime | Runs at | Profile |
|---|---:|---:|---|---|
| `hardware_capability.o` | 967 | 968 | `boot`, capability service start | bank 0, I/O visible |
| `boot_console.o` | 1,450 | 1,450 | `boot`, console start | bank 0, I/O visible |

Only initialized bytes need staging; the one-byte BSS of
`hardware_capability.o` is a runtime allocation. Both objects call resident
kernel functions, so they cannot run under the worker profile.

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

- `hardware_capability.o` fits the aggregate free payload (967 <= 1,078, 111
  bytes spare) but no single hole is large enough, so it needs a scatter copy
  across at least four chunks, for example 467 + 230 + 118 + 152 from the
  boot-sector hole.
- `boot_console.o` (1,450) exceeds the aggregate and remains blocked; it also
  needs a contiguous runtime home, which only the application slots provide.

## Options

1. **Scatter-copy `hardware_capability.o`.** Add a four-chunk staging splice
   and a matching stage-1 scatter copy into application slot 1. Realizes 967
   bytes of reclaim now, at the cost of a fragmented installer and a
   `build_d71.py` container split. Worth it only if the scheduler needs the
   bytes before the next reclaim step lands.
2. **Defer and reserve `$1C00-$1FFF` first (reclaim step 5).** Leave both
   objects resident, install the scheduler segment through stage 1, and
   revisit the boot-only objects once the scheduler's own staging and
   lifetime requirements are known.
3. **Do not use a scheduler-install overlay yet.** The two objects occupy
   separate CODE, RODATA, and BSS contributions, so there is no validated
   contiguous region for a scheduler to overlay, and no defined source from
   which that scheduler would be installed.

Until one of these lands, `hardware_capability.o` and `boot_console.o` stay
resident and their bytes remain budgeted reclaim, not realized reclaim.
