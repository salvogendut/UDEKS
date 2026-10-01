# Native banked C execution — 2026-10-01

Issue #30, branch `graphics-four-apps`, based on `b94bd43` plus the load-only
and native-execution working-tree increments. VICE 3.10 x128, cold native boot,
true-drive D64/1541 and D71/1571. No new 1986 or physical C128 qualification.
This proves independently executing C tasks, **not four graphical apps**.

| Run | Task 3 iterations | Task 4 iterations | Reloaded task 3 |
| --- | ---: | ---: | ---: |
| D64 / 1541 | 169 | 183 | 30 |
| D71 / 1571 | 71 | 65 | 33 |

Iteration counts depend on host/monitor timing and are not a speed comparison.
Both separate native C executables have 661 image + 7 BSS bytes. Entry is
base + 2, testing the non-base UDEX entry path. Recursive automatic arrays
remain live through SLEEP, with variable depths and per-task seeds; YIELD
interleaves iterations. Both clients validate SLEEP response sequence/state.
The lowest sampled software SP is `$8C47` / `$8F47` (105 bytes below entry).
Lower/upper software-stack guards and CPU-page canaries remain `$A5`; returned
C status becomes EXIT 43/44. Reap clears all slot/context/wait fields. Reload
starts from fresh DATA/BSS and repeats the execution check.

Admission/reap uses a one-shot hook at the normal managed-service poll, as in
the previous load-only probe, preserving registers, existing UTRQ and mapping.
No arbitrary PC takeover starts these clients: normal scheduler dispatch does.
Monitor control flags ask the real C main loops to finish. Fault-injected
wrong-parent/unowned zombies reject reap; live activation/release/reap rejects
with EBUSY. Managed callback images reject native activation with ENOEXEC.
The full malformed-image/ownership tests also run before native admission.

Clock and wave run on their existing paths; their code and the Z80 worker
remain unchanged. `cowsay` runs while both extra clients execute. Subsequent
calculator loading and console commands work. `legacy/` separately preserves
the normal-disk calculator arithmetic (4.00, 3.00, 4.75), reciprocal slot
rejection, wave coexistence, restart and shadow/VIC bitmap equality. Clicks
are injected at the WM queue; this does not qualify native mouse input.

The sibling artifact directory holds exact normal/fixture disk images,
client UDEX files, loader binary and binding/layout maps. The new module is
1,635 bytes at `$D900-$DF62`; resident C is unchanged. Common TASKLOADER and
BOOTINIT occupy 1,389 and 124 bytes. A separate clean parallel build produced
byte-identical D64, D71 and both client UDEX files, passing both placement gates.

```sh
distrobox enter my-distrobox -- make -j8 boot graphics-apps-check placement-check banked-native-fixtures
make banked-native-probe
python3 tools/xcalc_probe.py --output build/four-apps/native-legacy-regression
```

VICE captures have the usual two-byte load-address prefix. Repeated captures
overwrite the same filename: task 3's final client-state samples describe its
reload, while `result.json` retains both runs. Every probe-owned VICE process
is terminated. Published `build/udeks.*` snapshots remain unchanged.
