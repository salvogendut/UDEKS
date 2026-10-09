# Owned REU graphics store — standalone VICE qualification

This qualifies the C storage component, **not an installed UDEKS graphics
backend**. Boot disks, the 2,304-byte retained pool and app allocation are
unchanged. No disks were mounted by these tests. Each owned VICE session was
closed; no physical REU, 1986, live desktop, IRQ or RESTORE result is claimed.
The complete host suite passes 1,721 tests; the container boot/layout build
passes and `build/boot/udeks.d64/.d71/.d81` match the foundation baseline.

The real cc65 object has 1,372 CODE + 39 BSS bytes, excluding transport,
discovery, helpers and the future production adapter. Four independent 8 KiB
extents offer 32 KiB, deliberately less than the discovered hardware capacity.

| Attached REU | Discovered prefix | Offered store | I/O calls | Bytes compared | Rejections |
| --- | --- | --- | --- | --- | --- |
| none | none | none | 0 | 0 | 1 |
| 128 KiB | 128 KiB | 32 KiB | 1,861 | 32,769 | 14 |
| 256 KiB | 256 KiB | 32 KiB | 1,861 | 32,769 | 14 |
| 512 KiB | 512 KiB | 32 KiB | 1,861 | 32,769 | 14 |
| 1,024 KiB | 512 KiB | 32 KiB | 1,861 | 32,769 | 14 |

Every present case uploads four entire 8 KiB objects using 19/255/256/31-byte
chunks, then reads all four in 30-byte rows against independently computed
owner/offset patterns. Reads happen after all writes, so echoing the latest
transfer or cross-wiring extents cannot pass. The fixture checks trailing
host-buffer bytes, bank-1 DMA guards and unchanged bank-0 peer memory.

It also checks pending invisibility, exhaustion, duplicate ownership, foreign
and stale handles, upload order/bounds, commit completeness, release/reuse and
a deliberately partial DMA failure. Failure leaves the store offline and its
received count unchanged. All objects are released and capacity is discovered
again before the final one-byte allocation/upload/read succeeds.

`corrupt-read.bin` enables a fixture-only mutation after a successful fetch.
It fails with code 9 at the independent byte comparison; the positive decoder
rejects it. All successful record bytes and coverage counters are exact, with
zero reserved bytes, not just a boolean pass indicator.

The transport buffer is physical bank-1 `$6000-$60FF`; store DMA keeps RCR
`$49`, while a standalone common gate copies between the C buffer and bank 1.
These addresses are scratch-only: the live system already uses `$6000` for
the bitmap and `$F100` for diagnostics. They are NOT a production placement.
Discovery uses its separately qualified bank-0 byte buffer. Interrupt sources
are disabled, so unchanged RCR is not a claim of live-renderer qualification.

Initial fixture runs caught a speed-register assertion that included reserved
bits and a cc65 constant-pointer compound-assignment optimization problem in
the phase record. The final fixture masks the defined speed bit and binds the
record as a named absolute symbol; the full matrix here was regenerated after
both corrections. No storage assertion was removed to obtain a pass.

## Reproduce

```sh
distrobox-enter my-distrobox -- make -j8 reu-store-build
python3 tools/reu_store_probe.py
python3 -m unittest discover -s tests -p 'test_reu_store.py'
```

`probe.prg` and `probe.map` are the exact compiled image and map; `report.json`
contains source/artifact hashes and VICE Flatpak provenance. `SHA256SUMS`
covers the binaries, map, records, logs and report. The host test suite also
validates fault injection, random ownership lifecycles and handle exhaustion.
**Never load this destructive scratch probe inside a running UDEKS.**

See [remaining placement and integration work](../../../docs/GRAPHICS-REU.md).
