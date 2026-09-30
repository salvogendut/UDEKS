# Published UDEKS boot images

- [udeks.d64](udeks.d64?raw=true) — 1541-compatible/Pi1541 image, 174,848 bytes
- [udeks.d71](udeks.d71?raw=true) — 1571-compatible image, 349,696 bytes
- [SHA256SUMS](SHA256SUMS) — verify with `cd build && sha256sum -c SHA256SUMS`

Published 2026-09-30 from merged main commit
`b138b6173ee49e37688a7d7faa453a5fb993adc6` (PR #28). A rebuild in my-distrobox
matches the [accepted namespace artifacts](../bench/artifacts/2026-09-30-root-namespace/README.md)
byte-for-byte. Subsequent README/publication changes do not change the OS image.
See the [qualification record](../bench/results/2026-09-30-root-namespace/README.md)
for VICE, 1986, recovery, startup and task tests. User feedback accepts this
checkpoint; it is still an experimental build, not a stable release.

Select the disk on device 8, use native C128 mode and the 80-column display,
then type `BOOT` if it did not autoboot. Pi1541 users should use the D64.
Device 8 backs `/`; `/bin` commands work immediately, `/etc/rc` supplies the
bounded startup commands, and `/mnt` is available for a separate data disk.
Both images contain the same OS; these are standard CBM DOS disk formats.
See the [main README](../README.md#download-and-boot) for a short test sequence.

Only these two images, this file and SHA256SUMS are checked into `build/`.
Compiler outputs, test runs and nested worktrees remain ignored. Ordinary
`make boot` writes to `build/boot/` and does not replace these snapshots.
After qualifying new images, maintainers use `make publish-boot`, update this
provenance and the linked evidence, then commit the images and checksum file
together. See the [publication procedure](../docs/BUILDING.md#publishing-disk-images).
