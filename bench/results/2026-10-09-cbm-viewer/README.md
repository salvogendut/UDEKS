# Standalone CBM viewer — 2026-10-09

Branch `app-cbm-viewer`, based on main `fe26bf1`. No kernel/ABI changes.
`make xview` in `my-distrobox` builds the preserved 4,581-byte executable.
Its image is 3,821 bytes + 1,437 BSS: the existing joined slots 3/4 allocation.
The full host suite passes 1,640 tests, including the target C viewer/parser
with the actual native SDK and a mocked request gate. Normal `make boot`
images are byte-identical to main's published D64/D71/D81.

VICE x128 Flatpak qualification, using `tools/xview_probe.py`:

- `alex-1571`: ALEX, D71/1571 (app/data can allocate on side two).
- `alex-1581`: ALEX, D81/1581.
- `clockwork-1581`: CLOCKWORK, final two-picture D81/1581 demo.

All three runs exited successfully. Each cold-boots disposable media and tests
usage, absent files, version/trailing/padding errors, oversized/dense rejection,
file closure/reuse, background launch, drag, clock overlap/uncover, close box,
foreground Ctrl+C and cancellation during loading. Three exact bitmap captures
per run prove all 5,544 ALEX / 5,568 CLOCKWORK pixels match the converted source
at initial (24,18) and moved (54,48) origins. During each capture the kernel
shadow equalled the physical bank-1 VIC bitmap. Private code and stack guards
were checked. Neither demo/source media nor disposable test disk was modified
by the running viewer. All owned VICE processes were closed.

Inputs use the shell's keyboard queue; bounded pointer getter hooks drive the
real WM paths. This does not qualify physical keyboard/mouse hardware. No new
1986 or real C128/Pi1541 viewer result is claimed. It is cooperative; individual
IEC calls are still synchronous. One joined-slot viewer can run at a time,
plus compatible peers subject to the shared retained-image pool.

Preserved program/map/layout, reports, screenshots, three VIC bitmaps per run
and stack guards are covered by `SHA256SUMS`. Full disposable images/logs and
other live captures remain under `build/xview/probes/` in this worktree.
Reports contain exact program, source disk and private fixture hashes. Build
the source disk again with `tools/add_cbm_viewer.py`; probe fixtures then add
BAD/TRAIL/PAD/BIG/DENSE.CBM. The earlier ALEX runs had only ALEX on their source
demo disks; the final demos have both ALEX and CLOCKWORK. Existing DOS files
were compared byte-for-byte against main, and final packaging reproduced exactly.

Final user demo checksums:

```text
cf717dd0e28a35a6774e014eab032e318131a73f113e003f392950128172a0cf  build/xview/udeks-pictures.d71
ecfd1edc973bc83a54446685e6d780e58e2b2c6f3bd64e8b9d10e83ac9ccd09b  build/xview/udeks-pictures.d81
```

See [the format/demo guide](../../../abi/cbm.md) and [picture provenance and
conversion commands](../../../PICS/README.md). Manual acceptance precedes merge.
