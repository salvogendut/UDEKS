# Four-native cutover artifacts

Exact boot disks and independent flag-0 UDEX 0.2 applications qualified by
`bench/results/2026-10-05-four-native`. `layout.json` contains actual source
and input hashes, allocation bounds and the two delivery/runtime lifetimes.
The normal and panic resident maps agree. `HELLO.BIN` is independently built
without linking the OS; the probe adds identical copies under arbitrary names.

The complete build source is the enclosing commit; reproduction and qualification
scope are recorded in the results README. Do not replace older evidence or
the published top-level build snapshots with these files implicitly.
