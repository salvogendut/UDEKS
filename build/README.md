# Published UDEKS boot images

- [udeks.d64](udeks.d64?raw=true) — 1541-compatible/Pi1541 image, 174,848 bytes
- [udeks.d71](udeks.d71?raw=true) — 1571-compatible image, 349,696 bytes
- [udeks.d81](udeks.d81?raw=true) — 1581-compatible image, 819,200 bytes
- [SHA256SUMS](SHA256SUMS) — verify with `cd build && sha256sum -c SHA256SUMS`

Published 2026-10-05 from merged main commit
`799cc85c1632395b3d66f8a4b4f6fef76c279db9` (PR #39). The images are archived
byte-for-byte in the [accepted native-client artifacts](../bench/artifacts/2026-10-05-native-clients/README.md);
subsequent README/publication changes do not change the OS image. See the
[four-native qualification record](../bench/results/2026-10-05-four-native/README.md)
for the VICE and 1986 tests, [wave-resize](../bench/artifacts/2026-10-05-wave-resize/)
for the resize follow-up, and the [2026-09-30 namespace record](../bench/results/2026-09-30-root-namespace/README.md)
for the kernel baseline. It is still an experimental build, not a stable release.

Select the disk on device 8, use native C128 mode and the 80-column display,
then type `BOOT` if it did not autoboot. Pi1541 users should use the D64.
Device 8 backs `/`; `/bin` commands work immediately, `/etc/rc` supplies the
bounded startup commands, and `/mnt` is available for a separate data disk.
All images contain the same OS; these are standard CBM DOS disk formats.
See the [main README](../README.md#download-and-boot) for a short test sequence.

Only these three images, this file and SHA256SUMS are checked into `build/`.
Compiler outputs, test runs and nested worktrees remain ignored. Ordinary
`make boot` writes to `build/boot/` and does not replace these snapshots.
After qualifying new images, maintainers use `make publish-boot`, update this
provenance and the linked evidence, then commit the images and checksum file
together. See the [publication procedure](../docs/BUILDING.md#publishing-disk-images).
