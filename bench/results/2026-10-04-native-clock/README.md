# Native clock migration gate — 2026-10-04

Branch `graphics-native-clients`, based on PR #36 (`c704250`), issue #35.
This is an **independent application candidate**, not removal of the legacy
clock/wave runtime yet. No production kernel, service, allocation or default
disk image changed. The four-app baseline is preserved.

`NCLOCK.BIN` is a UDEX 0.2 relocatable C program: 2,039 image bytes, 351 private
BSS bytes, 2,463 on-disk bytes including relocation metadata. The executable
fits both native allocations. It links only user code and a private cc65
runtime; the clock model emits 43 generic retained commands. The read-only
common TIME snapshot is the same source used by `date`. Windows are fixed-size
until the generic resize contract is implemented. Source/model and the builder
are under `user/bin/xclock_native.c`, `user/lib/clock_face.c` and
`tools/build_graphical_example.py`.

VICE 3.10 Flatpak x128, true-drive D64/1541, D71/1571, D81/1581:

- Cold boot; independently added NCLOCK/CLOCK2 filenames, identical bytes.
- One executable runs in both native slots; captured installed code matches
  the independently applied relocation table byte-for-byte.
- Private commands and copied retained buffers match the trigonometric host
  oracle, including hands and digital glyphs after both `date` changes.
- Injected WM drag, targeted foreground Ctrl+C, background peer survival,
  task cleanup/reload, and four-window coexistence with unchanged clock/wave.
- Console remains usable; no legacy clock status writes before explicitly
  launching that app. Final stack guard counter stays zero.
- Two-clock bitmap equals bank-0 shadow after composition. Preview PNGs render
  captured bitmap RAM; they omit the hardware pointer sprite.

`vice-*/*.bin` files have the monitor's two-byte load-address prefix. The tests
decode it before comparing content. Keyboard and pointer injection in these
runs is not native/physical input qualification.

Unmodified 1986 `81485cc7`, D64 raw IEC, build via my-distrobox/SDL3:
`1986-d64/run.log`, `result.json`, `result.vsf` preserve the native keyboard/1351
test. No UDEKS input queue, pointer getter, request, task or app state is patched.
The test covers both slots, time changes, drag/close, Ctrl+C, reload, four windows,
console, both private stack guards and final bitmap/shadow equality. The exact
disk matches the VICE D64 candidate. Physical C128 testing remains pending.

An independent fresh-output rebuild of the clock is byte-identical (SHA-256
`3e29fa20dc92d360d6be09f175de26e6fea7a8cbf9ecee526b0fcca69068cfaa`). The existing
HELLO example remains byte-identical. Normal D64/D71/D81 hashes match the PR #36
artifacts in `bench/artifacts/2026-10-04-console-d81`; actual-build resident and
graphics placement gates pass. Host tests cover all 1,440 hour/minute values,
invalid-time atomic rejection, command bounds, canaries and custom builder
argument validation.

Reproduce:

```sh
distrobox enter my-distrobox -- make -j8 boot native-clock graphical-example graphics-apps-check placement-check
make native-clock-probe
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --emulator ../1986 --roms ../1986/roms --native-clock \
  --output build/native-clients/1986-d64
make check
```

Do not claim this completes #35: four interchangeable allocations, generic
resize and retained-wave/worker requests, app cutover and removal of compatibility
routing remain. Existing published release snapshots are untouched.
