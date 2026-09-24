# Assembly panic-path qualification

VICE 3.10 and `1986` commit
`7556c2357506dc576ab7ab0783f9971892db1450` cold-booted the preserved
bad-descriptor D71. Both produced valid 16-byte `PANI` records at `$F0B0` with:

- panic code `$22` (service startup, invalid descriptor magic);
- the 8502 selected in native C128 mode with MMU profile `$3E`;
- IRQ masking active before diagnostic work;
- VDC output attempted and completed;
- published state written last before the permanent assembly halt.

The emulators return different values for an unused high bit of `$D505`, as
already documented by native boot qualification. The strict decoder accepts
both while checking the defined CPU and native-mode bits.

The production image was separately booted in both emulators: both service
registry records passed, and the `1986` VDC console record passed its screen and
attribute readback checks. The exact production and injected D71 images are
preserved under
[`bench/artifacts/2026-09-24-panic-r1`](../../artifacts/2026-09-24-panic-r1/README.md).

```sh
python3 tools/panic_decode.py raw/vice-3.10.bin
python3 tools/panic_decode.py raw/1986-7556c23.bin
cd raw && sha256sum -c SHA256SUMS
```
