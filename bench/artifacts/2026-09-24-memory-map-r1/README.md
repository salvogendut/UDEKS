# Native MMU qualification artifact

`memory-map-8502.prg` is the exact direct-load C128 executable used for the
2026-09-24 MMU profile and page-relocation qualification run. It loads at
`$2800`, copies its 1,000-byte gateway to top common RAM at `$F800`, and writes
a 128-byte `MAPQ` result at `$F100`.

Build the equivalent development image with:

```sh
make bench-memory-map
```

The checked-in artifact is immutable evidence; a later development build is
not assumed to be byte-identical. Validate it with:

```sh
sha256sum -c SHA256SUMS
```
