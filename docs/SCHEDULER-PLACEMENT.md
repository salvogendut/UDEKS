# Scheduler placement spike

This is the Tasking 0.1 placement spike required before resident lifecycle
handlers are integrated. It measures the current resident map, identifies
boot-only and transitional material that can be reclaimed, and proposes the
regions for the bank-0 scheduler and the always-mapped switch tail. It is a
budget and reclaim order, not an accepted decision: each reclaim step lands
separately and must pass the emulator smoke gate below.

Run the audit against a built image:

```sh
make 8502
python3 tools/placement_audit.py            # human-readable budget
python3 tools/placement_audit.py --json     # machine-readable
```

## Current measurements

From `build/8502/udeks-8502.map` (2026-09-26, ABI 0.3 branch):

| Region | Address | Size | Notes |
|---|---:|---:|---|
| `STARTUP`-`BSS` | `$2000-$ACAB` | 35,500 | resident code, rodata, data, BSS |
| free gap | `$ACAB-$AEFF` | 597 | between BSS and the fixed VIC shadow |
| `VICSHADOW` | `$AF00-$CEFF` | 8,192 reserved | 8,000-byte bitmap plus 192 bytes padding |
| `SYSCALLS` | `$CF00-$CFF8` | 249 | fixed page |
| `HIGHBSS` | `$E1B8-$E2E1` | 298 | VIC tables, overflow canary |
| `MODULECODE`/`RODATA` | `$E300-$E643` | 836 | module-private code and data |
| module gap | `$E644-$E6FF` | 188 | before the C stack at `$E700` |
| `BOOTFSCODE` | `$F3EF-$F681` | 659 | bootfs request service |
| VIC gateways | `$F68A + up to 254` | 254 | largest copy ends at `$F788` |
| boot gateway | `$F700-$F7EF` | 240 | dead after stage 1 |
| `TASKREQUEST` | `$F800-$F905` | 262 | fixed request gateway |
| task loader | `$F910-$FEFF` | 1,520 | installed by stage 1, full |

Measured module sizes of the scheduler material already written:

| Module | Code + rodata | BSS |
|---|---:|---:|
| `task_policy.c` (cc65, compile-only) | 2,245 | 0 |
| `task_state.c` (cc65, compile-only) | 1,663 + 31 | 71 |
| total | 3,939 | 71 |

Future scheduler handlers, run queue, and task table are budgeted separately
below.

## Reclaim candidates

These objects run once during boot or discovery and are dead afterwards:

| Object | Bytes | Role |
|---|---:|---|
| `boot_console.o` | 1,450 | bordered boot-console composition |
| `hardware_capability.o` | 968 | discovery policy service |
| `probe.o` | 209 | VIC/VDC/REU/GeoRAM probes |
| `crt0.o` | 176 | startup and BSS clear |
| total | 2,803 | |

Structural slack:

| Item | Bytes | Condition |
|---|---:|---|
| BSS-to-shadow gap | 597 | already free |
| VIC shadow padding | 192 | requires shrinking/linking the shadow to its 8,000-byte array |
| `$1C00-$1FFF` bootstrap staging | 1,024 | requires stage-1 to keep or install a scheduler segment there |

Total bank-0 reclaim: 2,803 + 597 + 192 + 1,024 = **4,616 bytes**.

## Proposed bank-0 scheduler region

| Use | Budget |
|---|---:|
| lifecycle state (`task_state.c`) | 1,765 |
| request policy (`task_policy.c`) | 2,245 |
| handlers, run queue, task table | 1,200 |
| total | 5,210 |

The reclaim budget covers 4,616 bytes, leaving about 594 bytes to be found
either by trimming the handler budget or by the later shell-extraction
milestone. The region is deliberately not contiguous yet: the reclaimed
KERNEL bytes below the VIC shadow and the separate `$1C00-$1FFF` segment are
two linker areas until the VIC shadow placement is settled.

## Always-mapped switch tail

The boot-gateway page `$F700-$F7EF` is 240 bytes and is dead after stage 1,
but the largest VIC common-gateway copy (254 bytes at `$F68A`) reaches
`$F788`. The uncontested remainder is therefore only **104 bytes**
(`$F788-$F7EF`).

A minimal tail fits that window if it is split into two small entries and the
scheduling policy stays in bank 0:

- **switch-out entry**: save A/X/Y/P/SP into the current task context, select
  the kernel-visible profile, return to the bank-0 scheduler;
- **switch-in entry**: restore A/X/Y/P/SP from the selected context and return
  to the task after the bank-0 scheduler has written the page registers and
  profile.

Anything larger requires shortening the VIC gateway or moving its copy target,
which needs its own smoke-tested change. Placing the policy wholesale in
common RAM is not viable.

## Reclaim order and validation

Each step is a separate change with a `1986` and VICE smoke pass:

1. Link `VICSHADOW` sequentially and at its 8,000-byte size; verify boot,
   console, VIC graphics, and d71 staging.
2. Overlay or relocate `crt0.o`; verify boot and BSS clear.
3. Relocate `boot_console.o`; verify the boot console is pixel-identical.
4. Relocate `probe.o` and `hardware_capability.o`; verify the `HCAP` record is
   byte-identical.
5. Reserve `$1C00-$1FFF` and install a scheduler segment through stage 1;
   verify the D71 and D64 boot paths.
6. Place the switch tail in `$F788-$F7EF`; verify task switching, the VDC
   console, VIC windows, pointer input, and the Z80 worker.

Compatibility paths stay in place until their replacement is covered by the
smoke sequence. No step is merged on the strength of a linker map alone.
