# VDC pipe-logo r1 artifact

`udeks.d71` is the exact native autoboot image used to qualify the compact
64x64 UDEKS pipe bootsplash at the upper right of the VDC framebuffer.

The resident 8502 kernel is 6,862 bytes with SHA-256
`d19b1da347325974cb0430643b02943faa5ce10b3424b8fced2330a9a4eb9de4`.
Run `make boot` and validate the preserved disk with:

```sh
sha256sum -c SHA256SUMS
```
