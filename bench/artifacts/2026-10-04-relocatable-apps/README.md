# Slot-independent C execution — 2026-10-04

Issue #35 / `graphics-generic-apps`, working-tree checkpoint based on `9af159b`.
This is the relocation milestone, **not** generic shell dispatch or a completed
graphics SDK. No new app-name entry was added to the OS.

`relocapp.udx` is one UDEX 0.2 executable (1,175 file bytes, 963 image, 7 BSS,
97 high-byte patches). `probe.o65` and `probe.map` preserve the source of its
compiler-authored fixups. `oracle-2300.udx` and `oracle-3500.udx` are independent
flat links of the same objects, used only as test oracles, not distributed app
variants. The loader installs this one file in both native task allocations.

`udeks.d64`/`.d71` are the normal boot images. `reloc-test.*` add the same
`RELOCAPP.BIN` and disposable malformed/fixed-image fixtures to those images.
`native-test.d64` adds the 1986 harness's EMPTY/ONE fixtures. No fixture was
added to the normal disks or the published root `build/udeks.*` snapshots.

The three loader outputs and map record the exact reservation split:
CODE `$D900-$DFFA`, RELOC `$1880-$19ED`, ACCESS `$1F00-$1F69`.
Related source: `src/services/app/banked_loader.s`,
`tools/o65_to_udex.py`, `tools/build_reloc_fixture.py`,
`user/probes/banked_client.c`, `user/probes/reloc_split.s`.

Build in `my-distrobox` with cc65/ld65 V2.18 (Fedora cc65 2.19-15.fc44):

```sh
make -j8 boot graphics-apps-check placement-check reloc-fixtures
```

VICE 3.10 Flatpak and unmodified 1986 `81485cc7` evidence is preserved under
`bench/results/2026-10-04-relocatable-apps`. Physical C128 has not yet tested
this change. SHA256SUMS locks these exact files.
