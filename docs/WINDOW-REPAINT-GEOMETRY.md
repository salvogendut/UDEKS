# Private 8502 damage-box primitive checkpoint

Issue #14, 2026-09-29. This is an isolated code-recovery experiment, **not
installed in the window manager or in a boot image**. It does not qualify a
bounded repaint adapter, input latency or physical hardware.

The title-row C specialization was measured first: 17 bytes saved. It was
discarded because it did not justify a second renderer. The retained candidate
replaces the existing `damage_set` and `damage_add` C bodies with two small
8502 routines in `bench/window-repaint-geometry/damage.s`. They take the
compact manager's eight-byte window value prefix in AX. No window title,
callback or persistent pointer is used. They use only cc65's caller-clobbered
`ptr1`/`ptr2` zero-page scratch and allocate no BSS, DATA, HIGHBSS or ZP.
The four damage-box variables remain in their original resident state.

The C bodies occupy 87 + 163 = 250 bytes; the assembled replacements occupy
169. Both full normal and panic sizing links recover exactly **81 CODE bytes**,
reducing the previous 1,012-byte growth to 931. The new linked resident helper
closure remains 72 bytes. All fixed ranges, HIGHBSS, and RODATA/DATA/BSS/shadow
sizes remain unchanged. This is an optimization of **still-used legacy
helpers**, not retirement of the bodies or a new provider. The prior 2,113-byte
retired-body/reserve allowance plus the measured 81-byte recovery is 2,194;
against the 2,371-byte current candidate component, the provisional deficit
is **at least 177 bytes**. Real call sites, admission, delivery, NMI, providers,
busy/teardown and their helper closures would increase it. Sizing links move
the shadow and retain stale bridges: **unbootable; never package them**.

The standalone PRG executes the actual assembly routines on 100 pairs of
rectangles and checks each result against separate C min/max and modular-add
arithmetic. Cases include 0, 255/256, screen-edge and 16-bit-wrap values. Both
1986 and Flatpak VICE pass. VICE initially exposed a diagnostic-only BSS-clear
omission; the final launcher clears BSS before C, and both fresh runs pass.
The record carries a version, completion state, first failure and case count;
the decoder rejects any corruption in its first 16 bytes. This proves the
arithmetic and the standalone call convention, **not actual manager call-site
integration**, interruption safety, mouse/keyboard behavior or speed.

`make repaint-geometry` builds the isolated normal/panic links and diagnostic.
The tool's `run --engine 1986` (reference container), `run --engine vice`
(Flatpak host) and `preserve` actions hash-bind the inputs, complete split
outputs, native PRG, emulator provenance and raw records. Evidence is under
`bench/{artifacts,results}/2026-09-29-repaint-geometry`. Preservation refuses
overwrite. The regular D64, D71 and kernel remain unchanged.

Next: recover the remaining deficit with fully measured real provider/caller
costs; do not count the other legacy helpers as retired while their users
remain. Then establish checksummed delivery, admission and serialized
private-stack/gateway ownership with NMI drainage in the restored kernel map.
Only a complete live adapter should lead to a manual test disk. Keep
xwave-specific optimization separate from the window manager.
