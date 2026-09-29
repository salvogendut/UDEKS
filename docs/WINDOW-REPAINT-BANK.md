# Private banked repaint placement proof

Issue #14, 2026-09-29. This is a **standalone experiment**, not an installed
service, boot-delivery qualification, input-latency improvement or public ABI.
Normal disks and the frozen resident layout are unchanged.

## Measured placement and ownership

The pure-C lane, a value-only dispatcher and **all linked cc65 helpers** fit in
3,286 bytes. Unlike the preceding object-size lower bound, this measurement is a
self-contained link with its exact `none.lib` preserved. No resident imports or
cross-bank C pointers are used.

| Bank / range | Ownership and lifetime |
| --- | --- |
| Bank 1 `$A000-$D0FF` | Existing bootfs reservation; never a source of spare bytes. |
| Bank 1 `$D100-$DDD5` | Proposed service code, reachable only in worker-flat `$7F`. |
| Bank 1 `$DDD6-$DFDF` | 522 unused code-budget bytes, not claimed by other work. |
| Bank 1 `$DFE0-$DFF1` | Explicit 18-byte service-owned lane, persistent between calls. |
| Bank 1 `$DFF2-$DFFF` | Fourteen-byte upper guard; not state or code. |
| Bank 1 `$5220-$5239` | Existing cache state, preserved by this experiment. |
| Bank 1 `$523A-$524F` | Existing 22-byte lower stack guard, preserved. |
| Bank 1 `$5250-$533F` | Existing 240-byte private C stack, **serialized reuse**, not a second allocation. |
| Bank 1 `$5340-$534F` | Existing 16-byte upper stack guard, preserved. |
| Bank 1 `$5350-$5BFF` | Existing retained-image storage, preserved. |
| Bank 1 `$E700-$EFFF` | Existing shell stack reservation, preserved; never the service stack. |
| Common `$F68A-$F6C4` | 59-byte copied gateway during this call only; replaces other serialized graphics gateways. |
| Common `$F780-$F7D1` | 82-byte value packet during the same lease only. |
| Common `$F7D2-$F7D3` | Two-byte diagnostic returned-software-SP observation. |
| Common `$F7F0-$F7FF` | Existing transient stack top/guard, untouched. |

The code/state region beneath I/O is a **candidate reservation**. Source inspection
and the neighboring-limit checks support this experiment; production ownership,
loading and admission still need to be made explicit. The broad VIC reservation
is not treated as generally free: sprite templates `$4100/$4140`, cache module
`$4200`, screen `$5C00`, bitmap `$6000`, sprite `$7FC0`, task backup `$8000` and
shell `$9000` remain owned. The experiment does not change Z80 placement, MMU
profiles, relocated page ownership, the bank-0 shadow, or any public UAPP entry.

## Lease and value transport

The packet contains operation/count/completion/result (4), damage (6), receipt
(6), four validated manager views (36), returned work (12), and a diagnostic
state snapshot (18). The snapshot is **not authority** or another persistent job.
No title, callback, app address or cache pointer crosses the bank boundary.
The source header remains a private bench protocol.

The measured binding costs **84 resident CODE bytes including the gateway
image**. It masks IRQs from gateway installation through restoration. The common
gateway saves all 26 published cc65 zero-page bytes on the active hardware stack,
normalizes decimal mode, selects worker-flat, sets the private software stack,
calls `$D100`, records returned SP, selects kernel-I/O, restores zero page and
the caller's I/D flags, then returns status. The private stack must be idle;
there are no nested cache calls, scheduler calls, callbacks, polls or Z80 handoffs
inside the lease. C executes wholly in the worker bank.

This packet shares the existing row/gateway scratch and transient-app-stack
reservation; it is **not always-owned common state**. A future adapter must hold
the established kernel graphics lease, copy out needed receipts/work before a
different graphics gateway overwrites it, and release scratch before polling or
resuming an app. The standalone uploader is diagnostic code, **not** an uncharged
production installer. Production admission/checksum and NMI-drain integration
are still gates.

## Qualification and reproduction

From the reference container:

```
make repaint-bank
python3 tools/window_repaint_bank.py run --engine 1986 \
  --emulator-root /var/home/salvogendut/Dev/1986
```

From the host with VICE flatpak available:

```
python3 tools/window_repaint_bank.py run --engine vice
```

Both engines complete **1,415 policy calls**, with the packed host command-stream
checksum `$CF65`, explicit semantic assertions, restored zero page/hardware SP/
software SP/I/D/MMU, unchanged guards/cache state/image/bootfs boundary/shell
stack, and IRQ arrivals between calls. Positive IRQ counts are 28,486 (1986) and
28,592 (VICE). The lowest observed changed private-stack byte is `$5323`, offset
211 from `$5250`; this is a pattern-based observation, **not a worst-case stack
bound**. The lowest 64 stack bytes also remain unchanged.

All three deliberate faults are detected on both engines: restore zero page at
the wrong address; execute `CLI` inside the worker lease; or replace private-SP
high byte `$53` with shell-SP high byte `$EF`. The injected IRQ case must observe
an IRQ in a non-kernel map; the normal decoder rejects each fault even though its
policy trace still matches. Decoder tests also reject missing coverage, changed
counts/checksum, extra failures, damaged guard observations and reserved bytes.

The stream checksum is a cheap, non-cryptographic consistency check, not a proof
of semantic equivalence by itself. The prior differential lane tests and explicit
command-stream assertions remain required. This diagnostic runs without live
apps, graphical rendering, Z80 computation, RESTORE/NMI injection or task-context
relocation under load. No latency or physical-machine claim follows from it.

Two diagnostic fixes are captured in the sources/evidence: copied guard scanners
use relative branches (never a resident absolute jump while worker-flat), and
copies larger than 127 bytes use an unsigned count loop, not `DEX/BPL`. The final
scan reuses the retired diagnostic IRQ area only **after** the IRQ is stopped.
The caller's success check is structured to avoid a false-failing `booleq`
sequence emitted by this cc65 version after an intervening comparison.

Immutable source/library/maps/programs and positive/negative raw records are in
`bench/{artifacts,results}/2026-09-29-repaint-bank`, with complete SHA256 manifests.
The probe closes only its own VICE processes. No ROM-bearing snapshots are saved.

## Remaining code-fit and integration gates

Offloading the policy does **not** solve the entire resident budget. Row chrome
(1,468) + raster driver (1,175) + this binding (84) total 2,727 bytes against the
optimistic removable-body/reserve budget of 2,113: **at least 614 bytes remain
short**, before new helper/caller, painter/cache/admission/busy/teardown costs.
The normal manager is still unchanged, with its old damage storage.

Next: measure a compact resident raster replacement/shared primitives (or another
explicitly budgeted banked component); then qualify service delivery/admission,
serialized cache interoperation and NMI/context restoration. Only after code fit
should real bounded client/retained providers, poll cancellation/clip cleanup,
full pixels and input-service-gap gates be integrated. Request a hardware test
when a visible, both-format candidate exists. Keep xwave-specific optimizations
separate from generic manager work.
