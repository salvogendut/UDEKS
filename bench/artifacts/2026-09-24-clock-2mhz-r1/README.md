# VDC-only 2 MHz comparison artifacts

This bundle preserves the exact native autoboot images used for the `1986`
before/after comparison:

- `udeks-1mhz.d71` is commit `a5e444d` with the pipe and Japanese wordmark,
  before the clock service. Its 11,964-byte kernel has SHA-256
  `8cd27801bb98f1292537723c0596d2adea175169ac8da89347b45c670c0ea982`.
- `udeks-2mhz.d71` adds the ordered VIC blanking and verified `$D030`
  transition. Its 12,134-byte kernel has SHA-256
  `0d8f6c76780c45c5312aaa3ecc79dc4d212acce9e48fc2274f52ed78644805e1`.

Validate both images with:

```sh
sha256sum -c SHA256SUMS
```
