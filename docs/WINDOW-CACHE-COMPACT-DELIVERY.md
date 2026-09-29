# Compact cache delivery and resident placement — 2026-09-28

Status: revised module delivery passes in VICE 3.10 and 1986, D71 and D64.
The transport also fits isolated normal/panic resident links. These are two
separate gates: **no live compositor hooks or cached GUI moves are enabled**.
Normal boot images and providers are unchanged. There is no new manual test.

This document records that earlier checkpoint. A later
[live compositor candidate](WINDOW-CACHE-LIVE.md) now supplies separate manual
test disks with regenerated bridges and actual cached moves.

## Revised module delivery

The delivered module is exactly the [compact transport](WINDOW-CACHE-COMPACT.md)
proof's 4,106 bytes at `$4200–$5209`, including the immutable 196-byte gateway
source at `$5146`. Six zero bytes and the complete VCC2 header at `$5210`
are checked as part of the 4,128-byte captured slot. This is not the earlier
3,977-byte controller, which did not contain that source.

The existing isolated delivery recipe accepts an explicitly qualified module
path; it must be listed in the verified artifact manifest. The wrapper also
checks the exact gateway suffix, module map and proof hashes. Scheduler source
remains relocated to `$6000`; installed destinations, payload endpoint `$7229`
and existing installer lengths remain unchanged. Strict byte-delta checks admit
only the previously qualified source operands and derived checksum operands.
No resident delivery bytes are added, and the module is not invoked.

VICE captures match at boot, xinit, clock launch, wave launch/completion,
console utilities, graphics shutdown and restart on both formats. Both native
1986 runs preserve the slot through 32 wave drags while the clock runs, followed
by wave cancellation and a console command. This proves delivery/lifetime,
not active cache responsiveness or performance. All full-slot captures, logs,
emulator provenance and report/disk/run hashes are preserved in
`bench/{artifacts,results}/2026-09-28-window-cache-compact-delivery`.

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_compact_delivery.py build
python3 tools/window_cache_compact_delivery.py vice
distrobox enter my-distrobox -- python3 tools/window_cache_compact_delivery.py 1986
python3 tools/window_cache_compact_delivery.py preserve
```

## Real resident transport placement

`tools/window_cache_resident_link.py` replays both actual resident link recipes
in isolation, replacing only the graphics padding object and adding the
qualified raw wrapper, acceptance/guard/ticket seam and diagnostic helper.
All split linker outputs are redirected, not just the main binary.

| Charged CODE | Bytes |
| --- | ---: |
| Raw wrapper / banked source loader | 51 |
| Acceptance, guard, persistent ticket and embedded validator | 309 |
| Retained diagnostic helper | 11 |
| Total | 371 |

Padding spends 49 scratch + 42 primitives + 280 shared bytes, leaving 131
primitives bytes. These reservations are ordinary sequential CODE, not three
independently fixed-address memory banks; moving the charged closure within
that CODE section is linkable. The separate eight-byte outline reserve is
untouched. Five writable state bytes are charged within the acceptance CODE;
no new BSS, ZP, DATA, RODATA or runtime helper is needed.

Every segment matches its normal/panic baseline, including BSS, low/high state,
module/common gates, syscall addresses and the exact 8,000-byte shadow at
`$A1E0–$C11F`. Link-time UAPP ZP assertions also pass. The complete helper module
sets and sizes match. Normal providers and outputs are hashed before/after.

This is a **transport-only placement proof**, not a full compositor fit. The
131 bytes are now real residual padding in those isolated links, but no hook
or C adapter is yet charged. Experimental binaries are **not bootable**: private
providers moved, so their derived import bridges would need regeneration.
Do not package or execute these binaries. Exact objects, generated inputs,
normal/panic maps and split outputs are preserved in
`bench/artifacts/2026-09-28-window-cache-resident-link`.

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_resident_link.py build
python3 tools/window_cache_resident_link.py preserve
```

## Next gate

Measure the real compositor adapter and hooks before packaging an integrated
disk. Capture source and paste destination must stay frozen until READY;
early dragging must cancel incomplete capture and use ordinary redraw.
Invalidate before content changes, overlap, resize, restack, destruction/reuse,
shutdown and cancellation, but retain READY pixels through their own move's
background repair. Preserve original tickets across shared-workspace reuse.
Keep bounded row leases and fallback. Qualify live input/tasks/Z80/Ctrl+C,
completion/invalidation, overlap and pixels before enabling cached GUI moves.
Physical RESTORE/Z80 NMI routing still has its separate hardware gate.
