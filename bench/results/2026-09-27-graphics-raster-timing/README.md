# Raster timing and isolated link — 2026-09-27

Branch: `graphics-raster-audit`, issue #6. Parent audit commit: `42e19af`.
Actual display source SHA-256:
`b46df572db0de5499c6558abac3bc3b3f889d63086e54f5efd5d1e159968ba41`.
Toolchain: cc65 V2.18 (Fedora 2.19-15.fc44), `-Oirs`; VICE Flatpak x128 3.10;
1986 `0b1151c0b512f46c141cd961cd6735cbe30aa443` with the user's existing
display/frontend working-tree changes. We did not edit the emulator. The
native suite was rebuilt/rerun after discovering that checkout change; all
records reproduce the original counts exactly. `1986-provenance.json` records
the revision, dirty paths, and hashes of compiled sources and tracked headers,
verified unchanged across compilation/run. This is not a pristine checkout
claim; the native harness excludes SDL `main.c`, as documented by the builder.
Exact eight PRGs are preserved in `bench/artifacts/2026-09-27-graphics-raster-timing`.
No ROMs or full machine snapshots are distributed.

## Primitive timing

| Workload | VICE baseline counts | VICE scratch counts | Reduction |
| --- | ---: | ---: | ---: |
| Short lines | 1,743,838 | 1,539,646 | 11.709% |
| Clipped long lines | 7,183,099 | 6,286,556 | 12.481% |
| Aligned fills | 13,641,392 | 10,423,473 | 23.589% |
| Clipped fills | 13,954,308 | 10,624,921 | 23.859% |

1986 gives the same reductions to three decimal places. All 16 complete pixel
and dirty-map captures match the independent reference, not merely one another.
Raw records and hashes are preserved; see `report.json` for both engines.
The record includes fixed timer overhead. IRQs and display are disabled; bitmap
commits, window chrome orchestration and foreground job handling are excluded.
These results do not predict an equal percentage improvement in window latency.

1986's raw counts exceed VICE by 27/110/209/213 counts for baseline and
24/96/160/163 for scratch—one count per approximately 65,536 events. Inspection
of its `cia.c:timer_advance` shows it advances to underflow from the current
counter value; this is consistent with a cascade/reload period discrepancy.
That attribution is an inference, not a physical-CIA qualification. No emulator
source was changed and counts were not normalized to hide the difference.

## Scratch ownership audit

Current line/fill bodies have no callbacks, service polls, syscalls, yields,
or Z80 handoffs. Fill does not call line; line plots inline. Window chrome and
app painters call primitives serially. `pointer_irq.s` calls only its assembly
pointer/port helpers and the fixed scheduler tick; the tick advances monotonic
counters and does not schedule, render, or invoke C. Consequently static
scratch is compatible with the current cooperative ownership model.

This is not permission for preemptive/reentrant rendering. A future preemptive
task or interrupt display client needs display-service serialization or its
own scratch. User-supplied nested callbacks may not be added inside these loops.
The old `$F340-$F358` xwave row ABI remains reserved and untouched.

## Whole-link budget gate

```sh
distrobox enter my-distrobox -- python3 tools/graphics_raster_audit.py
distrobox enter my-distrobox -- python3 tools/graphics_raster_link_audit.py
```

The link audit replays the normal resident command into private directories,
including **every** split linker output. It replaces only the full graphics
object for the candidate. Both maps and the result are preserved.

CODE shrinks 81 bytes; BSS grows 32, leaving a measured 49-byte end reduction.
ZP and fixed syscall/task-gate segments do not move, but the candidate shadow
starts at `$A1AF`, not `$A1E0`. Private kernel providers also move. Therefore
this isolated image is **not bootable with production delivery/import bridges**
and has not been packaged or run as a kernel. Production disks remain identical
to the qualified PR #7 images.

Before production integration, preserve the shadow/staging contract explicitly
(for example, a named 49-byte code reservation with linked assertions, then
consume it in a measured compositor change), regenerate all import bridges,
and qualify normal/panic layouts, clean builds, D71/D64 input/window smoke and
bank bitmap equality. Physical-C128 and end-to-end redraw latency remain open.
