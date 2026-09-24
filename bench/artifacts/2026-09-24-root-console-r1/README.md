# Retained root-console r1 artifact

`udeks.d71` is the exact native autoboot image used to qualify the first
retained UDEKS root console. Boot content is constructed in a 64x21 text-cell
model, independently of the VDC pixels, then rendered into the established
black-on-yellow boot window.

The resident 8502 kernel is 11,765 bytes with SHA-256
`3e02e5c7444d43463f65f7128ecb1e05be87f6402c65b081e25a4da4a1a22159`.
Validate the preserved disk with:

```sh
sha256sum -c SHA256SUMS
```
