# Tile-boundary screen commits — 2026-09-28

This is a measured follow-up to the [live cache candidate](WINDOW-CACHE-LIVE.md),
not closure of the responsive-compositor or physical-hardware gates. New separate
test disks are in `bench/artifacts/2026-09-28-window-cache-repaint-tiled/build/`
as `udeks-cache.d64` and `.d71` (identical copies under
`build/window-cache-repaint/tiled/`). Do not use the private repo's ordinary
boot disks; they do not deliver the banked cache module.

Run `xinit`, `xclock &`, then `xwave`; wait for the plot/capture and drag normally.
Check outline-only dragging, return of cached pixels, Ctrl+C, console typing,
resize fallback and `xinit -q`/restart. Leave the clock running across a minute
change as well: that path still has a substantial delay.

## The change

The original four-row batch commits whole dirty 256-byte bitmap pages after
every batch. VIC-II bitmap scanlines are interleaved in eight-row bands. The
next four-row batch often dirties and copies the same pages again.

The new manager retains the **maximum four STEP rows per poll**. While pasting,
it stops a batch at a physical eight-row band boundary and commits there, or at
completion/error. Intermediate partial bands remain dirty in the shadow until
that boundary. No state or bitmap allocation is added. The last successful
STEP's `$F780` offset supplies the row's low three bits; there is no intervening
gateway/callback before reading it, and installed IRQ/NMI paths do not use it.
Capture, ticket reconstruction, source/destination locks and invalidation stay
unchanged. Each row still releases its MMU/runtime/IRQ lease independently.

The final partial band must be flushed, including nonaligned window origins.
Host tests cover all eight Y alignments and retain the earlier creation,
incomplete capture, move, resize, oversize, content, destruction/reuse and reset
checks. Manager CODE grows 32 bytes (7,645→7,677); RODATA130/HIGHBSS88 stay fixed,
transport377 is unchanged, and127 resident padding bytes remain. All normal/
panic segments, UAPP runtime assertions, helper sets and shadow placement remain
exact. No stack, cache capacity, public ABI or module checksum is changed.

## Read-only timing comparison

The native 1986 harness puts instruction breakpoints at the real
`udeks_vic_bitmap_commit_page` entry and its hardware-stack-derived return.
It counts pages, unique pages and elapsed 8502 cycles, including intervening
IRQ/NMI work. It resumes the **same partial machine frame** after every stop.
No OS code/state/device/input queue is patched by the profiler. Mouse/key
stimuli are the existing native 1351/keyboard sequence. These measurements are
emulator timing, not physical-C128 measurements or theoretical instruction sums.

Both D71 and D64 produce the same native comparison across16 moves:

| PAL sample | Four-row commits | Band-boundary commits |
| --- | ---: | ---: |
| Median pasted-stage page copies | 56 | 22.5 |
| Median pasted-stage page-copy cycles | 709,451.5 | 288,659.5 |
| Median settled-paste frames | 156.5 | 129.5 |
| Median release + settled-paste frames | 220 | 194.5 |
| Sampled Ctrl+C-to-idle frames | 211 | 156 |
| Worst settled-paste frames, including clock repair | 164 | 313 |

The median paste stage is17.3% shorter, page copies fall59.8%, and median
release-to-settled presentation improves11.6% (about4.40→3.89s at50Hz). The
background repair stage itself has not been optimized. The slower313-frame
sample is retained, not excluded from the medians or hidden behind a primitive
speedup. Its clock-paint counter identifies a coincident minute update: the
lower-window repair plus another cached presentation are still expensive.
Therefore this is **not a worst-case latency improvement** and does not accept
issue #6's responsiveness gate. Next work is visible-damage/occlusion-aware
background/clock repair, with the same input/pixel/ownership gates.

## Shutdown bug exposed by changed timing

An initial tiled run completed every move correctly but lost keyboard release
sampling after `xinit -q`. The preserved failure has raster IRQ target482,
sampler phase1, an OS matrix still holding Return, and a physically released
Return key. The CPU/scheduler continued; this was not a Z80 lease hang.

`VIC_CONTROL_1` (`$D011`) reads bit7 from the **current raster**, but writes it
into the **raster-compare target**. See the Commodore-authored
[C128 Programmer's Reference Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf),
VIC raster/control-register description. The shutdown read/modify/write used
`AND #$CF`; at a late PAL raster this turned sample target226 into482, beyond
the312-line frame, so the sampler never completed and keyboard arbitration
remained blocked. The fix is `AND #$4F`: preserve scroll/ECM while clearing
bitmap/display-enable and the read-back raster high bit. The service owns
low (<256) raster targets200/226.

This changes **one immediate byte** at `$2328`, with zero layout/size growth.
Both comparison variants include the fix. The new tiled run shuts down at
line295 and retains target226, then types and restarts successfully; the
reference shuts down at238 with target200. Source tests cover both raster-high
values, and an archive test verifies the failed versus fixed resident kernel
differs only in `$CF→$4F`. The normal build also receives this correctness fix;
normal cached moves are still not enabled.

## Qualification and preservation

Both native formats retain the live candidate's full17472-pixel checks, all
horizontal alignments, painter/Z80 counter stability, clock, incomplete-paint
fallback, partial-paste Ctrl+C, oversize resize, handle reuse, typed/history/
shutdown/restart, private guards, immutable module/header and NMI pressure.
VICE independently qualifies both variants/formats for capture/full bitmap
equality, gateway/guard, NMI drain/handoff and restart. Native VICE mouse dragging
and physical RESTORE/Z80 routing remain unqualified.

The tiled private cleanparallel rebuild is disk-identical. Separate reference
and tiled archives include all generated providers/maps/bridges/outputs,
disks and bound native/VICE results. The tiled result's `failure/` keeps the
original failed disk/kernel/map/runner/log, a sanitized state record and its
own checksum manifest; it does **not** include the full ROM-bearing snapshot.
Comparison JSON binds the exact reports, native runs and logs for both formats.
Preservation refuses changed inputs/results and existing evidence.

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_repaint.py baseline build
distrobox enter my-distrobox -- python3 tools/window_cache_repaint.py tiled build
distrobox enter my-distrobox -- python3 tools/window_cache_repaint.py baseline 1986
distrobox enter my-distrobox -- python3 tools/window_cache_repaint.py tiled 1986
python3 tools/window_cache_repaint.py baseline vice
python3 tools/window_cache_repaint.py tiled vice
python3 tools/window_cache_repaint.py tiled compare
python3 tools/window_cache_repaint.py baseline preserve
python3 tools/window_cache_repaint.py tiled preserve
```

Tiled image hashes:

- D71: `d1be51f9b17c04af00607c414b7d165ee5630bccd8112c830a92cc8912256317`
- D64: `af502122b2c5b0c5a1f18181b0709b43ae523cf3ba97552a8a643856aeb17b50`

Normal images, changed only by the shutdown correctness fix and its derived
boot checksums, are D71 `d99463d6...` and D64 `65a37c26...`.

Final checks: 787 host tests, archived hashes and Python compilation pass;
normal container `boot`/`all` and `placement-check` pass. No VICE sessions remain.
No commit/push or normal cache promotion was performed in this increment.

User feedback on 2026-09-28: "looks ok" for the presented tiled candidate.
The platform and individual cases were not specified, so physical-C128,
RESTORE/NMI and worst-case responsiveness gates remain open. The next
optimization is visible-damage/occlusion-aware clock/background repair;
this feedback does not promote the cache to the normal images.

The next candidate is now qualified in
[WINDOW-CACHE-OCCLUSION.md](WINDOW-CACHE-OCCLUSION.md): geometry-based hidden,
upper-strip and disjoint repair avoids unnecessary retained-image pastes.
The forced upper-strip clock case drops from 278 to 126 PAL frames, with two
page copies instead of 44 and identical complete canvases. Complex overlap
still uses the fallback, so general worst-case responsiveness remains open.
