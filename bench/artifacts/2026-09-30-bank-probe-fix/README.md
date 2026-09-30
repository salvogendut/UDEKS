# Bank-probe corruption fix — 2026-09-30

These disks include the issue #24 command-extraction work and the boot bank
probe moved from live kernel address `$8000` to boot-only scratch `$1000`.
The kernel's linked image and layout are unchanged. No emulator change.

- `udeks.d64` / `udeks.d71`: rebuilt normal disks.
- `udeks-boot-debug.d64`: same D64 with only the immediate operand of the
  secondary loader's SETMSG changed from `$00` to `$FF`, exposing KERNAL load
  messages. Generated with `tools/boot_diagnostic.py`.
- `udeks-8502.bin`: exact linked resident image used to verify `$8000`.

The physical-C128/Pi1541 boot hang is still unresolved. This is NOT a hardware
qualification claim or permission to merge. Test the diagnostic D64 with BOOT
and report the final message, particularly whether SEARCHING FOR SCHEDOVR /
LOADING appears. The old failing disk remains in `2026-09-30-disk-commands`.
