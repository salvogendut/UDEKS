# Deferred NMI ownership — 2026-09-28

Status: the 8502 handler is installed in normal builds and emulator-qualified.
Pixel-cache moves remain disabled. Physical C128 confirmation is pending.

## Ownership and bounds

`nmi.s` is a small assembly core module. At input-service startup, under the
kernel I/O profile, it disables inherited CIA2 interrupt sources and installs
an eight-byte always-mapped handler at `$FFE2-$FFE9`. The handler saves A,
sets `$FFF5` to one, restores A, and returns with RTI. It does not access
devices, change the MMU, use compiler state, schedule, or invoke C. X/Y and
the interrupted status remain intact; the hardware stack belongs to the
interrupted context.

The pointer IRQ trampoline selects kernel I/O and saves registers before
calling the drain routine. That routine clears the pending flag, acknowledges
CIA2, and increments a wrapping 16-bit **coalesced drain** counter at
`$FFF6-$FFF7`. It is not a lossless event queue or a timer clock. Clearing the
flag before acknowledgment leaves a later edge pending for the next IRQ.
An IRQ-masked lease may defer draining, but does not prevent the NMI stub
from safely recording an event.

Placement remains within the existing handoff/interrupt reservation:

| Owner | Bytes |
| --- | --- |
| Z80 return gateway | `$FFD0-$FFE1` (unchanged) |
| 8502 NMI handler | `$FFE2-$FFE9` |
| Reserved gap | `$FFEA-$FFEC` |
| Z80 first-entry bootstrap | `$FFED-$FFF4` (unchanged) |
| NMI pending/drains | `$FFF5-$FFF7` |
| Reserved gap | `$FFF8-$FFF9` |
| Native vectors | `$FFFA-$FFFF` |

This does **not** define RESTORE as reset, task cancellation, or shell input.
After input startup it is safely recorded/drained; Ctrl+C retains the existing
foreground-cancellation behavior. RESTORE during the boot stages or handler
installation is outside this gate. The handler is for the 8502, not a newly
defined Z80 NMI handler; emulator passes across Z80 leases do not replace a
physical-machine routing/RESTORE check.

## Evidence

The standalone combined-C proof uses the exact live stub and continuous CIA2
Timer A NMIs. Both emulators observe arrivals in the worker-flat C lease and
outside it, with exact arrival/drain totals, full bitmap/dirty oracles and
runtime/stack/guard checks. A diagnostic-only common observer counts arrivals
at `$FF20`; it is never linked into the normal OS, where that address is live.

| Emulator | Alignment-case NMIs / worker-flat | Repeated-paste NMIs / worker-flat |
| --- | ---: | ---: |
| 1986 | 9,027 / 105 | 15,399 / 102 |
| VICE | 8,896 / 122 | 15,292 / 106 |

Changing the live stub's STA-pending opcode to BIT is the single-byte negative
control. Pixels still match, but only one arrival and zero drains occur, and
the positive decoder rejects it. Saved inputs, exact PRGs, raw records,
emulator provenance and hashes are in
`bench/{artifacts,results}/2026-09-28-window-cache-nmi`.

The normal-build gate cold-boots D71 and D64 in both emulators, keeps a CIA2
timer active across xinit, clock and Z80 wave leases, and verifies actual
completion, stub/vector and unchanged Z80 bytes. Native 1986 additionally
injects RESTORE through its keyboard API before timer stress and runs real
typing/backspace/history, mouse drags, foreground Ctrl+C, console recovery,
and background-clock survival. Drain counts are 12,590 on each native disk;
VICE counts are recorded in the run files and are not timing benchmarks.
Evidence: `bench/{artifacts,results}/2026-09-28-nmi-integration`.
The separate `...-nmi-integration-layout` record checks the same disk's shadow
clear, scheduler installation, reclaimed tail and shadow/bitmap equality.

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_nmi.py build
distrobox enter my-distrobox -- python3 tools/window_cache_nmi.py run --engine 1986
python3 tools/window_cache_nmi.py run --engine vice
python3 tools/nmi_integration_probe.py build
distrobox enter my-distrobox -- python3 tools/nmi_integration_probe.py 1986
python3 tools/nmi_integration_probe.py vice
```

The standalone sources can be reproduced from their preserved checkpoint;
later unrelated resident edits must not be mistaken for its exact input set.

## Budget and next gate

The linked NMI object is 71 CODE bytes, no BSS/ZP. Two JSR sites add six bytes;
77 bytes are charged to shared padding (136 → 59). All primary segment bounds,
compiler-runtime addresses and scheduler reservations remain frozen. The
placement audit rejects NMI or pointer footprint drift at this checkpoint.

At this checkpoint remaining padding was **281**. Subsequent private C manager
savings recover 221: **502 current padding**, 261 after the 241-byte binding.
The actual resident continuation experiment remains at least 739 bytes short
before real hooks and delivery validation. See [WINDOW-MANAGER-BUDGET.md](WINDOW-MANAGER-BUDGET.md).
This is not proof that cache integration fits. Next, measure the actual C
manager continuation and identify service-local savings or a reviewed
relocation before enabling it. Do not borrow shell stacks, app slots, common
gateways or scheduler padding. Keep redraw fallback and partial/obscured-image
rejection. The completed-image generation, damage/clock interactions and live
cached drag/resize/cancellation gates remain unfinished.

## Manual gate

Boot `build/boot/udeks.d64` or `.d71`, run `xinit`, `xclock &`, and `xwave &`.
Press RESTORE during plotting and after a drag; the system should stay alive,
the mouse should keep working, and the console should still accept commands.
Also check foreground `xwave` → Ctrl+C while the background clock survives.
RESTORE is not expected to cancel the wave. This tests resilience, not faster
cached dragging; unchanged-size moves still replay pixels.
