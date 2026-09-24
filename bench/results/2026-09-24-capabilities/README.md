# Hardware-capability qualification

The preserved production D71 was cold-booted under VICE 3.10 and `1986`
commit `7556c2357506dc576ab7ab0783f9971892db1450` with six configurations:

| Emulator profile | Video | VDC | Expansion result |
|---|---|---|---|
| VICE default | PAL | revision 2, 64 KiB | none |
| VICE `-ntsc -VDC16KB -VDCRevision 1` | NTSC | revision 1, 16 KiB | none |
| VICE `-reu -reusize 512` | PAL | revision 2, 64 KiB | REU |
| VICE `-georam -georamsize 512` | PAL | revision 2, 64 KiB | GeoRAM |
| `1986`, 64 KiB VDC | PAL | revision 2, 64 KiB | none |
| `1986`, 16 KiB VDC | PAL | revision 2, 16 KiB | none |

Every 32-byte `HCAP` record passed strict consistency checks. The default VICE
and 64 KiB `1986` records are byte-identical. On the production image, `1986`
also confirmed that both registered services started and the console retained
its screen/attribute readback guarantees after the non-destructive VDC RAM
probe.

The exact D71 is preserved under
[`bench/artifacts/2026-09-24-capabilities-r1`](../../artifacts/2026-09-24-capabilities-r1/README.md).
Expansion presence is qualified in VICE; real hardware and expansion-capacity
tests remain open gates.

```sh
python3 tools/capability_decode.py raw/vice-pal64.bin
python3 tools/capability_decode.py raw/vice-ntsc16.bin
python3 tools/capability_decode.py raw/vice-reu512.bin
python3 tools/capability_decode.py raw/vice-georam512.bin
python3 tools/capability_decode.py raw/1986-64.bin
python3 tools/capability_decode.py raw/1986-16.bin
cd raw && sha256sum -c SHA256SUMS
```
