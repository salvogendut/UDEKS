# Context-switch spike artifact r5

`context-switch.prg` is the standalone spike image qualified on 2026-09-26 on
the `tasking-0.1` branch. It supersedes `-r4` by adding a screen readout for
physical-hardware capture: after the result is final, the 32-byte record is
printed as four lines of 16 hex characters on the 40-column VIC screen and the
80-column VDC screen before the halt.

The switch core runs from `$F400` in common RAM (reserved to `$FEFF`) so the
readout fits below the MMU register page; the `CXSW` result block remains at
`$F180`. It loads at `$2800`, enables top common RAM, and transfers to the
core.

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
