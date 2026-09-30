# Disk-only graphical app qualification

Candidate: issue #22, branch `storage-disk-graphics`, based on main `ea14666`.
Exact D64/D71, disk-exec fixture, bootfs and graphical UDEX files are in
`bench/artifacts/2026-09-30-disk-graphics`; SHA256SUMS locks both directories.

- `vice-1541.json`: cold D64 boot, missing-mount rejection, clock first,
  13 malformed/missing wave-file cases with byte-preserved destination and
  running peer, injected STOPPED/ZOMBIE staging protection, successful retry,
  both apps with console, and stop/restart after media removal.
- `vice-1571.json`: cold D71 boot, wave first, second clock load, coexistence,
  retained stop/restart with media removed. Both compare app code with the
  actual DOS files and assert no bootfs copies exist.
- `1986.json` / `1986.log`: unmodified emulator revision `43d7dce`, SDL build
  in `my-distrobox`, real drive core/raw IEC (no KERNAL traps). Native keyboard
  and 1351 clock drag/resize, wave Ctrl+C, wave drag, focus click, both-app
  console, stop/restart; disk shell/free/df and media recovery also pass.
  The harness adds EMPTY/ONE to a disposable copy; both hashes are recorded.
- `disk-exec.json`: existing foreground image/error/ownership regression.
- `startup.json`: an RC-only fixture mounts and starts the disk clock, then
  checks standalone free/df and the unchanged IEC driver.
- `spawn.log`: actual compiled task-2 SPAWN/EXIT/WAITPID, two cycles.
- `shadow.log`, `drawn.bin`, `vic.bin`: shadow clear, preserved tail and
  bank-0/bank-1 8,000-byte bitmap equality after disk clock launch.

`tools/managed_disk_probe.py`, `tools/managed_app_fixture.py` and the native
`1986_storage_smoke_build.py --disk-graphics` preserve the live tests. Full
commands and scope are in `docs/DISK-GRAPHICS.md`. Separate clean `make -j8
boot disk-exec-image panic-probe placement-check` reproduced all compared
images byte-for-byte; app/resident binaries match the preceding merged build.
No physical C128 result or manual visual acceptance is claimed for this slice.
