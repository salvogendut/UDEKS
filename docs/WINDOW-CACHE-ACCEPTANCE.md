# Cache acceptance and persistent continuation seam — 2026-09-28

Status: isolated machine-code diagnostic qualified in VICE 3.10 and 1986.
Normal boot disks are unchanged. No compositor hooks or cached GUI moves are
enabled; this is not a new hardware or drag-performance qualification.

## Before the first C call

Trusted resident code installs a separate 79-byte common validator at `$F68A`.
It does not execute the unvalidated bank-1 module to validate itself. Each poll
compares all 16 VCC2 identity bytes and sums at most one 256-byte code page.
The complete 3,977-byte module requires 16 polls; the final page is 137 bytes.
The identity fixes version, length, checksum, entry, dispatcher and capacity.
Only the exact expected identity and complete 16-bit additive sum admit INIT.
Failure latches disabled; guarded commands return `$FF` without entering C.
The sum detects the qualified single-byte corruption, not malicious or
compensating changes. This is an integrity/layout check, not authentication.

The initial check precedes row-core self-modification. It is not a checksum of
the mutable module after drawing, nor permission for future unvalidated loads.
No app callback, ZP allocation, software stack or C helper runs in validation.
Caller I/D state is preserved. IRQs are masked for each bounded bank lease;
the exact installed NMI stub can still record an event without changing banks.
A pending event is drained under kernel I/O after the gateway copy and before
the worker lease. This prevents copy-time pending events from suppressing all
worker NMI observations. Those two new JSRs are charged below. The diagnostic
CIA2 period is 768 cycles rather than phase-locked to the 512-cycle CIA1 IRQ.
These timer values are stress instrumentation, not production settings.

## State between polls

Five explicit writable resident CODE bytes hold acceptance state, a 16-bit
checksum/ticket, window owner and phase. They borrow no BSS, ZP or guard space.
The ticket bytes hold the partial sum before acceptance, then the original
content-generation ticket. Successful commands snapshot the returned ticket,
owner and phase while IRQs remain masked; rejected commands do not replace
them. STEP reconstructs the original ticket/owner before calling the controller.

The test replaces the common gateway between validation pages and overwrites
its page/sum parameters. During drawing it poisons the common ticket, owner and
phase before every STEP. Full independent pixel/dirty oracles still pass,
including capture followed by two pastes after the source bitmap is destroyed.
This proves the seam does not depend on common workspace surviving a poll.
It does not yet prove window-manager invalidation/serialization behavior.

## Footprint gate

| Resident material | Bytes |
| --- | ---: |
| Raw C gateway source/copy plus pre-worker drain | 244 |
| Acceptance, guard, STEP marshal, five state bytes and validator source | 309 |
| Total | 553 |
| Available qualified padding | 502 |
| Shortfall before any compositor hooks | 51 |

The 79-byte validator source is included in 309, not an extra allocation.
The existing NMI drain implementation is already installed and charged to the
normal image. All three measured objects have zero BSS and zero ZP.
This closure cannot be installed within the current budget. No fit claim,
shadow relocation, live-memory borrowing or production linker change is made.

## Qualification and reproduction

Both emulators pass all eight exact PRGs: two success geometries, one payload
byte corruption, one header-major corruption, and real single-byte faults in
SEI, ZP restore, private stack selection and NMI pending recording.

Success records verify 132 rows/480 commands/66 images and 312 rows/337
commands/two images. Four extra commands are deliberately blocked before
acceptance. Bad payload/header cases are rejected after 16/one validation
polls, with six blocked commands, no row or pixel changes, all 26 private
state bytes still `$6D`, and the entire unused private stack still seeded.
Poll counts and resident ticket/phase are checked by the compiled probe; any
failed assertion sets the raw semantic-failure byte and fails decoding.

Positive NMI totals equal deferred drains exactly: 1986 12,104 (302 worker)
and 20,749 (159 worker); VICE 12,034 (273 worker) and 20,757 (237 worker).
All 26 cc65 ZP bytes, I/D modes, hardware/software stacks, MMU and guards pass.
The four runtime faults fail the positive oracle and trigger only their
expected diagnostics; the pixel oracle remains exact. Lowest observed private
stack offset is `$CC`, not a maximum-depth proof. The standalone observer/IRQ
at `$FF20`/`$FF80` are not production allocations. Physical RESTORE/Z80 routing
still needs its separate hardware gate.

The extended diagnostic seed/scanner no longer uses a signed descending-X
copy loop: its added state checks crossed the old 128-byte limit. The final
unsigned bounded loops are preserved and checked by host tests.

Exact sources, generated assembly, maps, original/mutated PRGs, provenance,
build-report hash and raw records are preserved under
`bench/{artifacts,results}/2026-09-28-window-cache-acceptance`.
Preserve rechecks all hashes/decoders and refuses overwrite.

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_acceptance.py build
distrobox enter my-distrobox -- python3 tools/window_cache_acceptance.py run --engine 1986
python3 tools/window_cache_acceptance.py run --engine vice
python3 tools/window_cache_acceptance.py preserve
```

Next: recover resident bytes through measured private implementation savings,
then link acceptance plus all real compositor hooks/locks. Freeze capture and
paste geometry through READY, cancel early drags, invalidate stale ownership
before content/overlap/resize/restack/close/shutdown changes, and preserve
ordinary redraw fallback. Full normal/panic placement and live GUI/input/task/
Z80/cancellation/pixel gates must pass before enabling pixel-cached moves.
