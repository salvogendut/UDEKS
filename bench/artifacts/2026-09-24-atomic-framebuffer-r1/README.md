# Atomic framebuffer r1 artifact

`udeks.d71` is the exact native autoboot image used to qualify the first
atomic UDEKS boot renderer. It composes the complete 640x200 surface in system
RAM, blanks the VDC before modifying display memory, uploads all 16,000 bytes
through one bounded assembly loop, verifies the splash region, and reveals the
finished bitmap.

The resident 8502 kernel is 12,211 bytes with SHA-256
`65182927fe5d4b49637e537df6db8597eaf895d536cee74aada4b8cd6e293291`.
The D71 has SHA-256
`c5f2e8102d55f725e25d16ce93e983fdc6ba82a0382d4b50060a236595b7ab1c`.

Validate the preserved image with:

```sh
sha256sum -c SHA256SUMS
```
