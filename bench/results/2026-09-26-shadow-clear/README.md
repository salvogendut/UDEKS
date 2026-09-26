# VIC shadow clear and reclaimed-tail qualification

The native D71 cold boot was probed in VICE 3.10 (Flatpak `net.sf.VICE`) on
2026-09-26 with the sequential 8,000-byte `VICSHADOW` segment at `$ABFE-$CB3D`
and the reclaimed tail at `$CB3E-$CEFF`. `crt0` is no longer resident: it is
linked into the `$1C00-$1CFF` `BOOTCRT` page from the same linker invocation
as the kernel, staged at `$AE00-$AEFF`, copied over the dead stage-1 page by
the `$F700` final installer, and entered at `$1C00`. It clears BSS and the
shadow through `__VICSHADOW_RUN__`/`__VICSHADOW_SIZE__`, then jumps to
`_kernel_main` (resident CODE starts at `$2000`; `_kernel_main` is at
`$2A83`).

`tools/shadow_boot_probe.py --vic-compare` copies the D71 and seeds the safe
zero regions of the staged `$ABFE-$CEFF` image before boot:

- the newly reclaimed shadow prefix below the live crt0 staging
  (`$ABFE-$ADFF`) gets a nonzero pattern so a clear that starts late cannot
  pass;
- the free tail bytes `$CECB-$CEFF` get the `$5A`/`$A5` sentinels;
- the `$AE00-$AEFF` crt0 staging and the task-loader (`$C800-$CDEF`) and
  bank-1 task-gate (`$CE00-$CECA`) staging bytes are left untouched because
  stage 1 still reads them.

The seed travels with the payload, so both stage 1 and crt0 run after it is
planted. After boot the probe waits for the console and root-terminal
readiness bytes and then:

- saves `$ABFE-$CEFF` with the kernel MMU profile and requires all 8,000
  shadow bytes to be zero, including the crt0 staging source;
- compares all 962 tail bytes against the preserved preimage and requires an
  exact match, so a clear that overruns the shadow cannot pass;
- injects `xinit` and `xclock`, saves the drawn shadow with the kernel
  profile, switches to the worker profile to save the bank-1 `$6000-$7F3F`
  bitmap, restores the live MMU configuration register, and requires the two
  8,000-byte blocks to match.

## Preserved blocks

| File | Bytes | Meaning |
|---|---:|---|
| `raw/shadow-preimage.bin` | 8,962 | staged `$ABFE-$CEFF` image after seeding |
| `raw/shadow-after-boot.bin` | 8,962 | same window after crt0, before any client |
| `raw/shadow-drawn.bin` | 8,000 | bank-0 shadow after `xinit` + `xclock` |
| `raw/vic-bitmap.bin` | 8,000 | bank-1 `$6000-$7F3F` under the worker profile |
| `raw/D71.sha256` | 76 | hash of the built D71 the probe consumed |

The probed D71 is
`7fe194ef9ddbd18c6487d292478aa3756e74f98a7c31250913c85b64c27c16b0 udeks.d71`
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
