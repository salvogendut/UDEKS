# Service-registry boot artifact

`udeks.d71` is the exact native disk used to qualify UDEKS service-module ABI
0.1. It contains the generic C registry, the linker-visible static module table,
and the VDC console's compiler-neutral descriptor.

The image is immutable evidence. Build the current development disk with
`make boot`, and validate this artifact with:

```sh
sha256sum -c SHA256SUMS
```
