# VIC shadow clear and reclaimed-tail qualification

The native D71 cold boot was probed in VICE 3.10 (Flatpak `net.sf.VICE`) on
2026-09-26 with the sequential 8,000-byte `VICSHADOW` segment at `$AB2D-$CA6C`
and the reclaimed tail at `$CA6D-$CEFF`. Two boot-only objects are no longer
resident:

- `crt0` is linked into the `$1C00-$1CFF` `BOOTCRT` page from the same linker
  invocation as the kernel, staged at `$AE00-$AEFF`, copied over the dead
  stage-1 page by the `$F700` final installer, and entered at `$1C00`. It
  clears BSS and the shadow through `__VICSHADOW_RUN__`/`__VICSHADOW_SIZE__`,
  then jumps to `_kernel_main` (resident CODE starts at `$2000`).
- `probe.o` is linked into the `$0B00-$0BFF` `BOOTPROBE` page, staged at
  `$AD00-$ADFF`, and copied over the dead boot-sector page by the same final
  installer; the kernel runs its machine probes from `$0B00`.

`tools/shadow_boot_probe.py --vic-compare` copies the D71 and seeds the safe
zero regions of the staged `$AB2D-$CEFF` image before boot:

- the newly reclaimed shadow prefix below the live probe staging
  (`$AB2D-$ACFF`) gets a nonzero pattern so a clear that starts late cannot
  pass;
- the free tail bytes `$CECB-$CEFF` get the `$5A`/`$A5` sentinels;
- the `$AD00-$ADFF` probe staging, the `$AE00-$AEFF` crt0 staging, and the
  task-loader (`$C800-$CDEF`) and bank-1 task-gate (`$CE00-$CECA`) staging
  bytes are left untouched because stage 1 still reads them.

The seed travels with the payload, so stage 1, crt0, and the probe all run
after it is planted. After boot the probe waits for the console and
root-terminal readiness bytes and then:

- saves `$AB2D-$CEFF` with the kernel MMU profile and requires all 8,000
  shadow bytes to be zero, including both staging sources;
- compares all 1,171 tail bytes against the preserved preimage and requires
  an exact match, so a clear that overruns the shadow cannot pass;
- injects `xinit` and `xclock`, saves the drawn shadow with the kernel
  profile, switches to the worker profile to save the bank-1 `$6000-$7F3F`
  bitmap, restores the live MMU configuration register, and requires the two
  8,000-byte blocks to match.

## Preserved blocks

| File | Bytes | Meaning |
|---|---:|---|
| `raw/shadow-preimage.bin` | 9,171 | staged `$AB2D-$CEFF` image after seeding |
| `raw/shadow-after-boot.bin` | 9,171 | same window after crt0, before any client |
| `raw/shadow-drawn.bin` | 8,000 | bank-0 shadow after `xinit` + `xclock` |
| `raw/vic-bitmap.bin` | 8,000 | bank-1 `$6000-$7F3F` under the worker profile |
| `raw/capability-record.bin` | 32 | `HCAP` record from the same D71 under VICE, probe running from `$0B00` |
| `raw/1986-f9c6a24-hcap.bin` | 32 | same `HCAP` record extracted from the 1986 snapshot |
| `raw/1986-f9c6a24-boot-chain.bin` | 48 | `$F040` boot chain from the 1986 snapshot |
| `raw/D71.sha256` | 76 | hash of the built D71 the probe consumed |

The probed D71 is
`587d708086b67bcb9cd6548f3c0b46eaf31a881b5ab3adb7be23e381c70f749f udeks.d71`
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

## Probe gate

The probe gate uses the same D71 under VICE: capture `$F0C0-$F0DF` with
`--entry 0x1C00` and decode it, which yields `PAL, 8568-family revision 2,
64 KiB VDC RAM` and no expansions (`raw/capability-record.bin`).

```sh
python3 tools/vice_capture.py build/boot/udeks.d71 /tmp/udeks-hcap.bin \
  --native-disk --entry 0x1c00 --result-address 0xf0c0 --result-size 32 \
  --state-offset 5 --complete-value 2 --timeout 90
python3 tools/capability_decode.py /tmp/udeks-hcap.bin
```

## 1986 qualification

The same D71 was run in the `1986` C128DCR emulator at revision
`f9c6a24590c697c2978a0988616d8e683f6d2d69` for 3,000 frames and a VSF
snapshot was extracted. The `HCAP` record is byte-identical to the VICE
record, and the boot chain reports `stage 0 -> stage 1 -> 8502 kernel
complete` with the Z80 image verified.

```sh
cd /var/home/salvogendut/Dev/1986
./1986 --disk /var/home/salvogendut/Dev/UDEKS/build/boot/udeks.d71 \
  --frames 3000 --no-throttle --save-snapshot /tmp/udeks-1986.vsf
cd /var/home/salvogendut/Dev/UDEKS
python3 tools/snapshot_extract.py /tmp/udeks-1986.vsf /tmp/1986-hcap.bin \
  --address 0xf0c0 --size 32
python3 tools/snapshot_extract.py /tmp/udeks-1986.vsf /tmp/1986-boot.bin \
  --address 0xf040 --size 48
python3 tools/capability_decode.py /tmp/1986-hcap.bin
python3 tools/boot_chain_decode.py /tmp/1986-boot.bin
```

`tests/test_shadow_clear.py` decodes both committed `HCAP` records and the
1986 boot chain, and requires the two `HCAP` records to be byte-identical.
