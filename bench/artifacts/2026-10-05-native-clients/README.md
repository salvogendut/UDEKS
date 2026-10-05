# Published native-client build — 2026-10-05

Exact boot disks published as the top-level `build/` snapshots from merged
main `799cc85`: the generic native-client cutover (PR #37), D81 boot support
and the `df -h` user command (PR #39). `udeks.d64`/`.d71`/`.d81` here are
byte-identical to `build/udeks.*`; the checksums also cover the resident map,
module and shipped user programs.

Feature qualifications live in
[2026-10-05-four-native](../2026-10-05-four-native/README.md) and
[2026-10-05-wave-resize](../2026-10-05-wave-resize/README.md) with their
`bench/results` records; the root-namespace kernel baseline remains the
[2026-09-30 record](../2026-09-30-root-namespace/README.md). Still an
experimental build, not a stable release.
