# Streaming packed-picture viewer — steps 3 and 4

Issue #55, `graphics-packed-bitmaps`, 2026-10-09. The independent XVIEW client
now uses the qualified UTRQ 0.20 bitmap service. Normal boot services/slots
are unchanged from [steps 1–2](../2026-10-09-bitmap-integration/README.md).
File parsing stays in the app; no app-name registration or new kernel policy.

The saved executable is 3,217 bytes (2,455 image + 64 BSS = 2,519 runtime).
It still fits ordinary slots 3 and 5; it cannot use a smaller slot merely
because runtime shrank: the relocatable file must fit during loading too.
The 1,280-byte tile array is gone. Reads/uploads use a 19-byte private buffer,
yield between disk replies and never retain pointers into the shared request.

Header validation precedes CREATE/BEGIN. Pending pixels stay invisible until
all rows, zero padding, exact EOF and successful CLOSE have been checked.
Busy COMMIT retries without rereading. Errors abort the retained transaction;
EXIT retires an error frame only after recording status. An initial live test
caught an explicit-CLOSE path releasing foreground ownership too early; the
qualified app fixes that and the complete tests were rerun. User close during
upload cancels quietly; task cancellation releases both stream and surface.

## Qualification

- VICE 1571/D71 and 1581/D81: exact 128x80/160x100/9x7/dense pixels; invalid
  header, short/trailing/padded input; OOM without peer damage; two independent
  viewers; clock/wave coexistence; drag/uncover from unchanged retained bytes;
  close, foreground cancellation, pending close/cancel, stream reuse and guards.
- Native 1986 `d360c114e33216bf38a086f65af27533f581f6ba`, no tracked emulator
  changes, raw-IEC 1581/D81: the same large/dense/odd pictures and failure paths,
  real keyboard and 1351 drag, paired viewers, clock/wave, mid-upload Ctrl+C
  and close, subsequent `cat /hello`, console and guards. Input APIs only:
  no patched requests, queue, pointer getters, scheduler state or picture bytes.
- Host viewer tests use short reads and a portable transaction oracle, poison
  the shared reply between calls, inject read/sleep/CLOSE/COMMIT errors, verify
  no partial publication, preserve primary errors, and check cleanup.
- Existing four-app/console/input service regressions remain bound to the
  same base-disk hashes in the steps 1–2 evidence. No new physical-C128 result.

VICE captures include two-byte load addresses; native captures are 8,000 raw
VIC bytes. Tests recalculate pixels from the saved CBM files and compare VICE
shadow/VIC pairs. `demo/manifest.json` ties app/picture/base/disk hashes together
and inventories every original file, so adding the demo cannot silently drop
an existing application. Both demo disks reproduced byte-for-byte. Sources of
the app and test drivers are saved; local ROMs are not redistributed.

## Reproduce

From the feature worktree (never root `make clean`):

```sh
distrobox-enter my-distrobox -- make -j8 boot xview graphics-apps-check
python3 tools/build_xview_demo.py --output build/xview/demo
python3 tools/xview_probe.py --disk build/xview/demo/udeks-packed.d71 --picture build/xview/demo/ALEX128.CBM --second-picture PICS/CLOCKWORK.CBM --small-picture PICS/ALEX2.CBM --wide-picture build/xview/demo/CLOCK160.CBM --drive 1571 --output build/xview/check-vice-d71
python3 tools/xview_probe.py --disk build/xview/demo/udeks-packed.d81 --picture build/xview/demo/ALEX128.CBM --second-picture PICS/CLOCKWORK.CBM --small-picture PICS/ALEX2.CBM --wide-picture build/xview/demo/CLOCK160.CBM --drive 1581 --output build/xview/check-vice-d81
distrobox-enter my-distrobox -- python3 tools/1986_xview_check.py --emulator /var/home/salvogendut/Dev/1986 --roms /var/home/salvogendut/Dev/1986/roms --disk build/xview/demo/udeks-packed.d81 --pictures build/xview/demo --output build/xview/check-1986
make check
```

Use fresh output directories; existing files are not overwritten by packaging.
The normal D64 cannot hold the added app/photos; no existing app was removed.
Published root images/main are untouched. The completed D71/D81 demos are
ready for user testing, not implicitly authorized for merge.

## Manual test

Boot `build/packed-bitmap/build/xview/demo/udeks-packed.d81` in 1986 (1581),
or the `.d71` with a compatible drive/emulator. `/` mounts automatically.

```text
xview /alex128.cbm &
xclock &
xclock -q
xview -q
xview /clock160.cbm &
xview -q
xview /alex.cbm &
xview /clockwork.cbm &
```

Drag and cover/uncover; close the two small viewers independently. Test
CLOCK160 alone: its 2,008-byte surface leaves too little of the shared 2,304
bytes for the clock. Foreground `xview /alex128.cbm` should stop with Ctrl+C
during loading as well as after display; `cat /hello` must work afterward.
Test the close box during loading too. An empty loading frame is expected;
partial picture publication is not. No zoom/resize/pan/full-screen backing
storage is claimed. Keep any write experiments on disposable disk copies.
