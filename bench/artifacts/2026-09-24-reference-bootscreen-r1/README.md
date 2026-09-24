# Reference-style bootscreen r1 artifact

`udeks.d71` is the exact native autoboot image used to qualify the 640x200 VDC
adaptation of `assets/bootscreen.png`, including its logo rail, full-height boot
console, extended punctuation glyphs, aligned status fields, prompt, and cursor.

The resident 8502 kernel is 11,227 bytes with SHA-256
`c3da103cf1ce88b9c40d705098a78b460d2e66fd9999559718b3be8c811a994e`.
Run `make boot` and validate the preserved disk with:

```sh
sha256sum -c SHA256SUMS
```
