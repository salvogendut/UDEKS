# Four-app qualification — 2026-10-01

Paired images: `bench/artifacts/2026-10-01-four-apps`. All results name their
input disk hash. `SHA256SUMS` covers captured evidence.

## VICE

`four-d64` and `four-d71`: `tools/xcalc_probe.py --four-apps` on true-drive
1541/D64 and 1571/D71. Both pass four independently loaded apps, calculator
arithmetic, private drawing/toggle/clear state, retained drag, close-box and
shell close/reload, panel updates, full-capacity duplicate rejection, console
utilities, targeted Ctrl+C, desktop shutdown and stack guards.

`rejection-d64` / `rejection-d71`: `tools/four_apps_rejection_probe.py` adds
disposable DOS fixture files. Missing file returns ENOENT (2); bad magic and
wrong allocation return ENOEXEC (8); excessive BSS returns ENOMEM (12).
A separate valid `XEXTRA.BIN` targeting task 4 returns EBUSY (16) while all
four applications are live. Existing executable bytes and retained commands
match their pre-rejection captures; shell use and fourth-app reload recover.
The private loader is invoked at a root poll boundary through a self-restoring
hook in map-proven unused padding, with the caller request saved on the kernel
hardware stack. This is a mechanism test; normal launches use the shell.

Run all four with host `make four-apps-probe` after the container build.
VICE routes injected keyboard events and WM clicks/getters. PNG graphics are
rendered from the captured bitmap, excluding the hardware sprite. The console
PNG is converted from a VICE screenshot and shows all five panel entries.
Raw monitor `.bin` files include a two-byte load-address prefix. Bitmap checks
wait for completed presentation: a console reply does not fence pending flushes.

## Native input

`native-input-d64`: unmodified 1986 revision `81485cc7`, raw IEC and actual
emulated keyboard/1351 events. Four apps, arithmetic, drawing and clearing,
clock/drawing drag, close box, every app's independent restart, foreground
drawing Ctrl+C with three surviving peers, console/free accounting, shutdown,
stack guards and bitmap/shadow equality pass. Fixed-duration mouse presses
were insufficient during synchronous drawing; the harness waits for observed
WM press/release edges. This establishes functionality, not low input latency.

```sh
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --emulator ../1986 --roms ../1986/roms --four-apps \
  --output build/four-apps/native-input-d64
```

The native test disk adds unrelated EMPTY/ONE files via the shared storage
harness; its separate hash is recorded. Emulator sources were not changed.
The user subsequently reports "everything looks fine also on real HW" and
authorizes merging, completing the functional hardware acceptance gate.

## Build

`make check`: 1,056 host tests and preserved checksums pass. Both normal/panic
placement gates pass. `clean-result.json` records seven byte-identical outputs
from an isolated parallel source build. `layout.json` measures both banked
allocations and all relevant service/CPU-page reservations; resident headroom
is 45 bytes. No published root disk snapshot was refreshed.
