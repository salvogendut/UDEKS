# Exact private writer probe

`write.prg` is the standalone cc65/ca65 probe built from `bench/iec-write/`,
`cbm_write.c`, `cbm_file.c` and the `UDEKS_IEC_WRITE` variant of `iec_slow.s`.
It loads/enters at `$2800` and records results at `$6000`.

**Do not run against valuable media.** It creates files on device 8. It is not
a UDEKS command or boot image. Use `tools/storage_write_probe.py`, which only
creates/attaches disposable test images and runs the required phases.
Hashes and qualification limits are in the matching
[results](../../results/2026-10-07-iec-write/README.md).
