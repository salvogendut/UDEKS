# Storage 0.1 EOF and media recovery

Preserved hardware candidates: `../../artifacts/2026-09-30-storage-0.1/`.
They are the exact private disks read by the VICE shell probes, including
HELLO, EMPTY, ONE (`X`), TAIL (no newline), LONG and alternate-PETSCII ALT.
They contain the same kernel/service payload as the normal images whose
hashes are recorded in each result. They have not yet been tested physically.

Reproduce from the reference container (`my-distrobox`) for builds and SDL:

```sh
distrobox enter my-distrobox -- make -j8 boot panic-probe placement-check iec-eof-reference
make check
python3 tools/storage_service_probe.py --tiny-files --media-recovery
python3 tools/storage_service_probe.py --disk build/boot/udeks.d71 --drive 1571 --tiny-files --media-recovery --output build/storage/sector-1571
python3 tools/storage_shell_probe.py
python3 tools/storage_shell_probe.py --disk build/boot/udeks.d71 --drive 1571 --output build/storage/shell-sector-1571
distrobox enter my-distrobox -- python3 tools/1986_storage_smoke_build.py --emulator ../1986 --roms ../1986/roms
python3 tools/iec_eof_reference.py --drive 1541
python3 tools/iec_eof_reference.py --drive 1571
```

Pass an absolute sibling path when running from the nested storage worktree.
VICE uses Flatpak `net.sf.VICE`, true 1541/1571 drives, no KERNAL disk traps.
1986 revision and image hashes are in `1986.json`; its sources were unmodified.
The stock-KERNAL reference intentionally records wrong lengths for empty/one
byte files; it is a baseline discrepancy, not a passing UDEKS file-read test.

Native service results: exact 0, 1, 2, 24, 255 and 515-byte reads, repeated EOF,
busy-unmount rejection, missing-device failure, intact caller ZP/C stack and
unchanged VIC bitmap. The media-removal test returns the original sector's
254 buffered bytes, then EIO (never successful EOF); close/unmount and absent
media mount fail/recover correctly. Both immediate replacement tests have
one EIO remount followed by success. The keyboard tests pass without a reset,
with xclock and xwave still active. 1986 covers normal keyboard reads, tiny
files and eject/reinsert recovery.

883 host tests pass at qualification, as do placement and normal/panic builds.
The shadow gate clears 8,000 bytes, verifies scheduler delivery, and compares
the complete bank-0 shadow with bank-1 VIC bitmap. No timing improvement or
automatic media-change detection is claimed. Unmount before exchanging disks.
Physical C128 + PI1541 remains the merge gate in `docs/STORAGE-0.1.md`.
