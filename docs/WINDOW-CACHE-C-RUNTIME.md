# Private C display-cache runtime proof

Status: **standalone-qualified in 1986 and VICE**, 2026-09-28. The ordinary
boot disks are unchanged; no pixel-cache move path is installed. This follows
the [delivery and policy measurement](WINDOW-CACHE-DELIVERY.md).

The bank-1 module now executes the real C cache-state policy and its private
cc65 helpers. A small ASM dispatcher invokes six bounded operations with the
ordinary compiler calling convention: init, invalidate, capture-begin,
paste-begin, prepare-row and commit-row. Unknown operation selectors are
rejected without dispatch. Marshalled pointers are trusted, compiler-local
bindings—not an untrusted request or a new public ABI.

## Measured layout and cost

| Material | Home / size |
| --- | --- |
| Qualified ASM row core | bank 1 `$4200-$42D4`, 213 bytes |
| ASM C dispatcher | bank 1 `$42D5-$434A`, 118 bytes |
| C policy and helpers | bank 1 `$434B-$4C7C`, 1,828 + 526 bytes |
| Caller-owned lease / geometry / row | bank 1 `$4CD0-$4CEB`, 13 / 6 / 9 bytes |
| Private C software stack | bank 1 `$4D00-$4DEF`, top `$4DF0` |
| Packed image | bank 1 `$4E00-$5BFF`, 3,584-byte capacity |
| Copied C gateway | common `$F68A-$F6C4`, 59 bytes |
| C resident binding, including gateway source | 83 CODE, zero BSS |
| Existing row resident binding, including gateway source | 194 CODE, zero BSS |

Total linked module code is **2,685 bytes**. Code ends 83 bytes before the
fixed private state; another 20 bytes after the state are guard padding in
this experiment. Both bindings total **277 bytes**, leaving **239 of the
516-byte resident reserve** before marshalling, delivery validation,
completion/generation handling and window-manager continuations. The full
production link is not yet proven to fit. None of the uploader, diagnostic
IRQ code or embedded bank-0 module copy belongs in that budget or production.

These remain candidate graphics-service allocations, not frozen placements.
The module's real cc65 record sizes are compiled and measured. Link assertions
pin all twelve published runtime addresses; both caller and module allocate
the same `$06-$1F` zero-page runtime. No resident or shell stack is reduced.

## Calling and serialization

The C binding installs its gateway on **every call**, invalidating the shared
outline tag. The gateway captures P before SEI/CLD, saves all 26 cc65 runtime
bytes on the hardware stack, selects worker-flat, establishes the private C
stack, and invokes the dispatcher. It records the returned software SP, maps
kernel I/O, restores the runtime bytes and caller I/D state, then returns.

The caller uses the real bank-0 `$EFF0` stack top. The shell-stack address
range in bank 1 (`$E700-$EFFF`) is independently seeded and verified byte for
byte; it is not borrowed by the module. Hardware-stack balance/bottom guard,
caller-stack bottom/top guards, private-stack guards, state/image boundary
guards, and all four caller I/D combinations are checked.

There is no callback, task switch or poll during a C operation or row blit.
Each return restores kernel I/O so cooperative work can run between steps.
This experiment calls the real row binding after prepare-row and only then
acknowledges the row. C calls and row transfers replace each other's common
gateway safely by reinstallation; no stale copied code is reused.

## Evidence

Two positive programs pass an independent oracle for all 8,000 shadow bytes
and 32 logical dirty flags in both emulators:

- 66 alignment/edge images, 132 row transfers and 547 dispatcher calls;
- one complete 168×104 image, 208 row transfers and 439 dispatcher calls, pasted after
  replacing the entire source background;
- eligibility, owner, capacity, geometry, partial-image, generation-wrap,
  cancellation and stale/duplicate acknowledgement rejection;
- unchanged synthetic command/console/service bytes outside the display-owned
  outline tag, and intact private/caller/shell memory guards;
- active CIA1 IRQs, exact 32-bit interrupt counts, and no IRQ seeing a
  non-kernel memory profile.

Each program includes one rejected operation selector, so the actual C
function invocation totals are 546/438. The record's `policy_calls` field
counts all dispatcher entries, including that rejection.

The lowest **observed changed byte** in the private stack is `$4DDE` (an
18-byte changed extent below `$4DF0`). This is not an instrumented minimum SP
or a worst-case stack-depth guarantee; the low 64 bytes and upper 16-byte
guard are separately verified. Do not shrink the 240-byte stack from this
observation.

Three single-byte changes in the **live** C gateway are deliberately tested:
remove SEI, shift zero-page restoration by one address, or select `$EFF0`
instead of `$4DF0` for the worker C stack. Both emulators detect the respective
IRQ-map, runtime-restoration and shell-stack failures, and the normal decoder
rejects all three even though their pixels remain correct. The diagnostic
wrapper repairs the zero-page corruption **after recording it** so the fault
can be decoded; no such repair exists in the candidate binding.

Exact sources, linked outputs, PRGs, maps, compiler/emulator identities,
run-to-program hashes and records are preserved in
`bench/{artifacts,results}/2026-09-28-window-cache-c-runtime`. No ROM images
or complete emulator snapshots are stored.

## Remaining gates

This is not a GUI timing claim: display is off and the diagnostic guard scans
and publication dominate runtime. Live input, actual service/task/Z80 leases,
NMI handling and physical hardware remain unqualified. IRQ masking does not
protect against NMI, so that ownership/deferral gate must precede production
acceptance. The complete capture source must stay stable across its rows.

Next: measure a versioned completed-image notification and the C window-service
marshalling/continuation cost, preserve all existing UAPP vectors (the table
ends at `$CFFF`), and qualify production delivery/validation and NMI handling.
Only explicitly complete, topmost and unoccluded images may be captured.
Painting, resize, closure, shutdown and ownership changes invalidate the lease.
Oversized or ineligible windows retain redraw; 220×160 needs 4,480 bytes and
does not fit this candidate's 3,584-byte image area.

Reproduce from the repository root:

```sh
distrobox enter my-distrobox -- python3 tools/window_cache_c_runtime.py build
distrobox enter my-distrobox -- python3 tools/window_cache_c_runtime.py run --engine 1986
python3 tools/window_cache_c_runtime.py run --engine vice
python3 tools/window_cache_c_runtime.py decode
```

The tools raw-load their standalone PRGs and close their own VICE sessions.
`preserve` refuses to overwrite existing evidence. Work stays under
`build/bench/window-cache-c-runtime*`; production outputs are not patched.
