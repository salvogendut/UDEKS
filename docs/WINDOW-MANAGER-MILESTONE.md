# Window-manager milestone — merge scope

This milestone checkpoints the qualified graphics/window-manager foundations
and reproducible opt-in cache candidates. It does **not** enable cached dragging
or deferred-background dragging in normal `make boot` images.

Included: display-service assembly primitives and budget/placement checks,
explicit UAPP whole-image completion, safe deferred 8502 NMI recording/draining,
generic cache lease/state/controller code, guarded bank-crossing transport,
host/emulator test runners, and immutable source/map/image/result evidence.
The opt-in candidates cover retained pixel movement, partial background repair,
clipping/stacking/invalidation, input/cancellation and deferred drag start.

The minimal xwave whole-image notification is an adapter to the generic window
contract; it is not the app-local projection experiment. Projection tables,
wireframe-specific replay changes, their private build hooks, test images and
tests are explicitly excluded from this milestone and retained separately.
Future such optimizations belong to xwave, not manager policy or kernel BSS.

## Qualification and limits

The latest window-manager candidate is
`bench/artifacts/2026-09-29-window-drag-start/build/udeks-cache.d64` (or D71).
Native 1986 keyboard/mouse tests and VICE boot/pixel/NMI tests pass both formats;
host tests include complete canvases, invalidation, clipped repair and layout.
Private clean parallel builds produce identical disks and preserve frozen
normal/panic segment boundaries and runtime-helper closure. No ROM-bearing
snapshots are checked in.
Archive attributes preserve exact bytes and tool-emitted listing/map spacing;
whitespace checks apply to maintained source rather than rewriting hash-bound
evidence.

User feedback: deferred xclock drag start is "much better". Its native measured
start drops 265→16 PAL frames over xwave. Background repair on release still
takes seconds; this does not complete the responsiveness goal. Native VICE
mouse interaction, physical RESTORE/Z80 NMI routing and general hardware/input
acceptance are not inferred from emulator or unspecified-platform feedback.

## Next manager step

1. Integrate the accepted module, regenerated acceptance/checksum bindings and
   compositor hooks into an explicitly selected normal-build configuration.
2. Preserve fixed allocations, published runtime addresses, generic ownership
   and bounded row work; do not import xwave projection policy.
3. Qualify clean normal/panic builds, D64/D71, both emulators, native input,
   resize/restack/close/cancel and graphics shutdown/restart.
4. Request the physical/input/RESTORE acceptance run before claiming hardware
   qualification or changing the default cache policy.

Keep release/background latency as an open manager/composition issue. This PR
records a working milestone, not an implicit production-cache promotion or
closure of all graphics responsiveness work.
