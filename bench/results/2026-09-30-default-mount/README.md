# Default-mount qualification — 2026-09-30

The runtime change is solely `user/etc/rc`: enable `mount 8 /mnt`.

- VICE true-drive 1541/D64 and 1571/D71 cold boots: first interactive commands
  are `xclock &` and `xwave &`, with no manual mount. Both start; free/df,
  directory/file reads, stopping apps, unmount and console recovery pass.
  The bank-1 IEC driver still matches its linked bytes after the sequence.
- Native unmodified 1986 raw-IEC/1351: `--drag-regression --boot-mounted`
  waits for RC completion, then runs uname, z80ctl, clock, twelve drags, wave,
  another drag and cowsay. No manual mount; all fourteen border checks pass.
- VICE missing-USH recovery: skips RC, initially has no mounted disk, then
  manual mounting, disk commands, graphics and unmount/remount pass.

Reproduce VICE with `tools/startup_probe.py --variant default`, adding
`--drive 1571 --disk build/boot/udeks.d71` for D71. Reproduce 1986 inside
my-distrobox with `tools/1986_storage_smoke_build.py --drag-regression
--boot-mounted --emulator <1986 source> --roms <ROM directory>`.
Recovery uses `tools/disk_commands_probe.py --recovery`.

JSON records contain exact disk hashes. Prior acceptance and regression
evidence remains untouched; this script change is not a fresh hardware test.
