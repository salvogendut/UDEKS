# Default disk-loaded time service: #49 completion

Normal `make boot` now uses TIME.SVC through RC, not a resident time policy or
an opt-in disk variant. Based on merged PR #50 (`9eda8ba`), completion branch
`services-0.1-default-boot`. The user authorized implementation, testing and
merge after successful automated qualification. No new hardware run is claimed.

## Qualified

- Host `make check`: **1,550 tests pass**, including preserved checksums,
  actual emitted normal/panic vectors, publication hashes and admission guards.
- Normal/panic actual links: startup overlay at $93D0; 2 resident bytes spare;
  manager/read wrapper linked and old time.o absent. All frozen memory bounds
  unchanged. Module: 710 emitted + 7 BSS = 717 of 728 bytes.
- Fresh isolated build reproduces all three normal disk hashes (`build.json`
  and `inputs.json`). Real upgrade from the pre-cutover resident-time build
  overlays only changed inputs, without cleaning. Registry/gate/router objects
  rebuild, all three disks match, and the next build changes no output
  (`migration.json`). Explicit legacy DISK_TIME flags are rejected.
- VICE true-drive D64/1541, D71/1571, D81/1581 cold boots: RC loads the exact
  module, date set/read, xclock creation/retirement, stop/reload, duplicate-load
  rejection, missing-file rejection, a separately sealed revision-2 disk-only
  replacement without kernel relink, and working console afterward.
- D64 missing/corrupt TIME.SVC: usable console, offline time error, successful
  replacement load. D64 missing/corrupt USH.BIN: bootfs fallback, skipped RC,
  read-only recovery mount and explicit-path loader/date/cat work.
- Native 1986 D64/1571 (`1986/result.json` identifies the revision): real
  keyboard/1351 clock drag, stop/removal, reload/duplicate refusal, clock restart
  and console input.
- Four-app VICE D81: clock/wave/calculator/drawing coexist; move/resize and
  console operations work; wave reuse, four independently named unknown apps,
  malformed-file isolation and final cleanup pass (`four-native/result.json`).
- CPU module/manager/request proofs repeated (`cpu/`): all 86,400 times of day,
  malformed header/request rejection, ownership and private-runtime restoration,
  with negative controls retained. These RAM-backed tests are not CIA hardware
  timing or physical disk tests.

Published disks are in `build/udeks.d64`, `.d71`, `.d81`; `build.json` records
their exact hashes. The host suite validates those files directly, not a second
duplicate archive. D64 has 19 free blocks and omits only xsprdef. D71/D81 have
the full app selection. Use disposable media: normal root is read/write.

## Regression caught before merge

The earlier offline-clock checks made XCLOCK use 2,566 bytes of image+BSS,
six bytes beyond its 2,560-byte small-slot allowance. It then occupied the
wave's slot, preventing the usual four apps from coexisting. A constant-base
title-copy expression in xclock saves 8 code bytes without removing either
offline check: 2,558 bytes now fit. No kernel placement or allocation changed.
The build gate now simulates the real smallest-fitting-slot admission for all
24 launch orders; individual per-app fit checks alone were insufficient.

The old D71 four-app fixture still allocates extra probe files on side one
only and ran out of space; that was a test setup failure, not a boot failure.
The complete regression uses D81. Initial recovery tests assumed normal root
mount/search; corrected tests use the existing bootfs policy below. Failed
attempts are not counted as passing results; all preserved reports are final
passing runs against the published hashes.

## Recovery and reproduction

Missing TIME.SVC in an otherwise normal boot: `svc status` reports offline;
`date` exits 1. Restore the file and run `svc load`; there is no silent resident
time fallback. With missing/corrupt disk ush, recovery deliberately has no
system root, RC or `/bin` search:

```text
mount 8 /mnt
/mnt/svc.bin load /mnt/TIME.SVC
/mnt/date.bin
/mnt/cat.bin /mnt/hello
```

The probe supplies a valid replacement as TIME2.SVC on its disposable disk.
Cold boot with a valid shell restores the normal RW root/RC startup policy.

```sh
distrobox-enter my-distrobox -- make -j8 boot placement-check graphics-apps-check service-layout-check
distrobox-enter my-distrobox -- make service-rebuild-check service-migration-check
distrobox-enter my-distrobox -- make time-module-check time-slot-check service-request-check
python3 tools/service_boot_probe.py --format d64
python3 tools/service_boot_probe.py --format d71
python3 tools/service_boot_probe.py --format d81
python3 tools/service_boot_probe.py --mode missing
python3 tools/service_boot_probe.py --mode corrupt
python3 tools/service_boot_probe.py --mode shell-missing
python3 tools/service_boot_probe.py --mode shell-corrupt
```

For 1986, run `tools/1986_storage_smoke_build.py --disk-service` inside
my-distrobox, supplying `--emulator`, `--roms`, the normal D64 and `--output`.
For four-app VICE, build `tools/build_graphical_example.py` in the container,
then run `tools/four_native_probe.py --disk build/boot/udeks.d81 --drive 1581
--output build/services/four-default-vice-d81` on the host.

Absolute paths in reports identify the original builds, not dependencies.
SHA256SUMS covers retained evidence. No arbitrary timer-NMI stress, module-load
ejection, foreground-program cancellation or generic service allocator claim.
The separate periodic CIA2 timer-NMI loader issue remains unresolved.
