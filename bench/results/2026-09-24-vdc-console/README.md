# VDC console service qualification

VICE 3.10 and `1986` commit
`7556c2357506dc576ab7ab0783f9971892db1450` cold-booted the preserved D71 and
produced byte-identical `VCON` records.

Both runs prove that the C console service, through the bounded assembly
transport:

- initialized an 80×25 display at VDC RAM `$0000`;
- enabled and filled attribute RAM at `$0800` with `$0F`;
- selected light-gray-on-black color register `$F0`;
- wrote the UDEKS title and read screen code `$15` (`U`) back;
- read the corresponding `$0F` attribute back;
- reached ready state without a transport timeout.

The exact D71 is preserved under
[`bench/artifacts/2026-09-24-vdc-console-r1`](../../artifacts/2026-09-24-vdc-console-r1/README.md).
The test qualifies the polled console in emulation; real-hardware confirmation
and IRQ-safe queued output remain open.

```sh
python3 tools/vdc_console_decode.py raw/vice-3.10.bin
python3 tools/vdc_console_decode.py raw/1986-7556c23.bin
cd raw && sha256sum -c SHA256SUMS
```
