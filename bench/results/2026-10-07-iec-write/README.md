# Private IEC writer — 2026-10-07

This is the standalone backend checkpoint for #44, **not public UDEKS write
support**. See [Storage 0.3](../../../docs/STORAGE-0.3.md) for scope, placement
and pending gates. All runs used fresh disposable images and VICE true-drive
emulation through the installed `net.sf.VICE` Flatpak. No original/user disk
was attached. The exact probe is [preserved here](../../artifacts/2026-10-07-iec-write/write.prg).

| Drive / format | Non-empty roundtrip | Restart/readback | Write protected |
| --- | --- | --- | --- |
| 1541 / D64 | 10/10 exact | 10/10 exact | EROFS, image unchanged |
| 1571 / D71 | 10/10 exact | 10/10 exact | EROFS, image unchanged |
| 1581 / D81 | 10/10 exact | 10/10 exact | EROFS, image unchanged |

Sizes: 1, 2, 23, 24, 253, 254, 255, 256, 508, 515. Payload byte `i` is `i & 255`.
Each create is followed by a duplicate-create attempt that must return EEXIST.
Reopening must still return the exact original bytes. Both the C128-side
sector reader and a host-side directory/sector-chain walk check contents;
the pre-existing 768-byte KEEP sentinel is also checked. Speed and VIC bank
selection are preserved. The read-only restart must leave the disk hash intact.

**All three empty-file diagnostics produced one CR byte, not zero bytes.**
That is a recorded limitation, explicitly `qualified: false`, not a pass.
No live disk-full, media-removal, task-cancel, 1986 or physical-HW qualification
is claimed by these records. Host fault tests cover the backend error paths.

Reproduce from this branch worktree:

```sh
distrobox-enter my-distrobox -- make -j8 storage-write-backend
python3 tools/storage_write_probe.py
```

Per-run JSON contains raw 32-byte result records, program SHA-256, initial disk
hash and each phase's disk hash. Full temporary images/logs are left locally
under `build/storage/write-probe/`; they are not distribution boot images.
`make check` verifies the saved program/record correspondence. All probe VICE
sessions exited.

Normal module/policy/driver and all three boot images were rebuilt and compared
before/after: unchanged bytes. The production module still does not link the
writer, and its driver does not define `UDEKS_IEC_WRITE`.
