# Window-manager continuation budget — 2026-09-28

Status: behavior-preserving C savings are installed; the cache continuation
is host-tested and sized, but **not production-linked**. Moves still replay.

## Installed savings

The reference compiler already optimizes private calls: annotating them
fastcall produces no saving. Public calling conventions were not changed.
Three simpler C changes do help:

| Change | CODE bytes saved |
| --- | ---: |
| Startup invokes existing reset logic | 58 |
| Chrome reuses local x/y/width/height | 145 |
| Damage intersection computes right/bottom once | 18 |
| Total | 221 |

The manager drops from 7,900 to **7,679 CODE**, with unchanged 130 RODATA and
88 HIGHBSS bytes. No new library helpers or persistent state. Host tests
compare the **complete drawing/state trace**, not just a checksum, against
the previous C manager over min/max widths, title clipping, flags, overlapping
windows, paints, move/resize/close routing, reset and repeated lifecycle use.

The 221 bytes increase shared padding from 59 to 280, making **502 total
available padding**. All primary segment bounds, runtime zero page, common
gateways and scheduler owners remain unchanged. Actual-link tests verify
normal/panic parity and unchanged module footprints except the manager and
the compensating transport padding. The audit rejects manager-size drift.

Both formats pass native input/history, mouse dragging, foreground Ctrl+C,
background-clock survival, explicit image completion, RESTORE and sustained
CIA2 NMI stress. VICE passes both-format boot/clock/Z80 wave/completion/NMI
gates. The independent layout run verifies shadow clear, scheduler install,
tail preservation and bank-0/bank-1 bitmap equality. These are correctness
gates, not a new drag-speed claim.

Evidence: `bench/{artifacts,results}/2026-09-28-window-manager-integration`
and `bench/results/2026-09-28-window-manager-integration-layout`.

## C continuation prototype

`move_cache_flow.c` models capture, repeated paste, cancellation and one-row
continuations over the existing combined C command. Its caller-owned record
is four bytes: generation, window handle and phase. Cache owners are **window
handles**, not task/app ids. Every STEP validates the content-generation ticket
before touching the shared request, performs at most one row and returns.
This ticket is not a new per-paste transaction id: same-generation repeated
pastes are intentional, and calls must remain serialized by the manager.

Invalidation clears backend ownership before handle reuse or generation wrap;
zero generations are skipped. Unexpected phase/WRITTEN tags or backend errors
invalidate the flow so the caller can redraw. Tests link the actual flow,
command and policy C modules and cover stale/wrong tickets, bounded rows,
multiple pastes, cancellation in progress, wrap, invalid geometry and all
unexpected byte-valued response tags in both active phases.

The prototype does **not** implement compositor locks, hook installation,
delivery validation or manager polling. Capture still requires explicit image
completion and an immutable source until READY. Paste needs a stable destination.
Real integration must invalidate before damage, repaint, resize, restacking,
destroy/reuse or graphics shutdown. It must handle callbacks and cancellation
between rows without copying a partial/obscured image or reviving dead handles.

The reference cc65 optimizer crashed on the original variable-mask STEP-result
comparison. Explicit scalar comparisons compile with full `-Oirs`; exhaustive
host response tests cover the replacement. No compiler settings were weakened.

## Real bank-0 shortfall

An isolated link spends all 502 available bytes, adds the exact qualified
241-byte binding, the compiled flow and its actual four-byte state record,
and resolves against real normal resident providers. **Every split linker
output is retargeted**; this image is deliberately unbootable and never packaged.

| Candidate cost | Bytes |
| --- | ---: |
| Flow CODE | 992 |
| Flow RODATA | 4 |
| Caller-owned flow state | 4 |
| Combined command binding | 241 |
| Total | 1,241 |
| Available | 502 |
| Still short | **739** |

No extra library module is pulled in. The map independently confirms the
739-byte shadow displacement. This is a **lower bound**, since real manager
hooks, source/destination locking and delivery validation are absent.
The binding alone would leave 261; that is not a fit claim for the controller.
Do not install this experimental image or move the frozen shadow to hide the
shortfall. Packaging/scheduler gaps, app slots and stack guards are not free.

Sizing inputs, objects, listings, real provider hashes, isolated link/map and
all outputs are preserved under
`bench/artifacts/2026-09-28-window-manager-budget`.

```sh
distrobox enter my-distrobox -- python3 tools/window_manager_budget.py build
python3 tools/nmi_integration_probe.py build \
  --checkpoint 2026-09-28-window-manager-integration --work build/window-manager-integration
distrobox enter my-distrobox -- python3 tools/nmi_integration_probe.py 1986 \
  --checkpoint 2026-09-28-window-manager-integration --work build/window-manager-integration
python3 tools/nmi_integration_probe.py vice \
  --checkpoint 2026-09-28-window-manager-integration --work build/window-manager-integration
```

The preserved sizing checkpoint binds its original normal providers; replaying
it against later providers is a new measurement, not the same exact input set.

## Next

The subsequent direct in-bank controller now fits and passes standalone
pixel/dirty/stack/ZP/I/D/IRQ/NMI/fault-control proofs in both emulators. Its
single-owner C specialization, full helper closure, guarded 240-byte stack
and default packed-image budget are recorded in
[WINDOW-CACHE-CONTROLLER.md](WINDOW-CACHE-CONTROLLER.md).

Next is complete normal/panic delivery and bounded compositor integration
within the remaining resident budget, then live cached-drag gates. No layout
is production-frozen by the standalone proof, no pixel-cache move is enabled,
and no new manual test is needed for this checkpoint.
