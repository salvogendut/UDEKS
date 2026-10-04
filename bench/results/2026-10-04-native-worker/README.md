# Native-task Z80 requests, UTRQ 0.11

Parent checkpoint: `378c033`; sources are preserved by this evidence commit.
Exact final kernel, disk images and independent WORKER.BIN are in
`bench/artifacts/2026-10-04-native-worker`. VICE captures include their normal
two-byte load-address prefix. The probe adds the same executable as WORKER
and PEER; tests reconstruct and hash that fixture rather than assuming the
unmodified base disk is what ran. Published root `build/udeks.*` are untouched.

## Passed

- VICE x128 / D64 with 1541 and D81 with 1581: ordinary `worker &` / `peer &`
  launch into native tasks 3/4, no graphical initialization, independent
  relocation/code checks, console input while the clients yield between rows.
- Each client obtains all 525 surface samples plus a 64-byte integer waveform
  at a distinct phase; captured private results match independent oracles.
  The waveform uses the worker's frozen quantized table, not host libm rounding.
- Bad opcode, oversized output and bad surface operands return; original
  request sequence is checked in the real compiled client. Engine deltas are
  exactly 46 successful / 2 rejected leases for the two initial clients.
- Legacy xclock/xwave and cowsay coexist; both clients retain their private
  samples after legacy wave overwrites common worker output. Both tasks exit,
  reap, and a reloaded client has zeroed BSS and exits/reaps again. Guards pass.
- VICE D71/1571 complete native-clock regression: two independent resizable
  clocks, targeted Ctrl+C, date, drag/resize, close/reload, four-window legacy
  coexistence, actual VDC panel bytes and shadow/VIC bitmap equality.
- Normal/panic actual-link placement gates pass. Resident BSS ends $9AF7:
  eight bytes before LOWBSS. No app allocation, CPU page, stack or common gate
  moved; graphics remains 1,533 bytes in its 1,536-byte reservation.
- Fresh parallel source-copy build reproduces D64/D71/D81, WORKER.BIN,
  resident kernel and graphics module byte-for-byte. Compiler is the reference
  `my-distrobox` cc65 toolchain. The new handler/policy is C; the serialized
  engine uses size-oriented compilation and a 10-byte counter transport.

This is not native xwave presentation or four interchangeable native slots.
Those remain next work. No new physical-C128 or 1986 worker-API qualification
is claimed. The earlier resize checkpoint has its own 1986 evidence.
Every probe terminates its own VICE process group; user sessions/settings are
not used or changed.

## Reproduce

```sh
distrobox enter my-distrobox -- make -j8 boot native-clock native-worker-probe-app graphics-apps-check placement-check
make check
python3 tools/native_worker_probe.py --disk build/boot/udeks.d64 --drive 1541 --output build/native-clients/worker-qualified-d64
python3 tools/native_worker_probe.py --disk build/boot/udeks.d81 --drive 1581 --output build/native-clients/worker-qualified-d81
python3 tools/native_clock_probe.py --disk build/boot/udeks.d71 --drive 1571 --output build/native-clients/worker-final-resize
```
