# Issue #24 final qualification — 2026-09-30

Results bind to the matching artifact directory by SHA-256. Toolchain:
cc65 V2.18 (Fedora 2.19-15.fc44) in my-distrobox; Flatpak VICE 3.10;
native 1986 revision is recorded in `1986.json` (sibling sources unmodified).

- VICE true-1541/D64 and true-1571/D71: default RC mounts device 8, prints
  success only after the media read, and the first user commands launch
  xclock/xwave without mounting manually. Disk commands, stop/unmount and
  console recovery pass; IEC driver bytes remain unchanged.
- Typed BASIC BOOT passes on the normal D64 (not just emulator autostart).
- Native 1986 raw-IEC keyboard/1351 regression: uname, Z80 test, implicit
  desktop launch, twelve clock drags, wave launch/drag, cowsay; fourteen
  border-pixel checks pass. No manual mount.
- Actual cold-boot banner fault injection changes only the loaded IEC and/or
  bootfs identity bytes in disposable SCHEDOVR copies. Results 01/01, 00/01,
  01/00, 00/00 produce independent OK/-- rows. This is presence/version
  checking, not whole-image integrity validation or writable filesystem support.
- Managed apps: missing mount/file, already-running/not-ready, malformed
  UDEXs, absent media (I/O error), live-child busy (including stale launcher),
  peer/target preservation and restart without media all pass.
- Missing USH falls back to bootfs; disk utilities, graphics, unmount/remount
  and console recovery pass. The recovery shell intentionally skips RC.
- Shadow clear/scheduler installation and 8,000-byte shadow/VIC equality pass.
- Compiled-task SPAWN/EXIT/WAITPID passes two slot-reuse cycles on D64 and D71
  (`spawn.log`, exact separate probe disks in the artifact directory). Build
  runs in my-distrobox; VICE probes run on the host. The initial container
  attempt could not connect to Flatpak VICE; the host runs above succeeded.
- An isolated clean parallel `make -j8 boot panic-probe placement-check`
  reproduces normal D64, D71 and panic D71 byte-for-byte. Build logs included.
  `clean-disks.sha256` was generated from that separate clean-build directory.

Runners: `startup_probe.py --variant default`, `boot_entry_probe.py`,
`boot_banner_probe.py`, `managed_disk_probe.py --faults`,
`disk_commands_probe.py --recovery`, `shadow_boot_probe.py --vic-compare`,
and `1986_storage_smoke_build.py --drag-regression --boot-mounted`.
Each VICE runner terminates its own session. The user's earlier hardware
acceptance is retained separately; these finishing changes have not received
a separate real-C128 run and do not explain the original hardware hang.
