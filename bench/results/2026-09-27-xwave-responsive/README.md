# Bounded initial xwave rendering — first increment

Issue: https://github.com/salvogendut/UDEKS/issues/6.
Branch: `xwave-responsive-rendering`, based on main `1b7a6e0`.
Exact production D71/D64 images: `bench/artifacts/2026-09-27-xwave-responsive`.
Reference compiler: cc65 in `my-distrobox`; VICE Flatpak x128 3.10;
unmodified 1986 revision `815b3f6914bb1ab39c6a5903b99a537c5d17add8`.
ROM files and full local snapshots are not redistributed.

## Native 1986

Commands (run separately for each disk):

```sh
distrobox enter my-distrobox -- python3 tools/1986_input_smoke_build.py \
  --roms ../1986/roms --disk build/boot/udeks.d71 \
  --snapshot build/xwave-responsive-d71.vsf --log build/xwave-responsive-d71.log
```

The harness cold-boots the disk, types through the keyboard matrix, exercises
history/backspace and 1351 dragging, then sends Ctrl+C during initial plotting.
No guest request, pointer, window, or keyboard state is injected. Only native
emulator input APIs are used. D71/D64 give the same results:

- Foreground launch returns with row 0, four vertices, and one successful lease.
- Ctrl+C terminates **before** completing row 0; the background clock survives,
  and subsequent console input works.
- A second background launch completes 21 rows with 21 successful leases and
  zero 8502 fallbacks; moving the completed wave does not reacquire the Z80.
- Maximum sampled key press: 4 PAL frames. Maximum release: 383 frames.
- Total: 7,684 frames; lifecycle canary failures: zero.

The baseline smoke's maximum release was 689 frames. The new launch still
takes 383 frames for Return release, and closing over the clock takes 222
frames. These are substantial synchronous chrome/console/compositor costs:
**this increment is not a general responsiveness pass**. Cached repaint remains
synchronous. After the automated runs, the user reported the requested manual
1986 input/resize/restacking check looked good (2026-09-27). This is a user
observation, not an instrumented performance result. Issue #6 stays open for
compositor work; physical hardware qualification remains outstanding.

## VICE and host gates

```sh
python3 tools/task_yield_probe.py --timeout 90
python3 tools/task_yield_probe.py --disk build/boot/udeks.d64 --timeout 90
python3 tools/shadow_boot_probe.py --vic-compare --work build/vice/xwave-responsive-shadow
distrobox enter my-distrobox -- make placement-check
make check
```

Both VICE disks complete 21 cached rows while accepting utility commands;
suspensions progress 2→2→22 and the shell returns to INPUT waiting. The shadow
probe proves the 8,000-byte clear, 50-byte unassigned gap preservation, and
bank-0/bank-1 bitmap equality after xinit+xclock. It does **not** compare the
completed wave's native pixels. The host harness executes the actual xwave C
against mocks and checks the completed wave pixel-for-pixel against the prior
projection, including a larger geometry, partial-prefix replay, pause, fallback,
and close/relaunch. There is no claim of a captured visual VICE resize test.

Two clean `make -j8 boot all` runs reproduce the preserved disks byte-for-byte;
production and panic maps build. All 634 host tests pass. Placement remains
fixed at BSS ending `$A1DF`, VICSHADOW `$A1E0-$C11F`. Application image is
1,708 bytes, BSS 549; bootfs is 11,689/11,708. Historical evidence is untouched.
