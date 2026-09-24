# Native D71 boot artifact

`udeks.d71` is the exact first native-autoboot disk qualified on 2026-09-24.
It contains a C128 `CBM` boot sector, stage 1, the bank-0 8502 kernel, and the
bank-1 Z80 worker image.

Build the current development image with `make boot`. The checked-in image is
immutable evidence; later builds are not assumed to be byte-identical.

```sh
sha256sum -c SHA256SUMS
```
