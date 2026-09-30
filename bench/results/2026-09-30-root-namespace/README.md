# Root namespace qualification — 2026-09-30

Exact candidate: [artifacts](../../artifacts/2026-09-30-root-namespace).
VICE Flatpak x128 true-drive tests use the real loaded ush and its line queue;
1986 runs raw IEC and native matrix input. Physical testing remains pending.

- `vice-1541.json`, `vice-1571.json`: cold disk-shell boot, unmounted /mnt,
  root/bin/etc views, relative cd/pwd/cat and ./cowsay, missing-file errno,
  independent device 9 read/df, busy-cwd unmount rejection, system commands
  surviving data unmount, and both graphical apps with console I/O.
- `recovery.json`: remove USH.BIN only, reach bootfs ush, mount device 9,
  explicitly execute its RECOVER UDEX, unmount and retain the console.
- `startup-{valid,invalid,missing}.json`: modify only RC.ETC; valid commands
  and graphics run, invalid later input prevents all script execution,
  absence is silent, and each path leaves the root usable and driver intact.
- `1986.json`/`.log`: revision 43d7dceb, root/cwd/native keyboard, device-8
  data alias (single-drive harness), unmount, twelve clock drags, wave launch
  and drag, then cowsay. All fourteen focused-border checks have zero missing
  pixels. `root_namespace: true` selects the combined test; legacy CLI flags
  in JSON remain false. Independent device-9 evidence is the VICE pair.
- `typed-boot.json`: stock BASIC BOOT, true 1541, C128 model, no CPU state
  patch to reach the loader.
- `spawn.log`: two compiled-C SPAWN/normal-return EXIT(37)/blocking WAITPID
  cycles through the real task boundary, using the separate probe disk.
- `boot.bin`, `preimage.bin`, `shadow.bin`, `vic.bin`: existing shadow probe
  verifies all 8,000 bytes cleared, scheduler installed, 50-byte free tail
  preserved, and bank-0 shadow equals bank-1 VIC bitmap after xinit+xclock.
  `D71.sha256` identifies the unmodified source (the probe seeds a copy).
- `clean-disks.sha256`: independent fresh parallel-build disk comparison.

Reproduction commands are in [BUILDING](../../../docs/BUILDING.md#root-namespace-candidate-26).
Use the explicit final-image paths; earlier development runs in build/ are
not this evidence. All VICE sessions launched by the probes are closed.
SHA256SUMS and result/artifact relationships are checked by
`tests/test_root_namespace_evidence.py`. Name-collision rejection, range
bounds, handle ownership and request atomicity additionally have C-backed
host tests. This does not claim general .SH execution, per-process cwd,
writable disks, or fault coverage for every physical drive.
