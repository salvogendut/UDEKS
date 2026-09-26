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
| `BOOTPROBE` (`PROBECODE`) | `$0B00-$0BFF` | 256 | staged probe, executed from the dead boot-sector page |
| `BOOTCRT` (`STARTUP`) | `$1C00-$1CFF` | 256 | staged crt0, executed from the dead stage-1 page |
| resident `CODE`-`BSS` | `$2000-$AB2C` | 35,629 | resident code, rodata, data, BSS |
| `VICSHADOW` | `$AB2D-$CA6C` | 8,000 | bitmap shadow, linked sequentially at its array size |
| free gap | `$CA6D-$CEFF` | 1,171 | between the shadow and `SYSCALLS` |
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
| total | 2,418 | |

`crt0.o` and `probe.o` are no longer resident. `crt0` is linked into the
`$1C00-$1CFF` `BOOTCRT` page, staged at `$AE00-$AEFF`, and copied over the
dead stage-1 page by the `$F700` final installer. `probe.o` is linked into the
`$0B00-$0BFF` `BOOTPROBE` page, staged at `$AD00-$ADFF`, and copied over the
dead boot-sector page by the same installer. Their 211 and 209 bytes now show
up as free tail instead of boot-only resident code.

Structural slack:

| Item | Bytes | Condition |
|---|---|---|
| shadow tail gap `$CA6D-$CEFF` | 1,171 | post-bootstrap reclaim; during boot it still carries task-loader staging (`$C800-$CDEF`) and task-gate staging (`$CE00-$CECA`), so a scheduler segment placed here must be installed or overlaid after those payloads are relocated |
| `$1C00-$1FFF` bootstrap staging | 1,024 | requires stage-1 to keep or install a scheduler segment there; `$1C00-$1CFF` currently holds the executed crt0 copy |

Total bank-0 reclaim: 2,418 + 1,171 + 1,024 = **4,613 bytes**.

## Proposed bank-0 scheduler region

| Use | Budget |
|---|---:|
| lifecycle state (`task_state.c`) | 1,765 |
| request policy (`task_policy.c`) | 2,245 |
| handlers, run queue, task table | 1,200 |
| total | 5,210 |

The reclaim budget covers 4,613 bytes, leaving at least 597 bytes to be found
either by trimming the handler budget or by the later shell-extraction
milestone. The VIC shadow placement is settled, so the reclaimed KERNEL bytes
form one contiguous `$CA6D-$CEFF` window; the separate `$1C00-$1FFF` segment
remains a second linker area. The tail is not ordinary free RAM at reset: boot
staging occupies it until stage 1 relocates the task loader and bank-1 task
gate, so the scheduler segment must be installed after those payloads move or
overlaid on the dead staging bytes.

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

1. Link `VICSHADOW` sequentially and at its 8,000-byte size; clear it from
   `crt0` through `__VICSHADOW_RUN__`/`__VICSHADOW_SIZE__`, remove the
   hardcoded stage-1 `$AF00` clear so the `$CA6D-$CEFF` tail survives, and
   verify boot, console, VIC graphics, and D71 staging. `make shadow-probe`
   boots the patched D71 and must show the full shadow zeroed with the tail
   preimage intact plus a drawn shadow identical to the bank-1 bitmap; the
   2026-09-26 evidence is preserved in
   `bench/results/2026-09-26-shadow-clear`.
2. Link `crt0.o` into the `$1C00-$1CFF` `BOOTCRT` page from the same linker
   invocation as the kernel, stage it at `$AE00-$AEFF`, and copy it over the
   dead stage-1 page from the `$F700` final installer before entering at
   `$1C00`; verify boot, BSS and shadow clear, the reclaimed tail, and the
   direct PRG boot.
3. Relocate `probe.o` into the `$0B00-$0BFF` `BOOTPROBE` page, staged at
   `$AD00-$ADFF` and copied over the dead boot-sector page by the final
   installer; verify boot and the capability record in VICE and `1986`
   (evidence: `bench/results/2026-09-26-shadow-clear`).
4. `docs/BOOT-STAGING-MAP.md` records the byte-accurate staging/lifetime map:
   the free payload holes total 960 bytes (largest 467), so neither
   `hardware_capability.o` (968) nor `boot_console.o` (1,450) can be staged
   today. Free a contiguous staging region (bank-1 round trip, a freed payload
   region, or a scheduler-install overlay) before relocating either; then
   verify the `HCAP` record and the boot console are byte-identical.
5. Reserve `$1C00-$1FFF` and install a scheduler segment through stage 1;
   verify the D71 and D64 boot paths.
6. Replace the implementation behind the frozen `$FF10` reset, `$FF13` poll,
   and `$FF16` request trampolines, reuse the `$FF05-$FFC4` reservation for
   the switch tail, and retire the old special-case polling; verify task
   switching, the VDC console, VIC windows, pointer input, and the Z80 worker.

Compatibility paths stay in place until their replacement is covered by the
smoke sequence. No step is merged on the strength of a linker map alone.
