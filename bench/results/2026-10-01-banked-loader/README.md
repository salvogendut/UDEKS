# Banked image delivery — 2026-10-01

Issue #30, branch `graphics-four-apps`, based on `b94bd43` plus this checkpoint.
This is **load-only qualification**, not four running graphical applications.
VICE 3.10 x128, true-drive D64/1541 and D71/1571, cold boots. No new 1986 or
physical-C128 qualification is claimed.

`tools/banked_loader_probe.py` installs a one-shot hook in a map-checked free
bank-0 range; the real managed service poll invokes it. The hook preserves
the pre-existing request and CPU registers, calls the private loader using a
test request, snapshots the response, removes itself, and returns to normal
polling. An inert hook self-test precedes calls into the banked loader.

Both formats pass independent loading, exact full-slot limits, image/BSS
comparison, malformed/truncated/trailing files, overcapacity, missing files,
name/padding validation, owned-slot rejection, stopped/zombie ownership
guards (fault-injected, not scheduled tasks), release/reload and complete
request/kernel-map preservation. Legacy clock and wave code plus the linked
Z80 worker remain unchanged while both extra images are held. Console
`cowsay` and later calculator loading work. Final `app3.bin` and `app4.bin`
are VICE saves (two-byte load prefix) of the full-slot fixtures and zero BSS.

`legacy/` records the normal D64 calculator arithmetic regression, reciprocal
clock/calculator slot rejection, wave coexistence, shell commands, restart
and shadow/VIC bitmap equality. Clicks use the existing WM queue; this is not
a new native mouse/drag test.

The sibling artifact directory preserves the exact normal and fixture disks,
loader binaries, maps, keyboard assembly for probe bindings, and legacy UDEX
images. A clean, separate `make -j8 boot graphics-apps-check placement-check`
build reproduced both normal disk images byte-for-byte. The banked loader is
1,032 bytes; common TASKLOADER/BOOTINIT occupy 1,389/126 bytes respectively.

Reproduction from this source revision:

```sh
distrobox enter my-distrobox -- make -j8 boot graphics-apps-check placement-check
make banked-apps-probe
python3 tools/xcalc_probe.py --output build/four-apps/banked-legacy-regression
```

The large test hook initially exposed a VICE remote-monitor byte-list failure
(also reproduced with an inert routine). Monitor writes are now chunked to
32 bytes within one paused session. Only the passing reruns are preserved.
Failed diagnostic sessions were terminated; the published `build/udeks.*`
snapshots were not changed.
