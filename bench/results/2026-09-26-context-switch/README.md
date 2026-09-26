# Context-switch spike results

The standalone context-switch spike was built from the `tasking-0.1` branch and
run against the two qualified emulators. Both completed the relocation strategy
with one successful check per switch, no canary failure, and zero page bytes
moved per switch. Interrupts were observed both inside the marked
switch-boundary windows and during task execution.

| Run | Switches | Interrupts | Boundary | Body | Checks | Canary | Page bytes/switch |
|---|---:|---:|---:|---:|---:|---:|---:|
| `1986` | 128 | 334 | 170 | 164 | 128/128 | 0 | 0 |
| VICE 3.10 | 128 | 310 | 203 | 107 | 128/128 | 0 | 0 |

The exact image is preserved as
`bench/artifacts/2026-09-26-context-switch-r1/context-switch.prg`
(SHA-256 `59d5aae56726299412cd4bc542b7e38d96702dc735c23ae28373648ae345bb0d`).
Build and emulator provenance is in that directory's README.

Reproduction:

```sh
make bench-context-switch
# 1986
../1986/1986 --disk build/bench/context-switch/context-switch.prg \
  --paste 'BLOAD"*":SYS10240' --paste-at 180 --frames 400 --no-throttle \
  --save-snapshot /tmp/ctx.vsf
python3 tools/snapshot_extract.py /tmp/ctx.vsf /tmp/ctx.bin \
  --address 0xf180 --size 32
python3 tools/context_switch_decode.py /tmp/ctx.bin
# VICE 3.10 (x128)
python3 tools/vice_capture.py build/bench/context-switch/context-switch.prg \
  /tmp/ctx-vice.bin --entry 0x2800 --result-address 0xf180 --result-size 32 \
  --state-offset 6 --complete-value 2
python3 tools/context_switch_decode.py /tmp/ctx-vice.bin
```

Verify the preserved bytes with `cd raw && sha256sum -c SHA256SUMS`.

## What the records prove

- Each task owns a separate context record; A and B use distinct seed
  registers, yield tags, stack pointers, stack markers, and resume addresses,
  so a cross-wired or stale record fails the per-task checks.
- The stack marker is written into the actively used top of the relocated page
  one, and the marker bytes are verified after every switch.
- The interrupt handler saves and restores A, X, and Y, so an interrupt landing
  at the switch boundary cannot corrupt the task accumulator.
- Boundary and body interrupt counts both have to be nonzero, and every switch
  must record a successful check, before the decoder accepts the record.

## Decision input

Both runs prove the relocated page-zero/page-one ownership path: A, X, Y, P,
SP, and PC restore per switch; the relocated zero-page and stack pages survive;
the task-visible bank matches the selected profile; and interrupts arrive at
the switch boundary and during task execution without corrupting a switch.
Relocation moves no page bytes per switch, while the bounded copy primitive
already characterized by [`bench/context`](../../context/README.md) transfers
the 33-byte context plus any live stack bytes.

Recommendation: adopt relocated page-zero/page-one ownership for the
cooperative scheduler, keep a bounded copy fallback, and confirm on a physical
C128 before freezing the ABI. The spike remains outside the production kernel
so the permanent scheduler placement is decided with this evidence.
