# Engine IPC demo — slice 2

Full D71/D81 system images with independent ENGINE.BIN and ENGTEST.BIN added.
Standard programs, the time module and kernel are preserved. D64 is skipped:
the two programs need 34 additional blocks. The server/client/clock/draw fit
all 24 launch orders without joined allocations. ENGINE fits tasks 3/5;
ENGTEST fits task 3. Maps and layouts are preserved here.

Boot a disk and type:

```text
xclock &
xdraw &
engine &
engtest --nop
engtest
engtest --stop
engine &
engtest
engtest --stop
```

Expect `engine: ready` and `engtest: OK`. Default ENGTEST checks exact eight
samples and next phase 50. After stopping, ENGTEST reports an error and
`echo $?` returns 2 (missing server). Move the clock and draw with the engine
alive, then confirm another successful request. Graceful stop is
`engtest --stop`, not `engine -q`.

Native sibling 1986 D81 basic/input proof passes; broader media, cancellation,
soak, manual and real hardware acceptance remain future work.
[Evidence and limits](../../results/2026-10-15-engine-service/README.md).
SHA256SUMS binds all files. These are candidate demos, not refreshed root downloads.
