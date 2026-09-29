# Compact continuation and bounded raster prototype

Issue #14, `graphics-bounded-repaint`, 2026-09-29. **Not resident-linked, not a
new test disk, and not a measured input-latency improvement.**

The actual lane C policy matches the reference on trusted manager views and
valid scene-fencing sequences. One epoch replaces the separate caller revision;
geometry/content/cache/lifetime changes must invalidate before table mutation.
There are no persistent pointers, callbacks or drag/guard overlays. The target
18-byte state could replace the old damage box: 76 compact manager bytes minus
6 old damage bytes plus 18 lane bytes = the original 88. This replacement and
all real poll/paint/cache/busy interlocks are still unimplemented.

The row renderer matches original borders/font/buttons/strokes under many
sizes, flags, titles and clips. A row has at most three spans and 250 direct
pixel calls. The private raster entry validates before drawing, clears at most
four rows, draws one chrome row or commits one bitmap page, then resets clip
and acknowledges. Rejected/stale work touches no pixels, dirty flags, clip or
progress. CLIENT/RESTORE are delegated, not executed or declared bounded.
Tests use a bounded mock client and VIC-layout page model, not real apps/VIC.
Cancellation specifically revokes a glyph-row receipt before an invalid title
pointer could be read. No native timing/IRQ/NMI or physical qualification here.

Measured cc65 CODE: policy 2,641; chrome row 1,468; raster entry 1,175. The sizing
translation unit still contains a 70-byte synchronous chrome loop and old
callers; it is not poll integration. The private raster entry is explicitly
exported only so cc65 cannot omit it, with an object-presence regression gate.
Even granting removal of all old chrome/paint/compose bodies and 137 reserve
bytes leaves at least 3,171 bytes short, before helper/adapter/interlock costs.
State fit is not code fit; normal disks remain unchanged.

```
distrobox enter my-distrobox -- make repaint-lane
python3 -m unittest discover -s tests -p 'test_repaint_*.py'
```

The paired artifact directory preserves source, target objects/assembly/
listings, layouts, import records and hash bindings. The next gate is modular
service code placement/transport (or measured replacement), followed by real
renderer/lease providers and poll/cancellation/input/hardware qualification.
