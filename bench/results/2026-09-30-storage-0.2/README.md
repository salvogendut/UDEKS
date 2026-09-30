# Foreground disk-execution acceptance — 2026-09-30

Exact user-test images are in `bench/artifacts/2026-09-30-storage-0.2`.
`make disk-exec-image` builds them from source; normal bootfs contains no
DISKCOW entry. A fresh source-only parallel build reproduced both normal boot
images and both test disks byte-for-byte. Compiler: my-distrobox cc65 V2.18
(Fedora package 2.19-15.fc44); VICE x128 3.10; 1986 revision is in `1986.json`.
Subsequent manual hardware acceptance is recorded below.

- `vice-1541.json`, `vice-1571.json`: cold boot, real shell keyboard queue,
  43 commands each. Repeated disk execution/argv, nonzero entry and BSS,
  exact 2,560-byte image limit, malformed header classes, truncated/trailing/
  oversized files, missing/unmounted/removed media and recovery, bootfs,
  xclock/xwave coexistence. STOPPED/ZOMBIE ownership is monitor-seeded fault
  injection; launcher and full bank-1 slot/stack are byte-compared unchanged.
- `1986.log`, `1986.json`: cold boot through raw IEC and native keyboard APIs;
  repeated execution, arguments, entry/BSS/limit, rejection, recovery and
  bootfs. Built using sibling emulator sources; no sibling files were edited.
- `spawn.log`: real compiled child SPAWN/normal return/EXIT/WAITPID/reuse,
  confirming the relocated shared validator preserves the native-task path.
- `shadow.log`: full 8,000-byte shadow clear, installed scheduler, preserved
  tail gap and bank-0 shadow/bank-1 VIC bitmap equality after xinit+xclock.

Runners: `tools/disk_exec_probe.py`, `tools/1986_storage_smoke_build.py
--disk-exec`, `tools/task_spawn_probe.py`, `tools/shadow_boot_probe.py
--vic-compare`. See `docs/STORAGE-0.2.md` for reproduction and user test steps.

The first final D64 test run exposed a harness race, not a kernel failure:
multi-batch keyboard injection read the queue count under the current MMU
profile and could overwrite pending events when that profile was bank 1.
The runner now reads queue state explicitly under the kernel profile. The
preserved D64 result is the passing rerun. D71 passed before that harness-only
correction. The exact runtime disks are identical across these harness versions.

## User acceptance

Following checkpoint `f0a9065`, the user reported: "all these tests passed under
1986". This refers to the suggested mount, repeated DISKCOW execution,
xinit/xclock coexistence and subsequent typing/dragging checks. Record this as
positive manual emulator acceptance; no additional file-format/hash confirmation,
manual malformed-image coverage or physical-hardware qualification was supplied.

The user subsequently reported: "tests run beautifully on real C128 and
PI1541, you ca continue". This closes the requested physical-machine manual
gate for the suggested test sequence. No new format/hash/model confirmation
or exhaustive device/error-path log was supplied; do not broaden the claim.
