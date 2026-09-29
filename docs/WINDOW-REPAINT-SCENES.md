# Private value-prefix repaint frontend

Issue #14, 2026-09-29. This advances the private frontend sizing experiment;
**it is not installed in the manager, a new test disk, or a latency qualification.**
Normal boot images and public application ABI are unchanged.

## Code recovery and ownership

Auditing the four potential legacy helper retirements confirmed live drag,
cache, overlap and callback users. None of their 722 bytes is reclaimed here.
Instead, the resident poll copies only the window's first eight value bytes
(flags, x, y, width, height, rank). The banked C decoder validates geometry and
derives sparse handles, visible views and bounds there. Titles and callbacks
are beyond the copied prefix. Four temporary nine-byte views occupy the
existing private C stack, die before return, and are never retained by policy.
No new persistent manager or bank allocation is introduced.

The private packet remains 82 bytes with unchanged receipt/work offsets.
Prototype 0.2 uses marker `$84` instead of the old view count and requires four
zero reserved bytes. Both old and new PEEK decoders reject the other's format.
This is a private build binding, not a public ABI. Compiler-emitted 13-byte
layout sidecars verify the actual cc65 manager prefix and wire offsets before
qualification; intentional prefix/packet shifts must fail the exact match.
Host layout assertions use an explicitly packed 16-bit prefix, not native host
pointer sizes as a claim about target layout.

Malformed visible geometry, format or reserved bytes is rejected before lane
progress changes. The RPC result/snapshot can change on rejection, but lane,
pixels, dirty state and clip cannot. Free/hidden slots are skipped. This is a
trusted manager table: uniqueness of live ranks is the manager's precondition,
not a new untrusted-client parser. The new poll still copies returned work into
caller-local storage before receipts/raster reuse common scratch.

## Measured complete closures

| Item | Previous | This checkpoint |
| --- | ---: | ---: |
| Resident poll CODE | 440 | 212 |
| Component CODE, including receipt/binding/new helpers | 2,599 | 2,371 |
| Minimum shortfall against 2,113 allowance | 486 | 258 |
| Full normal/panic sizing-link CODE growth | 1,240 | 1,012 |
| Bank code plus all linked helpers | 3,286 | 3,720 |

The resident saving is 228 bytes. Gate/control remain 48/98 bytes; manager
CODE is 8,491, HIGHBSS 88, new linked resident helpers 72. All fixed segments,
whole HIGHBSS (298), and RODATA/DATA/BSS/shadow sizes are unchanged. Legacy
composition remains for conservative sizing. Those whole-link images move the
shadow and retain stale bridges: **unbootable, never package them.**

Bank entry 3 + lane 2,641 + dispatcher 564 + complete helper closure 512 =
3,720 bytes, `$D100-$DF87`. There are 88 code bytes before the fixed 18-byte
state at `$DFE0-$DFF1`; its 14-byte guard remains intact. Published runtime
zero-page bytes are the existing 26-byte saved/restored set, not new allocation.
The decoder's 36 local view bytes are explicitly charged to the existing
240-byte private stack. The lowest changed offset observed is 169 (previous
211); this is **observed coverage, not a worst-case stack bound**.

The remaining 258 is only a lower bound: real call sites, delivery, admission,
paint-lease storage, NMI cleanup, providers, busy and teardown costs are still
additional. Code-space fit alone does not establish serialization or NMI safety.

## Qualification and evidence

Host tests exercise the real table, new frontend/decoder, lane and compact
backend with modeled clients/page copy: overlapping old-reference canvases,
sparse ranks/high x, bounded one-step drawing, repeated delegated receipts,
packet overwrite after local copy, atomic resource deferrals, malformed-format
and geometry rejection, poisoned pointers and retirement fences. CLIENT stays
delegated and unacknowledged; no old whole painter is invoked or retained flag
admitted. Existing gate/control lifetime rules remain in
[WINDOW-REPAINT-FRONTEND.md](WINDOW-REPAINT-FRONTEND.md).

The standalone native program runs the actual new poll and banked C decoder
with real C/ASM shadow drawing, private stack and transport. Both 1986 and VICE
pass eight scenes and four malformed protocol cases. The exact final 8,000
bytes match the old-window oracle, SHA-256
`8efa40f4c55d395b9681363a2d872a625ea5a36532cad5a38b6d3ecc266423c7`.
Both record stack offset 169 and unchanged runtime/guard checks; IRQ arrivals
are 440,821 (1986) and 439,734 (VICE). The 12,767 PAL diagnostic frames include
heavy full-image/guard scans: this is **not renderer speed or input latency**.

The native client/page-copy and graphics/cache-admission functions remain
models; lease value 1 is asserted, not an implemented lock. No live OS apps,
task paging, Z80, physical hardware, NMI/RESTORE or production delivery is
qualified. Earlier transport fault controls retain only their previous scope;
they were not re-run in this checkpoint.

Exact sources, compiler/library/providers, split links, layout controls, native
PRG, emulator provenance and hash-bound results are preserved under
`bench/{artifacts,results}/2026-09-29-repaint-scenes`. Input/output drift is
checked before and after runs; immutable preservation refuses overwrite.

Reference-container build and 1986 run; Flatpak VICE run on host:

```
make repaint-scenes
python3 tools/window_repaint_scenes.py run --engine 1986
python3 tools/window_repaint_scenes.py run --engine vice
python3 tools/window_repaint_scenes.py preserve
```

## Next gate

Recover the remaining resident deficit with measured real call-site/provider
costs. Keep legacy helpers until their actual users migrate. Do not annex
private-stack guards, common gateway/app-stack overlap, bootfs or runtime state
to claim fit. Then qualify checksummed delivery/admission and serialized
gateway/private-stack ownership with NMI drainage in the restored kernel map.
Only after live poll/providers/interlocks pass can a visible test disk follow.
This remains window-manager work; xwave-specific optimizations are separate.
