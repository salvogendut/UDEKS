# Visible clock/background repair candidate

This is a separate bootable cache test disk, not a normal-image promotion.
It follows [WINDOW-CACHE-REPAINT.md](WINDOW-CACHE-REPAINT.md) and addresses
the clock-minute repair outlier without changing the four-row poll budget.

## Composition

The private compositor now keeps lower-window repaint damage bounded to that
window, rather than expanding it to the entire retained top window. It:

- repairs disjoint damage without requesting any cached paste;
- skips pixel repair when the retained top window completely covers damage;
- repairs only the exposed upper strip when the retained window covers the
  damage's full width and bottom edge;
- retains the existing background-plus-paste fallback for complex overlap.

These are geometry checks, not `xclock`/`xwave` application special cases.
The upper-strip path paints all intersecting lower windows in z order and
leaves the retained owner's pixels intact. Frontend phase `$82` marks repair
busy; banked ownership remains READY. Source/destination locks, invalidation,
handle reuse, resize fallback and row runtime/MMU/IRQ restoration are unchanged.

A fully hidden client still receives exactly one callback, with an empty
bitmap clip. This lets it acknowledge its update without drawing over the
retained image. In particular, the clock advances its previous-hour/minute
state rather than requesting the same repair every subsequent poll. There is
no new public entry, return code, application-ID policy or application binary.
Callbacks must respect the graphics clip, as they already must for partially
visible composition. Uncovering the client uses ordinary damage repaint.

Register placement of private window-pointer parameters pays for these checks.
The actual linked manager has CODE 7,695, RODATA 130 and HIGHBSS 88 bytes;
the transport remains 377 bytes and held resident padding is 87 bytes. All
normal/panic segments remain identical to the normal build, including the
8,000-byte shadow at `$A1E0-$C11F`. cc65 library module sets/sizes are unchanged;
private bridges/checksums are regenerated from the actual link. No additional
resident BSS, module bytes, bitmap allocation or common-RAM scratch is used.

## Measured results

The reference is byte-identical to the previously qualified tiled image.
Both variants run the same native keyboard/1351 mouse sequence, background
clock, CIA2 NMI pressure and three exact-geometry `date` changes in 1986.
Timing starts at the published `$CF40` clock-set syscall, and ends when the
clock has acknowledged the minute, the lease is READY, the current page copy
has returned and the dirty-page map is empty. It includes scheduler/control
overhead, not just the drawing function. One PAL frame is 20 ms.

| Clock repair case | PAL frames, reference → candidate | Page copies, reference → candidate |
| --- | --- | --- |
| Fully hidden: wave at (109,40) | 278 → 119 | 40 → 0 |
| Exposed four-row upper strip: (109,65) | 278 → 126 | 44 → 2 |
| Complex overlap fallback: (144,88) | 267 → 254 | 40 → 33 |

Results are identical for D71 and D64. Both variants invoke the clock callback
once per change, do not repeat it over the following 120 frames, and invoke
neither the wave painter nor additional Z80 jobs. Every byte of each case's
8,000-byte shadow and VIC canvas matches between variants and surfaces; the
17472-pixel retained image oracle also passes.

Across the original sixteen native drag cases, sampled worst settled-paste
latency drops from 313 to 163 frames. Median full move/repaint remains essentially
unchanged (194.5 → 194 frames), as does median paste-page count (22.5). This
is not a claim of universal worst-case responsiveness: complex overlap still
takes about five seconds in the forced clock-change sequence. More selective
partial-overlap repair remains a next optimization, and physical C128/input/
RESTORE qualification is still separate.

The read-only profiler now distinguishes an IRQ/NMI redispatch to an entry
breakpoint from a second call: the caller frame, SP, A/X/Y and P must all be
identical. Interrupt cycles stay in the measurement. Three such redispatches
occur in the candidate's native sequence; the reference has zero. No CPU,
keyboard queue, UDEKS record or IRQ state is patched by the profiler.

## Qualification and reproducibility

The host pixel oracle compares complete canvases after each repaint and after
uncovering, over 117 geometry combinations plus disjoint/high-X/three-layer
cases. It checks that hidden clients acknowledge exactly once and that the
optimized/disjoint cases request no cached paste. Native 1986 also exercises
early-drag fallback, all sixteen retained moves, oversize resize, partial-paste
Ctrl+C, console typing/history, graphics shutdown/restart and private guards.
VICE cold-boots both formats and checks capture, pixels, NMI and restart;
native VICE mouse dragging and physical hardware are not claimed by that run.

Candidate incremental and clean parallel builds produce identical disk hashes:

- D64: `d4e2a96cbd8c9be1f334d27c964c876a3bf70fa3b181bdd12b9de2dac24530e7`
- D71: `e27ebf93562fe786c42326b6c4e21bbd498f0fa1a2831fa0df74f9ac57cc8f8a`

Normal D64/D71 remain `65a37c26...` / `d99463d6...`. Source, maps, disks, runners,
emulator provenance, raw pixel records and comparison bindings are preserved
under `bench/{artifacts,results}/2026-09-28-window-cache-occlusion{,-reference}`.
Archives contain no ROM-bearing emulator snapshots and cannot be overwritten.

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_occlusion.py build
distrobox enter my-distrobox -- python3 tools/window_cache_occlusion.py --reference build
distrobox enter my-distrobox -- python3 tools/window_cache_occlusion.py 1986
distrobox enter my-distrobox -- python3 tools/window_cache_occlusion.py --reference 1986
python3 tools/window_cache_occlusion.py vice
python3 tools/window_cache_occlusion.py --reference vice
python3 tools/window_cache_occlusion.py compare
python3 tools/window_cache_occlusion.py preserve
python3 tools/window_cache_occlusion.py --reference preserve
```

For a manual test, boot the candidate D64, run `xinit`, `xclock &`, `xwave &`,
then drag the wave to cover the clock's body (or the whole clock). Use
`date 121000`, then `date 121100` to force clock changes. Check that the wave
stays intact, dragging and console input still work, and uncovering the clock
shows the updated time. Also check Ctrl+C in a foreground `xwave` and
`xinit -q` followed by a restart. No commit/push or normal promotion is implied.

Final checks: 793 host tests, archived manifests and Python compilation pass;
normal container `boot`/`all` and the real-object `placement-check` pass.
Candidate clean-parallel output matches the incremental hashes above.
No VICE sessions remained at qualification completion.

User feedback on 2026-09-29: "looks good" for the presented candidate. Platform
and individual cases were not specified; physical C128/input/RESTORE and general
responsiveness gates remain open. Next is selective partial-overlap repair.
This feedback does not authorize commit/push or promotion to normal images.
