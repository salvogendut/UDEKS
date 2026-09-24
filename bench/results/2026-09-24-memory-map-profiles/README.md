# Native MMU profile and page-relocation qualification

This probe executes from the proposed 4 KiB top-common region while exercising
the profile and page-relocation portions of ADR 0003. The exact executable is
preserved under
[`bench/artifacts/2026-09-24-memory-map-r1`](../../artifacts/2026-09-24-memory-map-r1/README.md).

VICE 3.10 and `1986` commit
`7556c2357506dc576ab7ab0783f9971892db1450` independently completed all 23
checks. Their 128-byte result records are byte-for-byte identical and prove:

- atomic selection of kernel-I/O `$3E`, kernel-flat `$3F`, worker-I/O `$7E`,
  and worker-flat `$7F` through `$FF01-$FF04`;
- distinct bytes retained at the same logical addresses in banks 0 and 1;
- `$D500` exposes private RAM in flat profiles and the MMU in I/O profiles;
- `$FF00` remains the MMU configuration register in every profile;
- the `$F000-$FFFF` common region survives every bank/profile transition;
- logical pages zero and one can target bank-1 physical pages `$80/$81`, be
  modified, and return safely to bank-0 pages `$00/$01`.

This validates the two emulator-side profile/relocation gates in ADR 0003. It
does not yet validate the D71 boot path, VIC bank-1 display traffic, or real
hardware.

## Reproduction

```sh
make bench-memory-map
python3 tools/vice_capture.py \
  build/bench/memory-map/memory-map.prg /tmp/udeks-memory-map-vice.bin \
  --entry 0x2800 --result-address 0xf100 --result-size 128 --state-offset 5
python3 tools/memory_map_decode.py /tmp/udeks-memory-map-vice.bin
```

For `1986`, attach the same PRG, inject `BLOAD"*":SYS10240`, save a VSF, and
pass the snapshot directly to `tools/memory_map_decode.py`. Validate the
preserved raw records with:

```sh
python3 tools/memory_map_decode.py raw/vice-3.10.bin
python3 tools/memory_map_decode.py raw/1986-7556c23.bin
cd raw && sha256sum -c SHA256SUMS
```
