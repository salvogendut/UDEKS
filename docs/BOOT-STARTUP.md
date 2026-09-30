# Disk shell and startup policy (Boot 0.2)

Issue [#20](https://github.com/salvogendut/UDEKS/issues/20), branch
`boot-disk-shell-startup`. This follows foreground disk execution, merged in
PR #19 after positive manual 1986 and C128/PI1541 testing.

## First testable slice: disk-loaded shell

Normal D64/D71 images now contain a closed SEQ file named `USH`: the exact
persistent UDEX bytes, not a Commodore PRG with a two-byte load prefix.
Before creating task 1, init temporarily mounts the native boot device,
loads `/mnt/USH` using the existing C storage service and UDEX validator,
closes the file, and releases that mount. The shell then runs at bank-1
`$9000` using the existing cooperative task/stream boundary. Ordinary
`mount 8 /mnt` remains available; bootstrap does not impose a user mount.

The boot-device number is captured from KERNAL `$BA` after loading SCHEDOVR
and before retiring KERNAL. Supported bootstrap units are 8–11, with 8 as
the default for a missing/unsupported value. Live qualification here uses
unit 8; the other units are not yet independently qualified.

If the shell file is missing, unreadable, or invalid, init loads the embedded
bootfs `ush` instead. This is recovery, not the final distribution model.
If that load also fails, init keeps the pre-existing resident compatibility
fallback rather than starting an invalid task; this double-failure path has
not received the same end-to-end qualification as disk-to-bootfs recovery.
No executable validation can make arbitrary machine code safe: this C128
has no memory protection, so install only trusted shell images.

The persistent shell must be an 8502 UDEX 0.0/0.1 with flags `$01`, load and
entry both `$9000`, and image+BSS at most `$0A00`. Entry is fixed by today's
scheduler; another in-image entry is rejected instead of silently ignored.
Exact file length, image bounds and BSS are checked before installation.
Boot-only loading owns bank-1 APP1 staging before a child can exist. Managed
apps and SPAWN still resolve from bootfs; they have not become disk-loaded
merely because the shell has.

## Placement and lifetime

No resident kernel, VIC shadow, app-slot, or published syscall address moves.
The loader's existing bank-1 validation extension also contains the small
bootstrap selection routine. A private gate at `$FE80` handles bank changes;
it is not a new user syscall. The emitted common loader occupies 1,496 of
1,520 bytes, including padding; the lookup/bootstrap image occupies 891 of
1,536 bytes at `$1A00`. Linker assertions enforce both limits.

The first live test caught an important lifetime overlap: boot presentation
leaves the 42-byte scheduler activator at `$F68A`, while the storage router
uses the same workspace for its bank-switch gateway. Bootstrap now saves
and restores all 42 bytes around the disk attempt, including failure paths,
before init invokes scheduler activation. The permanent switch tail and
existing `$F910/$F913/$F916/$F919` entries remain unchanged.

Diagnostics at `$F3DD-$F3DF` are source (1 disk, 2 bootfs, 3 resident fallback),
the disk-attempt `UDEKS_TASK_*` error (0 success), and bootstrap device.
They survive shell initialization. `$F064` holds the captured boot unit.

## Test it

`make boot` builds the normal disks. `make disk-exec-image` also adds the
disk-only DISKCOW and loader regression fixtures. Preserved test candidates
are under `bench/artifacts/2026-09-30-disk-shell`.

Cold boot the new image, then try:

```text
uname -a
mount 8 /mnt
ls /mnt
cat /mnt/HELLO
/mnt/DISKCOW hello
xinit
xclock &
/mnt/DISKCOW graphics
umount /mnt
```

`ls /mnt` should include `USH`; typing and window dragging should still work.
The extra disk read adds startup time at baseline slow-IEC speed. Faster IEC
is a separate optimization, not part of this feature.

To visibly prove the source without rebuilding any kernel or bootfs bytes:

```sh
python3 tools/disk_shell_fixture.py build/boot/udeks.d64 diskA build/disk-shell/A.d64
python3 tools/disk_shell_fixture.py build/boot/udeks.d64 diskB build/disk-shell/B.d64
```

Cold boot each and run `uname -a`: only the disk shell's version text changes
to `diskA` or `diskB`. Variants `missing`, `bad`, `entry`, and `flags` exercise
bootfs recovery and return the original `0.1.0` shell. These tools create new
images and refuse to overwrite the input. Do not edit the raw autoboot sectors.

## Qualification and next feature

The repeatable runners are `tools/disk_shell_probe.py` (six independent cold
boots per drive), `tools/disk_exec_probe.py` (43 shell commands including
graphics), `tools/1986_storage_smoke_build.py --disk-exec --disk-shell`,
`tools/task_spawn_probe.py`, and `tools/shadow_boot_probe.py --vic-compare`.
The source-changing fixtures alter only DOS USH file bytes or its directory
entry, so the recovery shell and boot payload cannot explain a changed
`uname` result. See the preserved results for the exact scope and hashes.
VICE 1541/D64 and 1571/D71, native 1986 input, task/graphics regressions,
898 host/evidence tests, placement checks and a byte-identical clean parallel
rebuild pass for this candidate.
The user has now reported "it all looks good" in response to this candidate's
test checklist. Record this as positive manual acceptance of the disk-shell
slice. The platform and individual checks were not specified; do not infer a
new physical-C128/PI1541 qualification from this feedback.

Next is **shell-run startup policy**, not further loader optimization:

1. Define a bounded startup text file (a DOS leaf initially, provisionally
   exposed as `/etc/rc` once the namespace supports it), with comments, blank
   lines, and normal shell commands.
2. Read/close it before dispatching commands so the single storage handle is
   available to launched programs. Keep command policy in `ush`, and make
   missing/invalid scripts or command failures recover to a prompt.
3. Demonstrate editing startup mounts and optional graphics commands on disk
   without rebuilding the kernel. Qualify VICE/1986, then real hardware.

This slice does **not** execute startup scripts or achieve kernel-only boot.
SCHEDOVR, bundled bootfs programs and preloaded non-kernel services are still
transitional and remain explicit roadmap work.
