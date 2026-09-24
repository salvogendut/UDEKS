# Panic-path boot artifacts

`udeks.d71` is the production image used to check that normal registry and
console startup still succeed after panic integration.

`udeks-panic-probe.d71` differs only in the first byte of the statically linked
console descriptor magic (`XSVC` instead of `USVC`). It is a deliberate
qualification fixture: the registry rejects it and the kernel enters panic
code `$22`. It must not be distributed as a normal boot image.

The images are immutable evidence. Rebuild their current equivalents with
`make boot panic-probe`, and validate these artifacts with:

```sh
sha256sum -c SHA256SUMS
```
