# Boot-only capability relocation qualification

This evidence qualifies ADR 0009's relocation of the 967-byte hardware
capability service from the resident kernel into application slot 1 at
`$0200-$05C7`.

The qualified layout is:

- resident data ends at `$A894`;
- `VICSHADOW` is `$A895-$C7D4` (8,000 bytes);
- the capability image is staged at `$A895-$AC5B`;
- its 102-byte exact-copy/checksum installer is staged at `$AC5C-$ACC1`;
- the scheduler scatter manifest remains fixed at `$ACD9` and its current
  delivery ceiling is 634 bytes.

## Results

- VICE 3.10 cold boots from both D71 and D64 produce byte-identical valid
  `HCAP` records.
- On both disk formats, `$0200-$05C7` is byte-identical to the separately
  linked service plus its cleared one-byte BSS.
- On the D71 path, `xinit` and `xclock` overwrite slot 1. Calling the
  stack-independent service-start veneer again returns zero and leaves all
  968 live xclock bytes unchanged.
- 1986 revision `f9c6a24` cold-boots the same D71. Its `HCAP` record is
  byte-identical to both VICE records, its native boot-chain record is valid,
  and its initial slot-1 image matches the linked service plus cleared BSS.

`make capability-probe` reproduces the two VICE runs. The 1986 capture used:

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ../1986/1986 \
  --disk build/boot/udeks.d71 --frames 3000 --no-throttle \
  --save-snapshot /tmp/udeks-capability-final-1986.vsf
```

The exact final D71 used for the preserved 1986 record has SHA-256
`b3cf253c87ed6ced13f2cea4dfb3937f4b02d01f72c1e36e8f10968ad52efd6a`.

