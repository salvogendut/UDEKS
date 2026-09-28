# Display-service span experiment — 2026-09-28

Standalone C-reference/ASM-span qualification only. See
`docs/GRAPHICS-SPAN.md` for implementation, limits and reproduction commands.

`build/` contains eight positive PRGs/maps, the dirty-flag negative-control PRG
and mutation metadata, generated C units and the full experimental link maps.
`sources/` contains exact fingerprinted inputs. The linked candidate is a budget
experiment, not a boot image: its unpadded shadow moved to `$A18A`.

The candidate saves 83 CODE + 3 BSS bytes (86 net), with unchanged library-helper
membership. No resident allocation, frozen ABI or current boot disk changed.
The exact PRGs are bound by build and run manifests to the corresponding raw
records under `bench/results/2026-09-28-graphics-span`.

`SHA256SUMS` covers qualified inputs/artifacts, not this explanatory README.
