# Command extraction qualification — 2026-09-30

Exact disks/maps/UDEX files are in the matching artifact directory. SHA256SUMS
and host evidence tests bind the results to those bytes. No previous evidence
was overwritten.

- VICE true-drive 1541/D64 and 1571/D71: disk cowsay/date/ls/cat and diagnostics,
  explicit uppercase paths, missing files, graphics start/stop/restart, utilities
  with both apps running, Z80 self-test, unmount/recovery/remount. Thirty-eight
  normal shell commands per run; see JSON for the authoritative sequence.
- Missing disk USH on D71 falls back to bootfs and passes the same sequence.
  Six D64 cold boots independently replace the shell help text or corrupt its
  magic, entry, flags, or directory entry, proving disk selection and recovery.
- Native 1986 `43d7dceb05e3781414922d6207089d89bd1ba81a`, unmodified sibling
  sources, SDL built in my-distrobox: keyboard, disk shell, free/df, both graphical
  apps, clock drag/resize, wave foreground Ctrl+C, drag/focus, console coexistence,
  stop/restart and media removal/reinsertion. Fixture adds EMPTY and ONE only.
- Managed-app rejection suite: missing/corrupt/wrong-slot images and live-child
  conflicts preserve the running peer; installed apps restart without media.
- Disk-exec malformed-image, bounds, ownership and removed-media regressions;
  valid disk RC mounts/launches the clock and returns one interactive prompt.
- Compiled C SPAWN/EXIT/WAITPID passes two slot-reuse cycles with real stack data.
- Shadow clear/scheduler tail checks pass; drawn bank-0 shadow and bank-1 VIC
  bitmap match byte-for-byte (8,000 bytes, saved with monitor load prefixes).
- Isolated clean `make -j8 boot panic-probe placement-check` reproduces D64/D71
  and panic D71 exactly. Compiler/VICE provenance and build log are included.

Runners: `tools/disk_commands_probe.py`, `tools/disk_shell_probe.py`,
`tools/1986_storage_smoke_build.py --disk-shell --sysinfo --disk-graphics`,
`tools/managed_disk_probe.py --faults`, `tools/disk_exec_probe.py`,
`tools/startup_probe.py --variant valid`, `tools/task_spawn_probe.py`, and
`tools/shadow_boot_probe.py --vic-compare`. All VICE sessions created by them
are terminated by their finally handlers. This is emulator qualification,
not physical hardware acceptance or exhaustive driver/device coverage.
