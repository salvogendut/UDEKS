# VDC framebuffer r1 artifact

`udeks.d71` is the exact native autoboot image used for the first 640x200 VDC
framebuffer and UDEKS splash qualification. It contains the generated 3,200-byte
logo payload and the black-on-yellow system theme.

The resident 8502 kernel is 8,140 bytes with SHA-256
`f0601aa1482cd4b7a0fba3256fb560e96efdb4ebb8748dfe17a5e658a90494f3`.
Run `make boot` and validate the preserved disk with:

```sh
sha256sum -c SHA256SUMS
```
