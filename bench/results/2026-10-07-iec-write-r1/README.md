# Exact-empty private writer — 2026-10-07 r1

Follow-up to pushed backend `ad01c45` for #44. The earlier
[diagnostic records](../2026-10-07-iec-write/README.md) are unchanged; they
document native DOS's CR insertion. This revision corrects only the new
empty file's sector length after checked DOS CREATE/CLOSE, without changing
the reader or the meaning of a real CR file. See
[Storage 0.3](../../../docs/STORAGE-0.3.md#exact-empty-file-finalization).

| True-drive VICE | Exact create/read | Fresh-process readback | Write protection | 16-byte empty filename |
| --- | --- | --- | --- | --- |
| 1541 / D64 | 12/12 | 12/12 | EROFS, image unchanged | zero bytes |
| 1571 / D71 | 12/12 | 12/12 | EROFS, image unchanged | zero bytes |
| 1581 / D81 | 12/12 | 12/12 | EROFS, image unchanged | zero bytes |

Sizes: 0, 1, 2, 23, 24, 253, 254, 255, 256, 508 and 515, plus one CR byte.
Ordinary payload byte `i` is `i & 255`. The empty file is checked by both the
C128-side sector reader and the host-side chain walker, including after an
emulator restart. Each file's second CREATE must fail EEXIST and preserve its
data. KEEP remains unchanged; the read-only restart leaves the whole image
hash unchanged. The CPU speed and VIC bank are restored. The final
`EMPTY-1234567890` case exercises the full physical filename length.

The [exact PRG](../../artifacts/2026-10-07-iec-write-r1/write.prg) and per-drive
JSON (raw 32-byte records and hashes) are preserved. `make check` verifies their
correspondence. Fresh disposable image/log directories remain local under
`build/storage/write-probe/`; no user disk or distribution boot image was
written. All private VICE sessions exited.

Reproduce:

```sh
distrobox-enter my-distrobox -- make -j8 storage-write-backend
python3 tools/storage_write_probe.py
python3 -m unittest discover -s tests -p 'test_cbm_empty.py'
```

The fault-injected C finalizer suite compares every mock sector byte and
requires precisely one change (the target data sector's byte 1: 2 → 1).
It rejects ambiguous/invalid targets and incomplete reads without U2; failed
or ignored U2 and failed CLOSE remain errors. This is not an allocator, fsck,
or a claim of safety against arbitrary corrupt media/physical media swaps.

**Still private:** no public write syscall, writable mount or task cleanup is
enabled. Service placement and ownership are pending. No 1986, real-C128,
PI1541, live disk-full or media-removal qualification is claimed here.
