# Native D71 cold-boot qualification

The preserved D71 cold-boots without a BASIC command in VICE 3.10 and `1986`
commit `7556c2357506dc576ab7ab0783f9971892db1450`.

The C128 ROM recognizes the `CBM` sector at track 1/sector 0 and loads 212
consecutive sectors into bank 0 at `$1C00`. Inline stage 0 runs from `$0B00`,
stage 1 runs from `$1C00`, and a common-RAM gateway copies the Z80 image from
bank-0 flat RAM at `$D000-$EFFF` to bank 1 at `$2000-$3FFF`. It compares every
installed byte and records matching 16-bit sums (`$083F`) before entering the
8502 kernel at `$2000`.

Both 48-byte records pass `tools/boot_chain_decode.py` and show:

- `S0OK`, `S1OK`, and `Z80!` completion markers;
- loader state 2 with no failure;
- source and installed-Z80 sums both `$083F`;
- the kernel's completed `UMMU` record with profile `$3E`, RCR `$09`, and
  physical bank-0 pages zero and one.

The mode byte and bytes outside the declared records retain emulator-specific
power-on values, so the full raw blocks are not expected to hash identically.

## Reproduction

```sh
make boot
python3 tools/vice_capture.py \
  build/boot/udeks.d71 /tmp/udeks-native-boot.bin --native-disk \
  --entry 0x2000 --result-address 0xf040 --result-size 48 \
  --state-offset 28 --timeout 60
python3 tools/boot_chain_decode.py /tmp/udeks-native-boot.bin
```

Attach the same D71 at `1986` startup, save a VSF, and pass that snapshot
directly to `tools/boot_chain_decode.py`. Validate the preserved evidence with:

```sh
python3 tools/boot_chain_decode.py raw/vice-3.10.bin
python3 tools/boot_chain_decode.py raw/1986-7556c23.bin
cd raw && sha256sum -c SHA256SUMS
```
