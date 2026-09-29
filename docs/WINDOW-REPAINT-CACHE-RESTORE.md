# Bounded retained-image restore checkpoint

Issue #14, 2026-09-29. `bench/window-repaint-provider/cache_restore.{h,c}`
is a **private, unbootable** cache provider, not a change to the resident
window manager or the UAPP interface.

The provider consumes one full-window `RESTORE` lane receipt per call. It
acquires synchronous CACHE admission, validates the receipt, checks that the
manager's retained content generation still matches the cache lease, and
starts a full paste if needed. Each successful call copies exactly one
scanline, checks owner/row/phase progression, commits at eight-row boundaries
or completion, acknowledges the receipt, and releases admission. A busy
admission or temporarily busy image defers without painting. A broken paste,
invalid image, or rejected acknowledgment invalidates retained eligibility
and queues full-window scene repair; it cannot be retried as if the partial
image were complete. The repair hook must use the admission already held and
must not invoke a client painter.

The prototype deliberately rejects a `RESTORE` clip smaller than the whole
window. The current cache prefix operation starts at the cached image's left
edge, so it is not a general arbitrary-clip restore. A manager integration
must expand a retained move to the complete cached window **before** the
lane selects work, or use a separately qualified clipped-paste/fresh-client
path. Existing `cache_paint_image` also performs synchronous background
`compose_damage`; merely swapping in this provider would still block input.
The lane's bounded clear/chrome/client phases must replace that composition
in z-order first. Between polls, all cache identity mutations must use the
same admission and invalidate the lane epoch; the binding must check the
actual content generation in both READY and PASTING rather than calling the
READY-only cache command.

`tests/test_repaint_cache_restore.py` checks one-row progress, admission
deferral, stale receipt, cache failure, repair failure, and receipt completion.
It also binds the provider to the real host repaint lane: a whole-window
ticket completes after 18 row steps, while a left-clipped ticket paints none.
The reference-container `cc65 -t none --cpu 6502 --standard c99 -Oirs`
compile and `od65 --dump-segments` report 1,170 CODE bytes and zero
RODATA/BSS/DATA/ZP bytes for the provider alone. This excludes binding code,
background raster, and delivery, so it is **not** a resident fit. The prior
optimistic shortfall is still at least 362 bytes before this provider; no
legacy `paint_window_damage`, `cache_paint_image`, or `compose_damage` bytes
are yet retired or credited.

Next gate: build a source-locked replacement for background composition and
the manager's retained-generation binding, then remove the now-unused legacy
callers in an isolated normal/panic link. Only a net-fit, bootable candidate
qualifies for VICE, 1986, and real-hardware testing.
