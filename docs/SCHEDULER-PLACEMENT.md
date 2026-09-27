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

From `build/8502/udeks-8502.map` (2026-09-27, ABI 0.3 branch):

| Region | Address | Size | Notes |
|---|---:|---:|---|
| `BOOTPROBE` (`PROBECODE`) | `$0B00-$0BFF` | 256 | staged probe, executed from the dead boot-sector page |
| `BOOTCRT` (`STARTUP`) | `$1C00-$1CFF` | 256 | staged crt0, executed from the dead stage-1 page |
| `KERNELENTRY` vectors | `$2000-$2005` | 6 | fixed kernel-main and boot-delivery entries |
| resident `CODE`-`BSS` | `$2006-$A1DF` | 33,242 | code, rodata, data, and BSS |
| `VICSHADOW` | `$A1E0-$C11F` | 8,000 | bitmap shadow; its boot preimage begins with boot-only delivery images |
| free gap | `$C120-$CEFF` | 3,552 | between the shadow and `SYSCALLS` |
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

No measured boot-only object remains in the resident link:

| Object | Bytes | Role |
|---|---:|---|
| total | 0 | all one-shot objects are split boot images |

`crt0.o` and `probe.o` are no longer resident. `crt0` is linked into the
`$1C00-$1CFF` `BOOTCRT` page, staged at `$AE00-$AEFF`, and copied over the
dead stage-1 page by the `$F700` final installer. `probe.o` is linked into the
`$0B00-$0BFF` `BOOTPROBE` page, staged at `$AD00-$ADFF`, and copied over the
dead boot-sector page by the same installer. Their 207 and 209 bytes now show
up as free tail instead of boot-only resident code.

`hardware_capability.o` is now realized reclaim: its 967-byte image is linked
separately at `$0200`, staged at `$A2EB-$A6B1`, installed and checksummed by a
102-byte boot-only routine at `$A6B2-$A717`, then erased from the shadow by
crt0. Its stack-independent idempotence guard has a net 31-byte resident cost
and is included in the
map above.

`boot_console.o` is also realized reclaim: its exact 1,450-byte image is
linked separately at `$1600-$1BA9`, staged at `$A718-$ACC1`, and installed by
a 99-byte checksum gate at `$0B50-$0BB2`. The installer runs before the
scheduler gather and is then overwritten by the relocated probe. The
scheduler allocator reserves the installer's complete linked extent, including
zero-valued tail bytes. The console image is dead after service startup and
application slot 2 may be reused by `xwave`.

`boot_delivery.o` is the final realized reclaim: its exact 267-byte assembly
image is linked at `$A1E0-$A2EA`, staged at the bottom of the VIC shadow, and
executed in place through the frozen `$2003` entry. It has no BSS or cc65
state. After it gathers and validates the scheduler, crt0 clears it with the
rest of the shadow. Capability staging therefore still begins at `$A2EB`.

Structural slack:

| Item | Bytes | Condition |
|---|---|---|
| shadow tail gap `$C120-$CEFF` | 3,552 | post-bootstrap reclaim; during boot it still carries module, request, task-loader, and task-gate staging, so a scheduler segment placed here must be installed or overlaid after those payloads are relocated |
| `$1C00-$1FFF` bootstrap staging | 1,024 | **consumed by the scheduler delivery**: stage 1 gathers the linked scheduler image and the `$F7D8` copier installs it there after crt0 |

Total bank-0 reclaim: 3,552 + 1,024 = **4,576 bytes**. Of that, 1,024 is now
occupied by the scheduler segment itself, leaving the complete 3,552-byte
tail for scheduler policy, lifecycle state, and handlers.

The first lifecycle integration increment is a link-only overlay proof. The
607-byte `udeks_lifecycle_apply()` transition engine is assigned to the
`$1C00-$1FFF` scheduler page beside the delivery stub; the remainder of
`task_state.o`, all of `task_policy.o`, their constants, and their 71-byte BSS
are linked into `$C120-$CEFF`. A generated, zero-byte private bridge binds only
their external cc65 runtime imports and requires normal/panic map address and
type parity. The only helpers absent from the resident kernel, `shlax2` and
`tosanda0`, come from exactly two extracted `none.lib` modules inside the
overlay rather than growing the resident runtime. `make scheduler-overlay`
builds this proof without installing it,
so the qualified boot image continues to use the scheduler identity stub until
the tail delivery and request handlers are ready together.

The active link occupies 955 bytes at `$1C00-$1FBA` (zero-padded to a 1 KiB
delivery page) and 3,235 runtime bytes at `$C120-$CDC2` (3,164 emitted plus 71
BSS), leaving 69 bytes in the page and 317 bytes in the tail. The bridge
contract is 26 resident providers: 23
absolute and three zero-page symbols. Any provider-count, address-class,
normal/panic parity, or placement drift fails the build.

`SCHEDOVR` now packages the page and 3,164 emitted tail bytes in one versioned
PRG on side one of both D71 and D64 images. Stage 0 loads it into bank 1 and a
192-byte one-shot `$FF05-$FFC4` installer copies it only after conflicting boot
staging has moved. The scheduler entry restores the permanent task gate before
entering `$2000`; the IRQ trampoline beginning at `$FFC5` is never overwritten.
VICE qualifies exact installation and both disk formats; ADR 0012 still awaits
`1986` and physical-hardware acceptance.

The scheduler bootstrap gate at `$1C1E` now creates and dispatches persistent
`/bin/ush` as task 1 before entering the retained `$FF13` poll path. The live
probe verifies the exact post-bootstrap 71-byte BSS image: task 1 is running,
the other seven slots remain clear, and only the expected lifecycle counters
are set.

## Proposed bank-0 scheduler region

| Use | Budget |
|---|---:|
| lifecycle state (`task_state.c`) | 1,765 |
| request policy (`task_policy.c`) | 2,245 |
| handlers, run queue, task table | 1,200 |
| total | 5,210 |

The reclaim budget covers 4,576 bytes, of which the scheduler delivery now
occupies the `$1C00-$1FFF` reservation, leaving 3,552 bytes to be found either
by trimming the handler budget or by the later shell-extraction milestone. The
VIC shadow placement is settled, so the reclaimed KERNEL bytes form one
contiguous `$C120-$CEFF` window; the scheduler segment is installed in the
separate `$1C00-$1FFF` area. The tail is not ordinary free RAM at reset: boot
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
4. `docs/BOOT-STAGING-MAP.md` records the byte-accurate staging/lifetime map.
   Before capability extraction, the free payload holes totalled 805 bytes
   (largest 230), blocking both remaining boot-only objects.
5. Reserve `$1C00-$1FFF` and install a scheduler segment through stage 1;
   verify the D71 and D64 boot paths. The first increment is implemented with
   the initially resident `BOOTDELIVERY` gather (fixed `$2003` kernel entry
   vector, no BSS) and the 35-byte `$F7D8` copier in FINAL; both cold boots
   install a page byte-identical to the linked scheduler image
   (`bench/results/2026-09-26-scheduler-delivery`).
6. Link `hardware_capability.o` separately at `$0200`, stage its exact image
   plus one-shot installer in the lower VIC shadow, and protect application-slot reuse
   with an idempotent service-start guard. The D71 and D64 `HCAP` records,
   linked slot image, xclock overwrite, and inert re-entry call are covered by
   `make capability-probe`; VICE and `1986` qualification is preserved in
   `bench/results/2026-09-27-capability-relocation`. ADR 0009 is accepted.
7. Link `boot_console.o` separately at `$1600`, stage its exact image at
   `$A718-$ACC1`, install it through the one-shot `$0B50` checksum gate, and
   reserve the installer's full extent from scheduler scatter allocation.
   `make boot-console-probe` verifies exact D71/D64 slot images and safe xwave
   reuse; the independent `1986` pass remains before ADR 0010 acceptance.
8. Link `boot_delivery.o` separately at `$A1E0` and execute it in place from
   the lower VIC shadow through the unchanged `$2003` entry. This realizes the
   final 267-byte boot-only reclaim without a copier; VICE D71/D64, capability,
   slot-reuse, and shadow gates pass.
9. Replace the implementation behind the frozen `$FF10` reset, `$FF13` poll,
   and `$FF16` request trampolines, reuse the `$FF05-$FFC4` reservation for
   the switch tail, and retire the old special-case polling; verify task
   switching, the VDC console, VIC windows, pointer input, and the Z80 worker.

Compatibility paths stay in place until their replacement is covered by the
smoke sequence. No step is merged on the strength of a linker map alone.
