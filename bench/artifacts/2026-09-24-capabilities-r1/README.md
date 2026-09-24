# Hardware-capability boot artifact

`udeks.d71` is the exact production image used to qualify hardware-capability
service revision 1 across PAL/NTSC, 16/64 KiB VDC RAM, REU, and GeoRAM emulator
profiles.

The image is immutable evidence. Build the current development disk with
`make boot`, and validate this artifact with:

```sh
sha256sum -c SHA256SUMS
```
