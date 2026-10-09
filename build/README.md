# Published UDEKS boot images

- [udeks.d64](udeks.d64?raw=true) — 1541-compatible/Pi1541 image, 174,848 bytes
- [udeks.d71](udeks.d71?raw=true) — 1571-compatible image, 349,696 bytes
- [udeks.d81](udeks.d81?raw=true) — 1581-compatible image, 819,200 bytes
- [SHA256SUMS](SHA256SUMS) — verify with `cd build && sha256sum -c SHA256SUMS`

Published 2026-10-09 from `tasking-native-console` source `ca0b436`, completing
issue #52 through [PR #53](https://github.com/salvogendut/UDEKS/pull/53).
The [qualification record](../bench/results/2026-10-09-native-console-files/README.md)
preserves these exact normal `make boot` images, maps, VICE D64/D81 checks and
native 1986 keyboard/mouse regressions. Publication changes documentation and
historical-test bindings, not the qualified executable bytes. The user approved
merge; no new physical-C128/Pi1541 result is inferred.
This is an experimental build, not a stable release.

The previous PR #51 downloads are
[archived unchanged](../bench/artifacts/2026-10-09-default-time-published/README.md)
for their original qualification and the initial native-console proof.

Includes writable root, cp/mv/rm, four generic graphical slots, and disk-loaded
timekeeping, foreground native console input/Ctrl+C, bounded background jobs,
task-owned file I/O and scheduled CAT.BIN. D64 omits only `xsprdef` (16 free
blocks); D71/D81 include it. Console and graphical tasks share four compatible
allocations, and only one file stream may be open system-wide. Start graphical
peers before a long file read. Other shipped console utilities remain synchronous.

Select the disk on device 8, use native C128 mode and the 80-column display,
then type `BOOT` if it did not autoboot. Pi1541 users should use the D64.
Device 8 backs `/`; `/bin` commands work immediately, `/etc/rc` supplies the
bounded startup commands including `svc load /TIME.SVC`, and `/mnt` is available
for a separate data disk. Use disposable copies: normal root is read/write.
All images contain the same OS; these are standard CBM DOS disk formats.
See the [main README](../README.md#download-and-boot) for a short test sequence.

Only these three images, this file and SHA256SUMS are checked into `build/`.
Compiler outputs, test runs and nested worktrees remain ignored. Ordinary
`make boot` writes to `build/boot/` and does not replace these snapshots.
After qualifying new images, maintainers use `make publish-boot`, update this
provenance and the linked evidence, then commit the images and checksum file
together. See the [publication procedure](../docs/BUILDING.md#publishing-disk-images).
