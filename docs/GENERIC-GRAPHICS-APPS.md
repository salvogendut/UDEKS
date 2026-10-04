# Generic disk-loaded graphical applications

Status: relocation and generic foreground/background launch implemented, 2026-10-04.
[Issue #35](https://github.com/salvogendut/UDEKS/issues/35).
Branch: `graphics-generic-apps`, based on merged
PR #31 (`9af159b`). This is the next feature priority, before service extraction.
It replaces application-specific slot wiring, not the four-window capacity limit.

## User-visible target

Build a new C graphical application using a documented SDK, copy its executable
to the system disk as `NAME.BIN`, then run `name &` from ush. UDEKS selects a free
compatible allocation, tracks the instance, and retires its window/input/task
resources on close or exit. Adding a program must not require editing or
rebuilding the kernel, shell, running-app panel or a resident name table.

The same executable must work in different suitable slots; users and app authors
must not select a slot or link separately for a task number. A free slot smaller
than an application's image/BSS/stack requirements is not a usable allocation.
Full, malformed or incompatible loads must give a useful error without changing
live peers. This remains a trusted cooperative system, not hardware protection
against arbitrary machine code.

## Original coupling (being removed)

- `user/bin/ush.c` recognizes app names and translates them to numeric control
  IDs in `include/udeks/service_control.h`.
- The banked graphics service previously selected only `xcalc`/`xdraw` and
  the running panel had fixed labels. Those paths now use generic admission
  and per-instance names; the legacy named CONTROL adapters remain.
- `src/services/shell/shell.c` still has compatibility job bits and foreground
  controls. Unknown `name &` requests now take the automatic native loader.
- Calculator and drawing link at bank-1 `$2300` and `$3500`, respectively.
  Absolute code/data references cannot simply be copied to a different base.
- Clock and wave use legacy bank-0 callback modules, not the native task model.
  Four window descriptors therefore do not yet mean four interchangeable app slots.

The existing owner-checked UTRQ graphics interface, retained commands and private
task contexts are reusable. Allocation policy, loading, instance tracking and
presentation belong to service/user code; do not move app policy into the kernel.

## Relocation checkpoint (committed as `fbdc72d`)

UDEX 0.2 carries a bounded page-relocation table generated from real ld65 o65
records. The same compiled C file runs at bank-1 `$2300` and `$3500`, with
private state, initialized pointers, BSS and recursive software-stack frames
surviving yield/sleep. Both D64/1541 and D71/1571 VICE runs pass rejection,
concurrent execution, exit, reap and reload. Flat-link oracles independently
match both relocated images byte-for-byte. See the
[format and build instructions](../abi/executable.md#page-relocatable-native-images-02-development).

The proof image is 963 image + 7 BSS bytes; its file is 1,175 bytes including
header and 97 high-byte patches. The current loader must stage the whole file
inside the allocation, so relocation overhead also counts against capacity.
This is not yet a graphical SDK example or a generic shell command.

No resident-core or public syscall change was needed. Loader delivery uses
measured slack in two bank-1 service reservations:

| Region | Linked bytes | Reservation |
|---|---:|---|
| Existing loader | 1,787 | `$D900-$DFFF` (1,792) |
| Relocation validator/patcher | 366 | `$1880-$19FF` (384) |
| Extracted access helpers | 106 | `$1F00-$1FFF` (256) |

Storage is now bounded below `$1880` (1,650 bytes, 14 spare); lookup below
`$1F00` (1,169 bytes, 111 spare). Link/build and actual-map gates enforce these
bounds. CPU zero pages/stacks at `$D100-$D8FF`, common gates, both app
allocations and the Z80 remain untouched. The four existing apps pass the
VICE D64 and native keyboard/mouse 1986 regression (existing fixed-address
apps, not a second emulator's relocation proof). An isolated parallel build reproduces both normal disks,
the new executable and all changed service outputs byte-for-byte.

Exact images, captures and reproduction notes:
`bench/{artifacts,results}/2026-10-04-relocatable-apps`. Existing historical
evidence and published `build/udeks.*` snapshots are unchanged.

## Current checkpoint: ordinary unknown-name background launch

`name &` now resolves the disk executable, chooses a FREE fitting task 3/4
allocation, activates it and publishes a service-owned instance name. The
panel reads those names (nine display characters); close/EXIT frees the owner
and another executable can reuse it. No new kernel, shell or panel app ID is
needed. Duplicate instances are allowed; window/task identity controls events
and retirement. Old `xcalc -q`/`xdraw -q` requests reject unrelated occupants.

The independent 597-byte `HELLO.BIN` sample is installed as both HELLO and
SECOND without rebuilding the OS. [Build/install/test guide](GRAPHICAL-APPS-SDK.md).
Both VICE disk formats pass normal shell launch, independent state/clicks,
drag/close/reuse, malformed and oversized image rejection, unchanged live
peers, console use and desktop shutdown. The existing four-app VICE D64 and
unmodified 1986 native-input regressions also pass; the latter is not a second
emulator qualification of the new example. Exact candidate/evidence:
`bench/{artifacts,results}/2026-10-04-generic-launch`.

Current measured bytes: loader 1,791/1,792; access 236/256; relocation 366/384;
graphics module 1,525/1,536; helper 216/224; high module three spare bytes;
resident BSS ends `$9AFE` (one spare byte). No runtime stack, guard, CPU page
or app allocation moved. Serialized root-service scratch is static to avoid
extra persistent cc65 frames. The new metadata belongs to the graphics service.

At that checkpoint foreground remained pending. The follow-up below implements
bare generic launch/Ctrl+C. **Next:** instance/name-based control and native-client
migration, then explicit clock/wave compatibility. Generic `-q`, native arguments
and all-four-slot interchangeability remain incomplete. Plan the next service
placement before adding resident code.

## Implementation sequence

1. **Prove slot-independent execution.** Define a bounded versioned executable
   and SDK contract with a measured placement plan. Evaluate relocation or
   equivalent address-independent loading using real cc65 C code, not only an
   assembly stub. Relocate code, initialized pointers, entry and BSS references;
   leave hardware/common-ABI addresses untouched. Reject malformed metadata and
   overflow before publishing ownership. Keep existing UDEX compatibility
   explicit; do not silently reinterpret its fixed load address.
2. **Generic launch and instance lifecycle.** Resolve the executable from `/bin`,
   select a fitting FREE allocation from runtime descriptors, then validate,
   load, initialize and publish the task/window owner. Keep per-instance name,
   task and foreground/background state. Replace native app-name switches and
   fixed panel labels with those descriptors. Preserve console commands, `&`,
   close, targeted Ctrl+C, graceful exit, cleanup and slot reuse. Decide whether
   any temporary launcher command is needed without mistaking it for the final
   ordinary `name &` interface.
3. **SDK, migration and end-to-end acceptance.** Supply an independently built
   sample app unknown to the OS and migrate calculator/drawing to the generic
   path. Define and carry out the clock/wave compatibility or migration needed
   for all four advertised slots; two generic slots plus two named legacy apps
   is an intermediate milestone, not completion. Keep xwave algorithm/performance
   work separate. Update packaging to accept extra `.BIN` files without adding
   per-app kernel or disk-builder branches.

Each increment should deliver a meaningful runnable capability, with a map gate
before placement changes. The merged baseline has only 45 bytes of resident
headroom, 16 bytes in the high module, 53 in the shell, and no space in the
`$D900-$DFFF` loader. Remeasure before implementation. Replacing old dispatch
may recover space; silent growth into adjacent ownership is not an option.
Do not promise relocation is a trivial name-table change or compensate for
placement pressure with more hardcoded applications.

## Acceptance

- An app absent from the OS source/catalog can be built separately, copied to
  the disk and launched without rebuilding the system.
- The same binary runs correctly in at least two different compatible slots,
  including C globals, pointer-bearing data, BSS, calls, software stack and
  yield/sleep across context switches. Suitable free slots are selected
  automatically, independent of filename and launch order.
- Multiple different generic apps keep independent data, windows, titles and
  input through drag/focus/close/restart. Duplicate-instance policy is explicit;
  ownership is task/instance based, never inferred solely from a name.
- Invalid images/relocations, unsupported versions, missing files, no fitting
  slot and an over-capacity launch leave every live peer and retained image
  unchanged. Every rejection cleans up partial loader resources.
- The running panel reflects actual instances; console I/O, foreground Ctrl+C,
  background launch and desktop shutdown remain usable.
- Existing apps continue to work during migration. Completion includes a clear
  four-slot compatibility model, not a claim that a large binary fits every slot.
- Host tests, actual-link memory checks, VICE D64/D71, native 1986 input, then a
  concrete physical-C128 test candidate. Preserve exact artifacts and evidence.

## Related work and boundaries

The follow-up to `1699e82` adds bare foreground native launch with cooperative
Ctrl+C, deferred desktop initialization on CREATE, and a standalone console
SDK/proof (arguments, streams, return status, BSS reset with four windows).
All three VICE formats now qualify those paths; D81 adds real 1581 geometry,
not an extension rename. Console commands use the existing synchronous UDEX
0.1 loader, not native task slots; native arguments/background console I/O are
not complete. Instance/name-based stop and migration of the named apps remain
the next #35 increments. See [the SDK](GRAPHICAL-APPS-SDK.md).

- PR #31 / issue #30 provides the merged four-app baseline; its historical
  qualification records remain immutable.
- Issue #32 (`additional-apps`) exposed this limitation. Its `.CBM` container
  and PNG/JPEG converter commit `6b61f5c` remain on their own branch/worktree;
  do not discard, merge or modify that exploration as an incidental step.
- No larger concurrency ceiling, preemption, scripting, graphics optimization
  or wholesale service extraction is required for this feature.
