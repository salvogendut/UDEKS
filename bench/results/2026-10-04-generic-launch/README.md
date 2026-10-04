# Unknown-name graphical launch qualification — 2026-10-04

Inputs: `bench/artifacts/2026-10-04-generic-launch`.
Branch `graphics-generic-apps`, implementation following committed `fbdc72d`.

## New launcher

`vice-d64` / `vice-d71`: VICE 3.10 x128 Flatpak, cold boot with true-drive
1541/1571. `tools/generic_launch_probe.py` uses ordinary ush keyboard input:
HELLO auto-loads in task 3, SECOND in task 4, with service-owned names and
dynamic running-panel mask. Both disk filenames contain the same UDEX file.

Malformed signature/patch and missing files fail; LARGE needs the larger
allocation and is rejected when only the smaller one is free. Full-slot and
legacy `xcalc -q`/`xdraw -q` attempts preserve both live image and retained
buffers. Console cowsay succeeds. Only SECOND consumes its injected click
(counter one, HELLO zero). Drag and close retire that instance, and EXTRA
reuses its task with fresh BSS. Desktop shutdown reaps both. LARGE then loads
successfully in the large slot, with SECOND in the small slot, and shutdown
leaves a working console and no reported task canary failures.

WM click/getter injection is **not native mouse qualification**. The pointer
record occupies four bytes of map-proven GRAPHICSHELP padding before the
shadow; no live BSS is patched. No loader, scheduler or service-poll hook is
used. Completed bank-0 shadow and bank-1 bitmap match. Raw `.bin` captures
have VICE's two-byte load-address prefix. The PNG omits the hardware sprite.

## Existing desktop regression and build gates

`four-apps-vice-d64` passes clock/wave/calculator/drawing coexistence, arithmetic,
clicks, drag/close/reload, console, panel, capacity, foreground Ctrl+C, shutdown,
guards and completed shadow/bitmap equality.

`native-input-d64`: unmodified 1986 `81485cc7` passes the old four-app sequence
using raw IEC and actual emulated keyboard/1351 input. This does **not**
separately qualify HELLO/SECOND on 1986. No sibling emulator sources changed.
Physical-C128 confirmation of this generic-app candidate remains pending.

`clean-result.json` records nine byte-identical outputs from an isolated clean
parallel build. Actual-map graphics and normal/panic placement gates pass;
`layout.json` records the measured bounds. The resident bridge has one byte
of headroom. No task allocation, stack, CPU page or guard moved.

Reproduce:

```sh
distrobox enter my-distrobox -- make -j8 boot graphical-example graphics-apps-check placement-check
make generic-launch-probe
python3 tools/xcalc_probe.py --four-apps --disk build/boot/udeks.d64 \
  --output build/generic-apps/four-app-regression
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --emulator ../1986 --roms ../1986/roms --four-apps \
  --output build/generic-apps/native-input-regression
```

New generic launches are background-only. Generic foreground/name-based stop,
arguments, legacy-client migration and all-four-slot compatibility remain #35
work. This is a feature checkpoint, not a claim that #35 is complete.
