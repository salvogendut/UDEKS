# Issue #24 release disks — 2026-09-30

Cold boot `udeks.d64` on a 1541/Pi1541 or `udeks.d71` on a 1571.
Normal disks now retain the SETMSG $FF setting from the hardware-accepted
diagnostic variant; no separate debug disk is needed. RC mounts device 8 at
`/mnt`; shell, utilities and graphical programs are ordinary disk files.

This preserves the bank-probe fix and default mount, and adds measured
IEC/bootfs HEADER rows, a mount-success message after reading media, and
specific managed-program failure messages. See the matching results directory.
The exact finishing changes have emulator qualification, not a new physical
hardware run. The cause of the earlier hardware boot hang is still unproven.

The fixed-address shell has 3,723 image bytes and a 368-byte BSS reservation
(360 actually used), leaving five bytes in its 4 KiB slot. All fixed public
gates, high-module ranges and the 8,000-byte VIC shadow remain unchanged.
`ush.udx`, its map, bootfs, kernel maps, stage 1 and RC are preserved here.
Previous artifacts, including the original failing disk, were not overwritten.
