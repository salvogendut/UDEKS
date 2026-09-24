# VDC console boot artifact

`udeks.d71` is the exact native disk used to qualify the first modular UDEKS
service: an assembly VDC transport with a C 80-column console implementation.
It writes the UDEKS bring-up banner and verifies screen and attribute RAM by
reading them back through the VDC.

The image is immutable evidence. Build the current development disk with
`make boot`, and validate this artifact with:

```sh
sha256sum -c SHA256SUMS
```
