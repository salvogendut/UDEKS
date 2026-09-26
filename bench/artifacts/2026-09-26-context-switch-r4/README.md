# Context-switch spike artifact r4

This revision was superseded by `../2026-09-26-context-switch-r5/`, which adds
a VIC and VDC hex readout so a physical C128 run can be captured from the
screen. It is kept as history.

`context-switch.prg` is the standalone spike image qualified on 2026-09-26 on
the `tasking-0.1` branch. It supersedes `-r3`: the context record now stores the
live stack pointer directly, and each resume label verifies the previous
marker and pad against the live stack page and pops the frame before preparing
the next yield. This proves a variable-depth stack frame survived the other
task's execution instead of being normalized to a fixed base.

It loads at `$2800`, enables top common RAM, copies the switch core to `$F800`,
and publishes the `CXSW` record at `$F180`.

Build provenance:

- `cc65-2.19-15.fc44` (`cc65`, `ca65`, and `ld65` report V2.18);
- GNU Make and Python 3.14.7;
- built with `make bench-context-switch`.

Qualification environment:

- `1986` revision `f9c6a24590c697c2978a0988616d8e683f6d2d69`;
- VICE 3.10 Flatpak `net.sf.VICE` commit
  `bbd997ea8cbf7e6ba06ff82136fd71069ce2011f93c006412bcda7bbde17e448`,
  `x128` machine, native disk image attached at power-on.

The checked-in image is immutable evidence; later builds are not assumed to be
byte-identical. Its hash is in `SHA256SUMS`.
