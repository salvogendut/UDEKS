# Backed framebuffer API r1 artifact

`udeks.d71` is the exact native autoboot image used to qualify the first
owned framebuffer API, system-RAM backing surface, disjoint dirty-span flush,
software text, and graphics-primitive-drawn console viewport.

The resident 8502 kernel is 10,134 bytes with SHA-256
`af0422a2e60432257ec0d819a4b76801f76af533b4c69a32db73bb426b5394ed`.
Run `make boot` and validate the preserved disk with:

```sh
sha256sum -c SHA256SUMS
```
