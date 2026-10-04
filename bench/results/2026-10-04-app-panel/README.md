# Running-app panel correction and 1986 D81 qualification

Follow-up to the immutable `2026-10-04-native-clock` checkpoint. The user
reported repeated initials in the running panel and D81 failing to boot in
1986. Native clock remains a migration candidate, not the default xclock.

## Findings

- `panel_draw_text` used `bcc :-` after case conversion had introduced nearer
  anonymous labels. It stored the first character repeatedly instead of loading
  successive source bytes. A named `panel_next_character` target fixes this
  without adding resident bytes or changing placement.
- `1986-before` deliberately runs the old disk: it fails with nine `$12`
  screen codes (`RRRRRRRRR`) instead of `RUNNING`.
- 1986's saved desktop settings selected a ROM-backed **1571**. The D81 run
  explicitly configures a **1581** before power-on, as the desktop does after
  selection and restart. The 1581 ROM was already present. No sibling sources
  or saved user settings were modified.

## Preserved evidence

`bench/artifacts/2026-10-04-app-panel` contains the three fixed test disks and
the kernel map. NCLOCK.BIN/CLOCK2.BIN are the identical native-clock executable
preserved in `2026-10-04-native-clock`; the original legacy programs remain.

- VICE 3.10 D64/1541, D71/1571 and D81/1581: successful cold boot, both native
  clocks, date changes, drag, foreground Ctrl+C, slot reuse, four apps and
  shutdown. Each `*-panel.bin` is an actual logical VDC RAM capture from
  `$0000-$0FFF`, with a two-byte load-address prefix. Text and attributes are
  checked at startup, two clocks, cancellation, four windows and shutdown.
  Panel interior row 1 starts at `$0502`, each row is 80 bytes apart, and its
  attributes are `$0800` bytes higher. The interior width is nine characters.
- Unmodified 1986 `81485cc7bc88b2113b210a4573529322dceac0c2`: D64/1571 and
  D81/1581 with ROM-backed raw IEC. Native keyboard and 1351 drag/close,
  date/Ctrl+C/reuse/console/guards/bitmap and actual VDC character/attribute
  checks all pass. Logs include each expected row and its observed bytes.

These panel archives retain reports, logical VDC dumps and native-input logs;
the earlier clock archive retains its independent geometry/relocation evidence.
No physical 1581 acceptance is claimed. VICE pointer tests inject WM state;
1986 uses its native input path. All test-owned VICE sessions were terminated.

## Reproduce

Build `boot native-clock graphics-apps-check placement-check` in my-distrobox.
Then run on the host (repeat for D64/1541 and D71/1571):

```sh
python3 tools/native_clock_probe.py --disk build/boot/udeks.d81 --drive 1581 \
  --output build/native-clients/panel-vice-d81
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --emulator ../1986 --roms ../1986/roms --native-clock \
  --disk build/boot/udeks.d81 --drive 1581 \
  --output build/native-clients/panel-1986-d81
```

Fresh manual images are `build/native-clients/native-clock-demo.*`.
In desktop 1986 select device 8 as 1581, enable Real Disk Drive and restart
before attaching D81. See `docs/D81.md`. Root release snapshots are unchanged.
