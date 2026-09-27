# Native input smoke — 1986, 2026-09-27

Both production disk formats pass against unmodified tracked 1986 sources at
`815b3f6914bb1ab39c6a5903b99a537c5d17add8`.
Reference build: cc65/ca65/ld65 and SDL3 in `my-distrobox`, default PAL C128DCR,
80-column boot, fast virtual IEC backend, port-1 1351 mouse, port-2 joystick.

`tools/1986_input_smoke.c` links the emulator machine sources without its SDL
frontend main. Input goes through `c128_key_event`/keyboard matrix and the
1351 motion/button APIs. It never patches UDEKS requests, submitted lines,
pointer positions or window-manager state. Key sampling and command submission
length/checksum are checked; cursor-up must recall and resubmit the same text.
The suite verifies stable idle suspensions, backspace, history, `xinit`,
`xclock &`, outline drag start/movement/release, subsequent console typing,
foreground `xwave`, Ctrl+C cancellation without stopping the background clock,
and another successful console command. Lifecycle canary failures remain zero.

Both runs take 6,239 emulated frames and produce identical diagnostic records:
one history recall, one completed drag with three outline moves, xclock RUNNING,
xwave READY, and ush WAITING for INPUT. Maximum observed key-press sampling
delay is three frames. Maximum release sampling delay is 689 frames during
initial xwave drawing: this is a functional qualification, **not** an input
latency/interactive-performance pass. Manual SDL/host input, responsiveness
measurement and physical-C128 checks remain open in issue #4.

The first run exposed a genuine selector/arbitration bug: the scanner restored
the ROM's `$D02F = $00`, leaving extended keyboard columns selected. Holding
cursor-up then looked like control-port activity and prevented scans. The
scanner now leaves `$D02F = $FF` between atomic scans. Its six-byte tail and
existing scratch reservation are retained, so resident placement is unchanged.
With the same harness the unfixed disk fails cursor-up; the corrected disks
pass. No 1986 source changes were needed.

Exact production disks are preserved in
[the input-qualified artifact directory](../../artifacts/2026-09-27-event-waits-input/).
Logs and flat bank-0 diagnostic blocks are preserved here and SHA-256 checked.
`raw/*-diagnostics.bin` contains `$F110-$F29F`; `raw/*-slots.bin` contains the
64-byte task table at `$C7D9`. Local snapshots/ROM images are not distributed.
The earlier compiled POLL probe evidence remains historical and unchanged.
VICE D71/D64 shell/graphics regression, shadow/VIC equality and placement-check
also pass on the corrected production build.
`make check` passes 631 host tests, including the preserved evidence hashes.
A full clean parallel `make -j8 boot all` reproduces both preserved disks
byte-for-byte; placement-check passes against the rebuilt object/map pair.

Reproduce after building the production disks, using your own local ROMs:

```sh
distrobox enter my-distrobox -- python3 tools/1986_input_smoke_build.py \
  --roms ../1986/roms --snapshot build/1986-input-smoke-d71.vsf \
  --log build/1986-input-smoke-d71.log
distrobox enter my-distrobox -- python3 tools/1986_input_smoke_build.py \
  --roms ../1986/roms --disk build/boot/udeks.d64 \
  --snapshot build/1986-input-smoke-d64.vsf --log build/1986-input-smoke-d64.log
```

The builder derives the private task-table address from the current overlay map;
it does not assume `$C7D9` for future builds. This increment does not complete
Tasking 0.1 or replace the remaining integrated-context hardware gates.
