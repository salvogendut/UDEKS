# Ordinary-slot / multiple-instance XVIEW qualification

2026-10-09, `app-cbm-viewer`, kernel baseline `fe26bf1`. No kernel changes.
The earlier `../2026-10-09-cbm-viewer` preserves the joined-slot prototype;
this directory supersedes it for the allocation fix. Source and probe
snapshots, exact executable/map and selected captures are preserved here.

The new file is **3,184 bytes**, with **2,442 image + 1,385 BSS = 3,827**.
Both ordinary slots 3 and 5 fit; no donor slot is consumed. Build with
container `make xview`. Its required-slot checks reject future size growth
that would break the feature. The C app uses existing argument and graphics/
file assembly bindings, not the general console/input runtime. Static locals
are private to each relocated, nonrecursive app instance. Tile construction
streams one row at a time without reducing the 160-tile acceptance limit.

Final candidate disks (all three supplied pictures, original DOS files intact):

```text
6e7bca86513636a5e7d524ab5a7af8efb33216a93c09a76655efc354e4c555f8  build/xview/udeks-pictures-r3.d71
1e92b1c5050f67f833c1815d7f936f2a0e2ef0bbbf2fe4d63a602fc45e22790f  build/xview/udeks-pictures-r3.d81
```

Both VICE x128 Flatpak runs cold-booted private copies with true drive
emulation, using the final `tools/xview_probe.py`:

```sh
python3 tools/xview_probe.py --disk build/xview/udeks-pictures-r3.d71 \
  --picture PICS/CLOCKWORK.CBM --second-picture PICS/ALEX2.CBM \
  --small-picture PICS/ALEX2.CBM --drive 1571
python3 tools/xview_probe.py --disk build/xview/udeks-pictures-r3.d81 \
  --picture PICS/ALEX.CBM --second-picture PICS/CLOCKWORK.CBM \
  --small-picture PICS/ALEX2.CBM --drive 1581
```

Final gates: `make check` passes **1,649 tests** and all preserved checksums;
container `make graphics-apps-check` passes (including 6502 rectangle/input
tests and all 24 standard four-app launch orders). Rebuilt normal D71/D81
images remain byte-identical to the accepted baseline.

Each passed invalid/missing/too-large files, exact pixels before/after drag
and uncover, independent simultaneous pictures in slots 5/3, separate close
and foreground Ctrl+C, safe rejection of a third viewer, slot reuse, load
cancellation, stream cleanup, relocated code integrity and stack guards.
Keyboard-queue and bounded pointer-getter hooks exercise normal shell/WM
paths; they do not qualify physical input hardware. No new 1986 or real C128
result is claimed. All owned VICE processes were terminated.

The three-app test requires actual drawing publication, not just three
window frames: XWAVE retained paths **1,128**, clock commands **344**, ALEX2
tiles **728** bytes, total **2,200 of 2,304**. ALEX and CLOCKWORK together
consume 2,296 bytes; either of those larger pictures plus both clock and
wave would exceed the separate shared retained-display pool. Window titles
identify each picture; `xview -q` stops one name match, while a close button
or foreground Ctrl+C selects the intended instance.

Captures have the VICE two-byte load-address prefix. Reports contain disk,
fixture and app hashes. `tests/test_xview_evidence.py` verifies executable
fit, all six viewer/clock/wave launch orders, reproducible final disk
packaging, retained sizes, both picture pixel sets and the survivor after
cancellation. Full logs/disposable disks remain under
`build/xview/probes/1571-robnuy8p` and `1581-mg3ytl43` in this worktree.
See [the user test instructions](../../../abi/cbm.md).
