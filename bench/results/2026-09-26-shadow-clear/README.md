# VIC shadow clear and reclaimed-tail qualification

The native D71 cold boot was probed in VICE 3.10 (Flatpak `net.sf.VICE`) on
2026-09-26 with the sequential 8,000-byte `VICSHADOW` segment at `$ACD1-$CC10`
and the reclaimed tail at `$CC11-$CEFF`.

`tools/shadow_boot_probe.py --vic-compare` copies the D71 and seeds the safe
zero regions of the staged `$ACD1-$CEFF` image before boot:

- the newly reclaimed `$ACD1-$AEFF` prefix, which the staged image leaves zero,
  gets a nonzero pattern so a clear that starts late cannot pass;
- the free tail bytes `$CECB-$CEFF` get the `$5A`/`$A5` sentinels;
- the task-loader (`$C800-$CDEF`) and bank-1 task-gate (`$CE00-$CECA`) staging
  bytes are left untouched because stage 1 still relocates them.

The seed travels with the payload, so both stage 1 and crt0 run after it is
planted. After boot the probe waits for the console and root-terminal
readiness bytes and then:

- saves `$ACD1-$CEFF` with the kernel MMU profile and requires all 8,000
  shadow bytes to be zero;
- compares all 751 tail bytes against the preserved preimage and requires an
  exact match, so a clear that overruns the shadow cannot pass;
- injects `xinit` and `xclock`, saves the drawn shadow with the kernel
  profile, switches to the worker profile to save the bank-1 `$6000-$7F3F`
  bitmap, restores the live MMU configuration register, and requires the two
  8,000-byte blocks to match.

`crt0` clears the shadow through the linker-generated `__VICSHADOW_RUN__` and
`__VICSHADOW_SIZE__` bounds; stage 1 no longer contains a hardcoded `$AF00`
clear. The tail is still boot staging during stage 1, so a scheduler segment
placed there must be installed after those payloads are relocated.

## Preserved blocks

| File | Bytes | Meaning |
|---|---:|---|
| `raw/shadow-preimage.bin` | 8,751 | staged `$ACD1-$CEFF` image after seeding |
| `raw/shadow-after-boot.bin` | 8,751 | same window after crt0, before any client |
| `raw/shadow-drawn.bin` | 8,000 | bank-0 shadow after `xinit` + `xclock` |
| `raw/vic-bitmap.bin` | 8,000 | bank-1 `$6000-$7F3F` under the worker profile |
| `raw/D71.sha256` | 76 | hash of the built D71 the probe consumed |

The probed D71 is
`a178553ce8f58fbf0d60a0ef5cbe533b088ae308ac7991f98a92ac02a43683d9 udeks.d71`
(`raw/D71.sha256`); the disk image itself is a build artifact and is not
committed.

## Reproduction

```sh
make 8502
make boot
python3 tools/shadow_boot_probe.py --vic-compare \
  --boot-output bench/results/2026-09-26-shadow-clear/raw/shadow-after-boot.bin \
  --shadow-output bench/results/2026-09-26-shadow-clear/raw/shadow-drawn.bin \
  --vic-output bench/results/2026-09-26-shadow-clear/raw/vic-bitmap.bin \
  --preimage-output bench/results/2026-09-26-shadow-clear/raw/shadow-preimage.bin \
  --hash-output bench/results/2026-09-26-shadow-clear/raw/D71.sha256
python3 tools/shadow_clear_decode.py bench/results/2026-09-26-shadow-clear/raw
```

`make check` verifies the preserved checksums and runs
`tests/test_shadow_clear.py`, which re-checks the clear, the full-tail
preimage match, the nonzero reclaimed prefix, and the shadow/bitmap equality.
