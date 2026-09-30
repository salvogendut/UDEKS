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
The default disk `RC` subsequently issues that command, so the normal prompt
has device 8 mounted at `/mnt`. Recovery skips RC and still starts unmounted.

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
entry both `$9000`, and image+BSS at most `$1000`. Entry is fixed by today's
scheduler; another in-image entry is rejected instead of silently ignored.
Exact file length, image bounds and BSS are checked before installation.
Boot-only loading owns bank-1 APP1 staging before a child can exist. Managed
apps now load from mounted disk on first use; SPAWN still resolves bootfs.
See [disk-loaded graphics](DISK-GRAPHICS.md) for their separate ownership gate.

## Placement and lifetime

No resident kernel, VIC shadow, app-slot, or published syscall address moves.
The loader's existing bank-1 validation extension also contains the small
bootstrap selection routine. A private gate at `$FE80` handles bank changes;
it is not a new user syscall. The emitted common loader occupies 1,496 of
1,520 bytes, including padding; the lookup/bootstrap reservation is
1,536 bytes at `$1A00`. Linker assertions enforce both limits; current managed
loader changes and qualification are in [Disk graphics](DISK-GRAPHICS.md).

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

Cold boot the new image (default RC mounts device 8), then try:

```text
uname -a
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

Cold boot each and run `help`: only the disk shell's `Recovery` label changes
to `diskAery` or `diskBery`. (The historical probe changed uname; uname is now
a standalone disk utility.) Variants `missing`, `bad`, `entry`, and `flags` exercise
bootfs recovery and return the original help text. These tools create new
images and refuse to overwrite the input. Do not edit the raw autoboot sectors.

## Accepted disk-shell checkpoint

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

## Shell-run startup and system-information commands

The disk shell now reads the boot device's ordinary ASCII `RC` SEQ file.
The source default is `user/etc/rc`; `/etc/rc` is a future namespace, not a
currently supported disk path. Up to 255 bytes, 54 bytes per line; LF, CRLF,
blank lines and leading-whitespace `#` comments are supported. This is a
bounded list of normal shell commands, not a Bash scripting language:
no variables, loops, quoting extensions, pipes or conditionals are added.

The entire script is read, checked, closed and unmounted before any command
runs. A missing/empty file is silent. Oversize, invalid text or I/O failure
skips the entire script with a diagnostic and leaves an interactive prompt.
Command failures do not stop later lines. Foreground applications keep their
normal Ctrl+C behavior; use `&` to continue startup with a background app.
Bootfs recovery intentionally omits the startup reader and never reruns RC.
Common diagnostic `$F3E0` is 1 while executing RC, 2 when finished/skipped
by the disk shell (not a bootfs-recovery diagnostic).

For example, replace just the disk's `RC` file with:

```text
# Optional graphical startup
mount 8 /mnt
xinit
xclock &
echo Ready
```

The default file runs `mount 8 /mnt`; no manual mount is needed before disk
commands or the first graphical application. This specifically selects device
8, even if a different device booted the machine. Edit or comment out the line
to change that policy. A mount failure reports an error and leaves the prompt
usable; the recovery shell still requires a manual mount. Successful mounting
prints `mount: /mnt ready (read-only)` after reading the media, not merely
because the driver was compiled in.
Use `mount 9 /mnt` instead if desired; script contents are policy, not kernel
code. No image rebuild is necessary to change a DOS RC file. The repeatable
`tools/startup_probe.py` creates modified disk copies to test this explicitly.

The boot banner's IEC-driver and bootfs HEADER rows use stage 1's comparison
of the actual bank-1 UIEC/UBFS 0.1 headers. Boot-chain offsets 21/22 hold 1 for
a match and 0 for a mismatch; `[ -- ]` is a mismatch. Neither row implies a
mounted/writable filesystem or a whole-image integrity check. Normal boot
shows the KERNAL secondary-load messages, matching the hardware-tested setting.

`FREE` and `DF` are disk-only standalone UDEX files (one C multicall program),
not resident shell builtins. Bare foreground names search bootfs `/bin` first,
then `/mnt`; explicit `/mnt/FREE` and `/mnt/DF` work as well. After normal boot:

```text
free
df
```

`free` reports physical CPU/VDC capacities separately and the current fixed
2,560-byte native-child image pool as total/used/free. This is **not total
unused physical RAM**: a general heap is not implemented, and fixed resident,
stack, cache and graphics reservations are not allocatable. VDC memory is
not CPU RAM. Future allocator work must replace this limited accounting,
not silently label all unused address ranges as free memory.

`df [/mnt]` queries live BAM data via UTRQ 0.6 `STATFS` and prints total,
used and available 256-byte DOS allocation blocks. The mount remains read-only.
The D64 derivative now clears the D71 double-sided flag so totals describe
the actual medium, rather than claiming an absent second side.

To keep C startup code out of the resident kernel, ush owns bank-1
`$9000-$9FFF` with a bounded `$E900-$EFF0` C stack; the separately linked
IEC driver/BAM reader uses `$E300-$E8FF`. Its private stack remains at `$E200`.
The full shell reserves 384 BSS bytes (356 linked); recovery reserves 80.
The secondary envelope now ends at `$E900`, and the packager preserves the
driver when inserting bootfs. Native child/managed image bounds stay unchanged.

### Startup/sysinfo qualification — 2026-09-30

Exact disks and UDEX files: `bench/artifacts/2026-09-30-startup-sysinfo`.
Receipts: `bench/results/2026-09-30-startup-sysinfo`. SHA-256 manifests and
host tests bind the receipts to these images; the earlier disk-shell artifacts
are unchanged. The `udeks-rc-demo.d64` copy changes only RC and demonstrates
automatic mount, `xinit`, `xclock &`, and `RC-END`. Normal `udeks.d64` / `.d71`
retain the older comment-only RC (current builds mount device 8 by default).
`udeks-test.*` additionally include disk-execution
regression programs.

- 913 host/evidence tests pass. Clean parallel `make -j8 boot disk-exec-image
  panic-probe placement-check` reproduces byte-identical normal and test disks.
- VICE true-drive 1541/D64 and 1571/D71 execute the RC demo and disk-only
  `free`, `df`, explicit `/mnt/DF`, bad-argument stderr/exit, listing, reading,
  unmount and bootfs commands. The final IEC driver bytes match the linked
  image, checking that shell stack use did not overwrite it. This is not an
  exhaustive stack-depth proof for arbitrary future shell extensions.
- D64: 664 total / 206 available; D71: 1328 total / 870 available. Expected
  counts are independently calculated from each tested disk's BAM.
- Missing and malformed RC recover; the malformed later line prevents the
  preceding `MUST-NOT-RUN` command from executing. Six final 1541 shell-source
  and recovery variants pass after the full/recovery shell split.
- Unmodified native 1986 revision `43d7dce`, built with SDL3 in my-distrobox,
  passes default-RC completion, free/df and disk-execution/media recovery.
  The auto-graphics RC variant is qualified in VICE, not separately in 1986.
- SPAWN/compiled-child/WAITPID regression and shadow-clear/VIC bitmap equality
  pass. All test VICE sessions are terminated by their runners.

The user reports "looks ok to me" for this startup/sysinfo candidate: positive
manual acceptance. The platform and individual checks were not specified;
do not infer a new physical-C128 qualification or exhaustive RC-demo testing.
The user has authorized the commit/push/PR checkpoint. The next project step
is to review issue #20 for merge, not repeat the same generic test request or
start unrelated optimization. Merge approval remains separate.

This slice does **not** achieve kernel-only boot.
SCHEDOVR, bundled bootfs programs and preloaded non-kernel services are still
transitional and remain explicit roadmap work.
