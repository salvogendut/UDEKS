# Xwave responsiveness — issue #6

Branch: `xwave-responsive-rendering`. Baseline: PR #5 / `1b7a6e0`.
Tracking: https://github.com/salvogendut/UDEKS/issues/6.

The machine-input smoke measured a 689-PAL-frame keyboard-release delay during
initial xwave painting. The synchronous compositor invokes `paint_wave`, which
leases all 21 Z80 rows and draws every segment before returning. Raster mouse
sampling continues, but keyboard/window/job service passes are delayed.

## Plan

1. Audit the live map and instrument launch/input/plot progress. Preserve the
   original 689-frame qualification as the baseline, not a new performance claim.
2. Compact the drawing loop to make room for the cooperative cursor. Consider
   geometry-specific axis lookup tables in a later measured optimization:
   APP2 is only 2,560 bytes and bootfs has one emitted byte spare.
3. Keep the compositor callback as an idempotent cached-content replay; advance
   initial sampling/drawing through a bounded application poll cursor. Add only
   the missing public clipped begin/end paint bindings, preserving all existing
   UAPP addresses and the resident/VIC-shadow boundary. Do not recursively poll
   services or yield while a compositor/clip callback is live.
4. Qualify input and foreground cancellation **before** initial plot completion,
   background-clock survival, drag/resize/stacking/cache behavior, full final
   bitmap equivalence, and repeated close/relaunch cycles. Record observed latency,
   including synchronous cached replay/chrome costs rather than concealing them.
5. Re-run host tests, placement-check, clean-build determinism, 1986 and VICE
   D71/D64 regressions. Keep issue #4's manual and physical-C128 gates open.

Cached compositor replay is a separate bounded-by-grid cost, not automatically
made cooperative by step 3. If its measured latency remains excessive, retain
that as an explicit issue #6 blocker and design a deferred compositor before
claiming all window repaint operations responsive.

## Initial budget

`xwave.map`: 18 STARTUP + 1,667 CODE + 41 RODATA = 1,726 emitted bytes;
536 BSS; 2,262 total, leaving 298 bytes in APP2. Production bootfs is
11,707/11,708 bytes. The UAPP table ends at `$CFF9`, leaving exactly two
three-byte entries before `$D000`; existing begin/end paint implementations
already exist in the window service. Any added resident code must be offset by
measured reclaim, not silently move the fixed `$A1E0` VIC shadow/delivery source.

## First increment

The application now samples at most one 25-point row and draws at most four
vertices per poll, ending at a row boundary. The compositor callback draws
only the already-drawn prefix and never enters the Z80. Initial creation draws
no surface points; all 525 points eventually produce the same wireframe.
Topmost/non-dragged clipped drawing uses appended UAPP 0.2 entries. End-paint
commits dirty pages, not the entire bitmap. Non-reentrant scratch avoids cc65
software-stack overhead; no callback or nested service pass occurs inside it.

Measured application: 1,708 emitted bytes (18 fewer than baseline), 549 BSS
bytes, 2,257-byte allocation. Bootfs: 11,689/11,708 bytes (19 free). Kernel BSS
still ends at `$A1DF`, shadow starts at `$A1E0`, and all old UAPP/zero-page
addresses remain fixed. The three-byte end-paint commit call is balanced by
retiring three bytes of the unused keyboard selector snapshot; its scratch
reservation and idle-selector behavior remain unchanged.

Host execution of the real application checks per-poll budgets, completed
pixel-for-pixel wireframe equivalence, geometry changes, partial damage replay,
pause/resume, close/relaunch, and the offline-worker fallback. Native 1986
D71/D64 and VICE results are recorded with the exact disk images separately.

Issue #6 remains open: compositor replay, window chrome, and exposed clock
redraw are still synchronous. Native Ctrl+C reaches the app during row 0 but
completion of close takes 222 PAL frames with the clock underneath. The smoke
has a maximum release delay of 383 frames (baseline 689), not a general
interactive-latency qualification. The user reported the requested manual
1986 interaction check looked good (2026-09-27); no measured timing or separate
physical-C128 run was supplied. Physical C128 checks remain outstanding.
Do not mark roadmap task
migration or responsive compositor completion from this increment.
