# Four generic native graphical allocations — 2026-10-05

This qualifies the cutover after resize-fix commit `cb003f9`, on
`graphics-native-clients` / issue #35. Exact normal disks, programs, maps and
placement report are in `bench/artifacts/2026-10-05-four-native`; hashes in
both directories lock the captured evidence. Published `build/udeks.*` is
unchanged. No physical-hardware acceptance is claimed for this new layout.

## Results

- VICE 3.10: D64/1541, D71/1571 and D81/1581 cold boot pass. All four defaults
  run as ordinary relocated disk programs, alongside console commands.
- Wave preserves all 525 heights and 524 edges. A move publishes no new
  geometry; resize holds the outline without publication and submits exactly
  once on release. Exactly 21 Z80 row leases occur per initial load; moving
  and resizing use the private height cache. Projection yields every four
  vertices. Synchronous dense retained rasterization remains a limitation.
- Calculator evaluates 12+34=46; drawing accepts an independent cell click;
  date 03:15 is reflected by the clock's exact retained-command oracle.
- The same independently linked HELLO executable runs as ORBIT, CANVAS,
  HELLO and FOURTH, occupying all four allocations (6,4,5,3). Per-instance
  clicks and BSS stay independent. A fifth app is rejected; a malformed
  relocation leaves peers intact; freed task 4 accepts EXTRA with clear BSS.
- Actual VDC panel characters and attributes match four default, four unknown
  and reused instance names. Code, software-stack guards and retained pool
  bounds are checked. VIC bitmap equals the bank-0 shadow after repaint.
- Unmodified 1986 `81485cc7`, raw-IEC D64/1571: real emulated keyboard/1351
  input passes clock dragging, wave dragging/resizing, held-outline behavior,
  worker reuse, calculator 1.25+2.75=4, drawing input, console typing,
  fifth-app rejection, all four apps independently stopped/reloaded,
  foreground Ctrl+C, shutdown and all four hardware/software stack guards.
  `1986-d64/result.vsf` preserves four live native clients before shutdown.

VICE `.bin` captures include a two-byte monitor load address. Repeated resize
tags hold the *last* iteration; the JSON also records the earlier iteration's
presentation count. These tests inject pointer getters/click mailboxes in
VICE; only the separate 1986 run is a native keyboard/mouse-input test.
HELLO's initialized DATA intentionally changes after a click; code comparisons
exclude that DATA, not executable code. Apps remain trusted cooperative code.

## Reproduction

Reference compiler: cc65 V2.18, Fedora package 2.19-15.fc44, in my-distrobox.

```sh
distrobox enter my-distrobox -- make -j8 boot graphical-example graphics-apps-check placement-check
make four-native-probe
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --emulator ../1986 --roms ../1986/roms --four-native \
  --output build/native-clients/four-1986-d64
make check
```

A fresh source copy in `/tmp/udeks-four-clean.TJ2ZHB` built with `make -j8 boot
graphics-apps-check placement-check` reproduces all three normal disk hashes
byte-for-byte. The actual-map gate checks normal/panic placement, compiled
allocation tables, delivery lifetimes, app capacities and retained pool bounds.
Existing frozen common gates, console/recovery and worker reservations remain.
No emulator source changes were made. The probes' VICE sessions were closed.
