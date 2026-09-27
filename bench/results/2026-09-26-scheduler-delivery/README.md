# Scheduler delivery qualification

The scheduler segment is linked at `$1C00-$1FFF` (`cfg/8502-scheduler.cfg`) and
delivered without ever occupying the resident image:

1. `tools/build_d71.py --scheduler --map` splits the linked image across the
   free payload holes and writes a `USCT` scatter manifest at `$ACD9`.
2. Stage 1 calls the fixed `$2003` kernel entry vector before crt0; the
   boot-only `BOOTDELIVERY` routine in the resident image gathers the chunks
   into `$1200-$15FF`, validates the manifest magic and the 16-bit image
   checksum, and reports failures in the boot-chain record.
3. crt0 clears BSS and the VIC shadow and returns to the protected `$F7D8`
   installer, which copies the gathered image into `$1C00-$1FFF` and enters
   the scheduler.
4. The scheduler entry jumps through the fixed `$2000` kernel entry vector,
   which continues into `_kernel_main`.

The delivery logic in the protected `$F700` page is only the 35-byte copier;
the gather runs from `BOOTDELIVERY` in the resident image and is accounted as
boot-only reclaim.

## Preserved blocks

| File | Bytes | Meaning |
|---|---:|---|
| `raw/udeks-scheduler.bin` | 297 | linked scheduler image (entry, identity, stubs, multi-chunk pattern) |
| `raw/d71-installed.bin` | 1,024 | `$1C00-$1FFF` captured after a D71 cold boot |
| `raw/d64-installed.bin` | 1,024 | `$1C00-$1FFF` captured after a D64 cold boot |
| `raw/1986-f9c6a24-installed.bin` | 1,024 | `$1C00-$1FFF` extracted from a 1986 f9c6a24 snapshot |

The 297-byte image spans two scatter chunks (the boot-sector hole and the
shadow prefix), so the cold boots exercise multi-chunk gathering. Both
captures equal `udeks-scheduler.bin` zero-filled to the 1,024-byte
reservation, and the D71 and D64 captures are byte-identical. The measured
delivery ceiling is 766 bytes; a larger scheduler is rejected by
`tools/build_d71.py` until more staging is freed.

Probed disks:

```text
6fb9ccd046296faf1cbbd137105f63148bc9a3ab3951762bd2ae1f601df8794b  udeks.d71
88b765026db9305ea039d08705e88ee395a64435466726e9f94b7577d364a0b7  udeks.d64
```

## Reproduction

```sh
make 8502
make boot
python3 tools/scheduler_delivery_probe.py --disk build/boot/udeks.d71 \
  --output bench/results/2026-09-26-scheduler-delivery/raw/d71-installed.bin
python3 tools/scheduler_delivery_probe.py --disk build/boot/udeks.d64 \
  --output bench/results/2026-09-26-scheduler-delivery/raw/d64-installed.bin
```

The `1986` C128DCR emulator at revision
`f9c6a24590c697c2978a0988616d8e683f6d2d69` was run for 3,000 frames with
`--save-snapshot`, and `tools/snapshot_extract.py` extracted `$1C00-$1FFF`;
it is byte-identical to the linked image and to the VICE captures.

`make check` verifies the preserved checksums and runs
`tests/test_scheduler_delivery.py`, which requires both captures to equal the
linked scheduler image and locks the delivery contract in the sources.
