# Compact validated cache transport — 2026-09-28

Status: standalone machine-code proof in VICE 3.10 and 1986. Normal disks and
their resident links are unchanged. No pixel-cached GUI dragging is enabled.

## Footprint recovered

The [acceptance seam](WINDOW-CACHE-ACCEPTANCE.md) needed 553 resident bytes,
51 more than the aggregate qualified padding. The new transport needs **371**,
saving **182**, with **131 remaining before real compositor hooks**.

| Charged resident material | Bytes |
| --- | ---: |
| Bank-1 source loader, installer, drain and diagnostic call | 51 |
| Unchanged acceptance/guard/ticket seam, including validator and five state bytes | 309 |
| Diagnostic post-copy patch helper | 11 |
| Total | 371 |

Even the test-only helper and its call remain charged. This is an aggregate
byte budget, not a completed normal/panic linker placement or integration fit.
No public ABI, shadow, app slot, scheduler reservation, stack, guard or image
capacity is reduced or borrowed.

## Bank-1 module and trusted transport

The initially validated module now includes its own immutable gateway source:
196 bytes at `$5146–$5209`. Total module size is 4,106 bytes, with six spare
bytes before VCC2 identity at `$5210`. The row core remains byte-identical,
dispatcher remains `$42D5`, private state remains `$5220–$5239`, stack remains
240 bytes at `$5250–$533F`, and packed image remains 2,224 bytes at `$5350`.

Acceptance validates all module bytes, including the gateway source, before
entering C or calling the banked source loader. There are now **17** bounded
validation polls: 16 full pages and ten bytes. The test generator and page
arithmetic derive this from the actual size and also handle exact multiples
of 256 correctly. An additive checksum is not authentication.

The trusted resident raw wrapper copies a 20-byte loader to `$F75A–$F76D`.
That loader selects worker-flat RAM, copies the accepted source to `$F68A`,
and restores kernel I/O before returning. The 196-byte gateway ends at `$F74D`,
so it does not overwrite the executing loader or reach parameters at `$F780`.
Copying is serialized under the resident guard. The source is never modified
by row-core self-modification and is not stored in an application slot.

The outer guard owns status/IRQ preservation, so the copied command gateway
does not duplicate PHP/SEI/PLP. It still CLDs before compiled C, preserves all
26 cc65 ZP bytes, restores kernel mapping and returns through the outer guard.
MMU preset strobes do not require loading zero before each write. Dirty-page
marking computes the logical last offset directly, including both carries in
`OFFSET + (RAWCOUNT-1)*8`, rather than reconstructing it from a physical address.
Independent pixel/dirty oracles qualify those instruction changes; host tests
check the carry formula over every low-byte offset and row count 1–40.

## C remains the policy implementation

The private fixed-flow specialization removes redundant copies of the shared
geometry record onto itself, reducing flow CODE from 637 to 570 bytes. Capture
and paste now require the actual shared request address; a separate record,
even with identical values, is rejected before any mutation. The real C
dispatcher already supplies that address. Host tests check rejection leaves
flow, lease, row, request and row count unchanged, plus capture/two-paste,
stale work, cancellation and generation-wrap behavior.

The generic C flow and all production C sources are unchanged. This specialized
source is generated only for the isolated module. Policy, eligibility, geometry
validation, ownership and continuation remain C; assembler handles transport.

## Qualification

Both emulators pass all eight exact PRGs and the complete independent
8,000-pixel/32-dirty-byte oracles: alignment 132 rows/480 commands/66 images;
capture plus two pastes after destroying the source 312 rows/337 commands/two
images. Deliberately overwritten common workspace does not lose the resident
original ticket. Bad payload/header rejects after 17/one polls without C state,
stack or pixel writes. I/D, ZP, MMU, caller/worker/USH/hardware stacks and guards
pass. Private stack low-water remains `$CC`, not a maximum-depth proof.

Positive NMI totals equal drains: 1986 11,981 (475 worker) / 20,762 (338 worker);
VICE 11,937 (483 worker) / 20,647 (339 worker). These include worker-copy leases
and are stress coverage, not timing/performance results. Physical RESTORE/Z80
NMI routing retains its separate hardware gate.

Four one-byte faults still expose interrupt masking, ZP restoration, live USH
stack corruption and missing pending-NMI recording. Since the gateway is now
part of the checksummed module, ZP/stack faults are injected into the copied
gateway **after** acceptance through the test helper. Its baseline stores the
original bytes; changing one immediate induces the actual restore/stack bug.
The initial checksum is not weakened or bypassed. The dropped-SEI fault permits
an intentional interrupt race, so its NMI accounting is not a positive gate.
All four fail the positive decoder and retain the exact pixel oracle.

Exact inputs, generated C/assembly, linked maps, original/mutated programs,
build-report/program hashes, emulator provenance and raw records are in
`bench/{artifacts,results}/2026-09-28-window-cache-compact`.

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_compact.py build
distrobox enter my-distrobox -- python3 tools/window_cache_compact.py run --engine 1986
python3 tools/window_cache_compact.py run --engine vice
python3 tools/window_cache_compact.py preserve
```

Follow-up: this module's cold-boot/lifetime delivery and isolated normal/panic
**transport-only** placement now pass; see
[WINDOW-CACHE-COMPACT-DELIVERY.md](WINDOW-CACHE-COMPACT-DELIVERY.md).
Next: link and measure the complete normal/panic resident hooks,
then qualify live compositor invalidation, bounded capture/paste, input,
cancellation, overlap, resize/restack/close and pixel behavior. Keep ordinary
redraw fallback and cached GUI moves disabled until that full path passes.
