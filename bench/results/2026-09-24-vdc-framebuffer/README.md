# VDC framebuffer and boot-splash qualification

The preserved production D71 was cold-booted under VICE 3.10 and `1986`
commit `7556c2357506dc576ab7ab0783f9971892db1450`, each with 16 KiB and
64 KiB VDC RAM.

All four strict `VFBR` records report:

- a 640x200, one-bit, 80-byte-stride framebuffer at VDC address `$0000`;
- complete register snapshot, hardware clear, splash upload, byte-for-byte
  readback, and bitmap activation flags (`$1F`);
- the centred 160x160 splash at `$065E` with verified byte-sum `$282E`;
- bitmap register 25 value `$87` and colour register 26 value `$0D`;
- black foreground on the yellow system background.

VICE and `1986` produced byte-identical records for each corresponding VDC RAM
tier. The service registry also reported three of three services started, and
the preceding format-2 text-console record retained its black-on-yellow screen
and attribute readback guarantees. `vice-vdc.png` is the VICE VDC-canvas visual
capture.

![Black-on-yellow UDEKS VDC splash](vice-vdc.png)

The exact D71 is preserved under
[`bench/artifacts/2026-09-24-vdc-framebuffer-r1`](../../artifacts/2026-09-24-vdc-framebuffer-r1/README.md).
Real C128 RGBI output remains a qualification gate.

```sh
python3 tools/framebuffer_decode.py raw/vice-64.bin
python3 tools/framebuffer_decode.py raw/vice-16.bin
python3 tools/framebuffer_decode.py raw/1986-64.bin
python3 tools/framebuffer_decode.py raw/1986-16.bin
cd raw && sha256sum -c SHA256SUMS
```
