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
| `raw/udeks-scheduler.bin` | 17 | linked scheduler image (entry, identity, stubs) |
| `raw/d71-installed.bin` | 1,024 | `$1C00-$1FFF` captured after a D71 cold boot |
| `raw/d64-installed.bin` | 1,024 | `$1C00-$1FFF` captured after a D64 cold boot |

Both captures equal `udeks-scheduler.bin` zero-filled to the 1,024-byte
reservation, and the D71 and D64 captures are byte-identical.

Probed disks:

```text
ad0974ba5a514ef1e45e5e026d745ecbf695cd3d710fbc55ec765be6e04c8564  udeks.d71
bff8d92c65b38959af61d05ef45be0373ad9ca534c33d0450cc4b499c0e07d49  udeks.d64
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

`make check` verifies the preserved checksums and runs
`tests/test_scheduler_delivery.py`, which requires both captures to equal the
linked scheduler image and locks the delivery contract in the sources.
