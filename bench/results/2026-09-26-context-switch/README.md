# Context-switch spike results

The standalone context-switch spike was built from the `tasking-0.1` branch and
run against the two qualified emulators. Both completed the relocation strategy
without a check or canary failure and moved zero page bytes per switch.

| Run | Switches | Interrupts | Checks | Canary | Page bytes/switch |
|---|---:|---:|---:|---:|---:|
| `1986` | 128 | 136 | 128/128 | 0 | 0 |
| VICE 3.10 | 128 | 150 | 128/128 | 0 | 0 |

Reproduction:

```sh
make bench-context-switch
python3 tools/context_switch_decode.py raw/1986.bin
python3 tools/context_switch_decode.py raw/vice-3.10.bin
```

The `1986` record came from attaching
`build/bench/context-switch/context-switch.prg`, injecting
`BLOAD"*":SYS10240`, and extracting `$F180` from the saved snapshot. The VICE
record came from `tools/vice_capture.py` with entry `$2800`, result `$F180`,
and complete state `2`. Verify the preserved bytes with
`cd raw && sha256sum -c SHA256SUMS`.

## Decision input

Both runs prove the relocated page-zero/page-one ownership path: A, X, Y, P,
SP, and PC restore per switch; the relocated zero-page and stack pages survive;
the task-visible bank matches the selected profile; and timer interrupts
arrive during task execution without corrupting a switch. Relocation moves no
page bytes per switch, while the bounded copy primitive already characterized
by [`bench/context`](../../context/README.md) transfers the 33-byte context
plus any live stack bytes.

Recommendation: adopt relocated page-zero/page-one ownership for the
cooperative scheduler, keep a bounded copy fallback, and confirm on a physical
C128 before freezing the ABI. The assembly spike remains outside the production
kernel so the permanent scheduler placement can be decided with this evidence.
