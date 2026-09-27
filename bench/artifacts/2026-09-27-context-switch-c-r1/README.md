# Compiled-C context-switch artifact r1

`context-switch-c.prg` is the exact standalone image qualified on 2026-09-27.
It was built with cc65 V2.18 (Fedora package 2.19-15.fc44) using the repository
rules and sources under `bench/context-switch-c`.

The image loads at `$2800` and enters at `$2806` (`SYS 10246`). It exercises
two real cc65 tasks for 64 context switches using the ADR 0008 relocated
page-zero/page-one strategy. Verify the preserved image with:

```sh
sha256sum -c SHA256SUMS
```
