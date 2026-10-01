# Banked graphics/calculator qualification — 2026-10-01

`tools/xcalc_probe.py` cold-boots unmodified copies of the paired artifact
disks on VICE x128, true-drive D64/1541 and D71/1571. Both pass:

- Clock + wave + independently loaded bank-1 calculator, three live windows.
- Calculator executable bytes equal the disk UDEX; private arithmetic yields
  4.00, 3.00 and 4.75, while console commands and both peers remain usable.
- A real window-manager drag from (108,30) to (40,40), unchanged retained
  commands and calculator value; compositor shadow equals VIC bitmap.
- Close-box delivery, cooperative exit/reap, reload, repeated stop/restart.
- Foreground calculator Ctrl+C preserves both background peers. Desktop
  shutdown subsequently closes all three. Software-stack guards stay intact.
- `cowsay`, `free`, and `echo` through the ordinary disk shell.

Arithmetic clicks are injected into the WM's input queue. Drag/close redirects
the existing pointer-getter operands to a map-checked temporary test record,
then restores them. Instruction sizes and all application code remain intact.
This exercises routing/composition, **not** native 1351 or keyboard hardware.
No 1986/physical-C128 qualification is inferred. Test-owned VICE processes are
terminated in the harness's `finally` block.

Reproduction (after the artifact README's container build):

```sh
python3 tools/xcalc_probe.py --output build/four-apps/final-d64
python3 tools/xcalc_probe.py --disk build/boot/udeks.d71 --drive 1571 \
  --output build/four-apps/final-d71
```

`result.json` records disk hash, exact shell sequence and results. Raw VICE
`.bin` files have two-byte load-address prefixes; strip those before comparing
bank-0 shadow with bank-1 bitmap. The PNG is a deterministic rendering of the
captured bitmap, excluding the hardware sprite. This is not an emulator screen
capture. `layout.json` records actual maps, input hashes and ownership bounds.
It reports 19 resident bytes remaining; the private loader reservation is full.
