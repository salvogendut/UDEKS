# Four graphical applications — 2026-10-01 accepted candidate

Exact images from committed checkpoint `c05a011` on `graphics-four-apps`. Build with:

```sh
distrobox enter my-distrobox -- make -j8 boot graphics-apps-check placement-check
```

An independent clean source build reproduced both disks, calculator, drawing,
disk shell and graphics/loader outputs byte-for-byte. See the paired results
directory's `clean-result.json` and `layout.json` for hashes and measurements.

Cold boot device 8, then launch `xclock &`, `xwave &`, `xcalc &`, `xdraw &`.
Move clock left before launching the later apps to leave its title exposed.
Xdraw is a 6×4 click-to-toggle grid; C clears it. Try arithmetic, dragging,
closing/reloading each app, and console commands with all four present.
`xdraw -q`, then `xdraw` and Ctrl+C should stop only drawing. `xinit -q` closes
all four. The user confirms this candidate works on real hardware and
authorizes merging; the hardware report does not identify the machine variant,
drive, or disk format.

Calculator/drawing have separate bank-1 image, BSS, CPU pages, software stacks,
and retained drawing images. Clock/wave retain their bank-0 managed lifecycle.
Xdraw uses 1,477 image + 354 BSS bytes at `$3500`; calculator remains 3,912 + 412
at `$2300`. The paired `SHA256SUMS` covers disks and maps/modules.

VICE D64/1541 and D71/1571, native 1986 D64 input, 1,056 host tests and placement
checks pass, with real-hardware acceptance of these exact bytes recorded above.
