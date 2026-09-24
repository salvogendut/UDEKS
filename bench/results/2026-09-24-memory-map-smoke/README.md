# Native memory-map direct-load smoke test

This smoke test exercises the first implementation slice of proposed ADR 0003.
The 8502 development PRG was loaded into bank 0 at `$2000` and entered with
`SYS 8192` under VICE 3.10 and `1986` commit
`7556c2357506dc576ab7ab0783f9971892db1450`.

The exact `build/8502/udeks-8502.prg` had SHA-256:

```text
49d11680f6df400d15012c54931c9652cce62e5349d6aaec1a02f99e179c6f71
```

Startup selected and read back:

- configuration `$3E`: bank-0 RAM with I/O visible;
- RCR `$09`: 4 KiB top common RAM, no bottom common, VIC bank 0;
- page zero at physical bank-0 page `$00`;
- page one at physical bank-0 page `$01`;
- 8502 ownership in native C128 mode.

Both 16-byte `UMMU` records pass `tools/boot_status_decode.py`. Their mode
bytes differ only in the read-only 40/80-column-key bit (`$B7` in VICE and
`$37` in `1986`), which is intentionally not part of the required state.
Unused trailing bytes reflect each emulator's initial RAM pattern and are also
outside the contract.

The raw records and their hashes are under `raw/`. This validates the
direct-load entry only. It does not yet validate bank/profile switching,
relocated task pages, VIC bank 1, or the native D71 stage-0/stage-1 path.

## Reproduction

Build the development PRG, run VICE, and decode the common-RAM status block:

```sh
make 8502
python3 tools/vice_capture.py \
  build/8502/udeks-8502.prg /tmp/udeks-boot-status-vice.bin \
  --entry 0x2000 --result-address 0xf040 --result-size 16 \
  --state-offset 5 --poke 0xf045=0xff
python3 tools/boot_status_decode.py /tmp/udeks-boot-status-vice.bin
```

The corresponding `1986` run attaches the same PRG, injects
`BLOAD"*":SYS8192`, saves a VSF, and passes that snapshot directly to
`tools/boot_status_decode.py`.

Validate the preserved records with:

```sh
python3 tools/boot_status_decode.py raw/vice-3.10.bin
python3 tools/boot_status_decode.py raw/1986-7556c23.bin
cd raw && sha256sum -c SHA256SUMS
```
