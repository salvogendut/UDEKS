# VDC software-font r1 artifact

`udeks.d71` is the exact native autoboot image used to qualify the original
UDEKS 5x7 software font and the `HCAP`-backed hardware-information panel.

The resident 8502 kernel is 9,550 bytes with SHA-256
`064ea3b9677ab811723fa4b059e8e9ec08dfa692ae12f40ecabd910650c31f14`.
Run `make boot` and validate the preserved disk with:

```sh
sha256sum -c SHA256SUMS
```
