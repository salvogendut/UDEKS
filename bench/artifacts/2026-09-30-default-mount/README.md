# Default device-8 mount — 2026-09-30

Normal RC now executes `mount 8 /mnt` at boot. It does not start graphics;
`xclock &`, `xwave &` and disk utilities work at the first prompt without a
manual mount. Edit the ordinary DOS `RC` file to change startup policy.
Recovery ush skips RC and remains manually mountable.

`udeks.d64` and `udeks.d71` differ from `2026-09-30-bank-probe-fix` only in
RC's single sector: 62 changed bytes. Kernel, shell, applications, ABI and
placements are unchanged. `rc` preserves the exact script.

`udeks-boot-debug.d64` retains the boot messages of the last user-accepted
hardware image, with the same RC-only change. This is the recommended
replacement for that test disk. The normal build remains quiet at boot;
the earlier hardware hang's cause was not established by the successful retest.

VICE D64/D71 and native 1986 tests are preserved in the matching results
directory. The user accepted boot/apps on the preceding bank-probe diagnostic
image; do not describe that as a new physical test of this changed script.
