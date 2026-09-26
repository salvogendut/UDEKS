# Scheduler placement spike

This is the Tasking 0.1 placement spike required before resident lifecycle
handlers are integrated. It measures the current resident map, identifies
boot-only and transitional material that can be reclaimed, and proposes the
regions for the bank-0 scheduler and the always-mapped switch tail. It is a
budget and reclaim order, not an accepted decision: each reclaim step lands
separately and must pass the emulator smoke gate below.

Run the audit against a built image in the reference container:

```sh
make 8502
make placement-check                        # fail-fast qualification
python3 tools/placement_audit.py            # human-readable budget
python3 tools/placement_audit.py --json     # machine-readable
```

`make placement-check` requires `cc65`/`od65` and refuses to run from the host
with the exact container command. It compares the measured gateway sizes
against the qualified `[254, 46, 68, 358]` baseline, rejects copies beyond
`$F7EF` or into `$F800` and later, and requires the `TASKGATE` segment to be
exactly `$FF05-$FFC4` in the map.

All linked-segment ends are inclusive. Gateway sizes are read from the
absolute `_udeks_vic_gateway_size_*` exports in the assembled
`vic_graphics_transport.o` through `od65`; they are not hardcoded, and the
audit reports them as unavailable if the object or `od65` is missing.

## Current measurements

From `build/8502/udeks-8502.map` (2026-09-26, ABI 0.3 branch):

| Region | Address | Size | Notes |
|---|---:|---:|---|
| `STARTUP`-`BSS` | `$2000-$ACAB` | 36,012 | resident code, rodata, data, BSS |
| free gap | `$ACAC-$AEFF` | 596 | between BSS end and the fixed VIC shadow |
| `VICSHADOW` | `$AF00-$CEFF` | 8,192 reserved | 8,000-byte bitmap plus 192 bytes padding |
| `SYSCALLS` | `$CF00-$CFF8` | 249 | fixed page |
| `HIGHBSS` | `$E1B8-$E2E1` | 298 | VIC tables, overflow canary |
| `MODULECODE`/`RODATA` | `$E300-$E643` | 836 | module-private code and data |
| module gap | `$E644-$E6FF` | 188 | before the C stack at `$E700` |
| `BOOTFSCODE` | `$F3EF-$F681` | 659 | bootfs request service |
| VIC gateway copies | `$F68A-$F7EF` | 358 | largest copy is the outline gateway (`$166`) |
| transient task stack | `$F700-$F7EF` | 240 | cc65 software stack, top `$F7F0` |
| `TASKREQUEST` | `$F800-$F905` | 262 | fixed request gateway |
| task loader | `$F910-$FEFF` | 1,520 | installed by stage 1, full |
| `TASKGATE` | `$FF05-$FFC4` | 192 | legacy bank-1 cooperative gate |

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
| `crt0.o` | 174 | startup and BSS clear, excluding two zero-page bytes |
| total | 2,801 | |

Structural slack:

| Item | Bytes | Condition |
|---|---:|---|
| BSS-to-shadow gap | 596 | already free |
| VIC shadow padding | 192 | requires shrinking/linking the shadow to its 8,000-byte array |
| `$1C00-$1FFF` bootstrap staging | 1,024 | requires stage-1 to keep or install a scheduler segment there |

Total bank-0 reclaim: 2,801 + 596 + 192 + 1,024 = **4,613 bytes**.

## Proposed bank-0 scheduler region

| Use | Budget |
|---|---:|
| lifecycle state (`task_state.c`) | 1,765 |
| request policy (`task_policy.c`) | 2,245 |
| handlers, run queue, task table | 1,200 |
| total | 5,210 |

The reclaim budget covers 4,613 bytes, leaving at least 597 bytes to be found
either by trimming the handler budget or by the later shell-extraction
milestone. The region is deliberately not contiguous yet: the reclaimed
KERNEL bytes below the VIC shadow and the separate `$1C00-$1FFF` segment are
two linker areas until the VIC shadow placement is settled.

## Always-mapped switch tail

There is no uncontested window in the upper common RAM. The outline gateway
copy alone is 358 bytes, so the gateway copies occupy `$F68A-$F7EF`, and
`$F700-$F7EF` is simultaneously the transient UDEX program's live cc65
software stack with its top and guard at `$F7F0-$F7FF` (ADR 0003). A
persistent switch routine placed there would be corrupted by either the
outline blitter or a transient program's stack. The audit reports zero
uncontested bytes and names both overlaps.

The promising replacement is the legacy bank-1 cooperative gate reservation,
`$FF05-$FFC4` (192 bytes). The task-bank ABI freezes `$FF10` (context reset),
`$FF13` (cooperative poll), and `$FF16` (request/resume entry) as its public
entry addresses, so the scheduler replaces the implementation *behind* those
trampolines and keeps the trampolines at their published addresses; it does
not retire the addresses themselves. A switch tail placed in the same
reservation must preserve `$FF10`, `$FF13`, and `$FF16` and stay within the
192 reserved bytes. Until then, a tail there would collide with the active
task-bank gateway.

Order of preference:

1. replace the bodies behind the frozen `$FF10`, `$FF13`, and `$FF16` entry
   trampolines as part of the scheduler migration and reuse the `$FF05-$FFC4`
   reservation for the switch tail without moving those entries;
2. otherwise relocate the outline gateway and the transient task stack first,
   then reuse the freed upper windows.

A minimal tail also fits a small budget if the policy stays in bank 0: a
switch-out entry that saves A/X/Y/P/SP, selects the kernel-visible profile,
and returns to the bank-0 scheduler, plus a switch-in entry that restores the
selected context after the scheduler writes the page registers and profile.

## Reclaim order and validation

Each step is a separate change with a `1986` and VICE smoke pass:

1. Link `VICSHADOW` sequentially and at its 8,000-byte size; verify boot,
   console, VIC graphics, and D71 staging.
2. Overlay or relocate `crt0.o`; verify boot and BSS clear.
3. Relocate `boot_console.o`; verify the boot console is pixel-identical.
4. Relocate `probe.o` and `hardware_capability.o`; verify the `HCAP` record is
   byte-identical.
5. Reserve `$1C00-$1FFF` and install a scheduler segment through stage 1;
   verify the D71 and D64 boot paths.
6. Replace the implementation behind the frozen `$FF10` reset, `$FF13` poll,
   and `$FF16` request trampolines, reuse the `$FF05-$FFC4` reservation for
   the switch tail, and retire the old special-case polling; verify task
   switching, the VDC console, VIC windows, pointer input, and the Z80 worker.

Compatibility paths stay in place until their replacement is covered by the
smoke sequence. No step is merged on the strength of a linker map alone.
