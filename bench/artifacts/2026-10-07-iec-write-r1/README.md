# Exact private writer probe, r1

This is the standalone program for the
[exact-empty qualification](../../results/2026-10-07-iec-write-r1/README.md),
not a UDEKS command/boot image. It enters at `$2800`, reports at `$6000`, and
uses the optional `UDEKS_IEC_WRITE` transport and finalizer.

**Only disposable media.** Use `tools/storage_write_probe.py`, which creates
fresh images and drives all required phases. The probe creates files on unit
8; it must not be attached to valuable/user media. Its SHA-256 is recorded in
each matching drive result. The earlier r0 program remains preserved unchanged.
