# Repaint clipping CODE-recovery gate

Issue #14, 2026-09-29. This is a **private, unbootable** measurement of the
still-used `set_damage_intersection` helper, not a production manager change.

`tools/window_repaint_intersection.py` builds four local-allocation variants
from the source-bound geometry candidate. The best reuses the incoming
width/height parameters as right/bottom endpoints and registers the remaining
left/top locals. Both complete normal and panic isolated links save exactly
**23 CODE bytes**, allocate no new state or runtime helpers, and retain all
fixed segments. The VIC shadow shifts back by 23 bytes relative to the
private bank-0 admission link. A host test compares both implementations
against an independent clipping/side-effect oracle for 4,096 valid geometry
cases, including empty intersections. `make repaint-intersection` rebuilds
the predecessor links and this measurement in the reference container.

The saving reduces the optimistic resident shortfall from **385 to 362 bytes**,
still before real caller rewrites, a bounded provider, delivery or teardown.
Installing a 23-byte rewrite of a helper likely to disappear would churn the
frozen production layout without materially advancing bounded repaint. It is
therefore **not** selected for production.

The current call graph has two intersection calls in the legacy
`paint_window_damage` and one in `cache_paint_image`. Its 316-byte C body and
the 156-byte cache-paint body are *additional potential* retirements beyond
the already-budgeted old chrome/paint/compose bodies, but neither can be
credited while these paths are used. The next meaningful CODE gate is a real
bounded client/cache replacement with explicit deferred completion and
source-verified removal of the legacy users. Only then can complete links
measure net savings after the new callers and providers are charged. The
current `void` painter and cache paths cannot simply be deleted or queued
unchanged. No new test disk or hardware prompt follows from this experiment.
