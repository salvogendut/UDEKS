# Service-module registry qualification

VICE 3.10 and `1986` commit
`7556c2357506dc576ab7ab0783f9971892db1450` cold-booted the preserved D71 and
produced byte-identical 24-byte `SREG` records at `$F090`.

Both runs prove that the generic registry:

- discovered the one descriptor in the image table;
- accepted its `USVC` magic, ABI 0.1, and 16-byte size;
- recorded console class 1, instance 0, and flags `$03`;
- dispatched the descriptor's start vector successfully;
- reached ready state with one service started and no failures.

The `1986` snapshot also passed the complete native boot-chain decoder and the
VDC console's existing readback checks. The exact D71 is preserved under
[`bench/artifacts/2026-09-24-service-registry-r1`](../../artifacts/2026-09-24-service-registry-r1/README.md).
Dynamic discovery and the reserved poll/stop lifecycle operations remain future
work.

```sh
python3 tools/service_registry_decode.py raw/vice-3.10.bin
python3 tools/service_registry_decode.py raw/1986-7556c23.bin
cd raw && sha256sum -c SHA256SUMS
```
