# REU transport and capacity — standalone VICE qualification

This is **not an REU-backed UDEKS desktop**. It qualifies the private service
candidate and its standalone harness. No disk was mounted or altered; all
sessions opened by the runner were closed. No 1986 or physical-REU result is
claimed. Normal boot images and app allocation remain unchanged.
The complete host suite passes 1,707 tests. A fresh container `make -j8 boot
graphics-apps-check` passes; D64/D71/D81 SHA-256 hashes match the packed-bitmap
baseline respectively:

```text
2c094dd4b8d38d59edbb30126b78814a35059aca98582fb0efc0c9c15dfeed09
225a527af10d18c66c153c4c2d77de87ae1b55bcfbc033a5a1f29c0f327b6cae
f5d1ec2fb6f3a9c1ca81b31aed344bb5fc5e0884cf32fcebe376d88fe5bf9c03
```

| VICE REU configuration | Published usable prefix | Round trips | Checked transport calls | Rejections | Distinct banks / restored tags |
| --- | --- | --- | --- | --- | --- |
| none | none (`ENODEV`) | 0 | 1 | 0 | 0 / 0 |
| 128 KiB | 128 KiB | 128 | 271 | 8 | 2 / 2 |
| 256 KiB | 256 KiB | 128 | 277 | 8 | 4 / 4 |
| 512 KiB | 512 KiB | 128 | 289 | 8 | 8 / 8 |
| 1,024 KiB | 512 KiB | 128 | 313 | 8 | 16 / 16 |

The configured-capacity transport check deliberately visits every configured
bank. The **discovery function** only verifies the first eight banks and does
not infer full 1 MiB capacity from that. The checked-call count excludes its
internal calls; its return, published prefix and preserved seeded bytes are
independently checked by the harness.

`misbanked.prg` changes only the transport's bank-1 selector to bank 0. With
512 KiB attached it fails with code 10 (target data comparison); the positive
decoder rejects it. `tools/reu_probe.py` guards the patch's uniqueness.

## Artifacts and reproduction

- `probe.prg`, `probe.map`: exact linked positive program and map.
- `misbanked.prg`: exact negative-control program.
- `vice-*.bin`, `misbanked.bin`: raw 32-byte records at `$7000`.
- `*.log`: capture output for each owned VICE session.
- `report.json`: decoded results, raw records, Flatpak provenance, source and
  artifact SHA-256 hashes. `SHA256SUMS` covers the evidence files.

Run from the `graphics-reu` worktree:

```sh
distrobox-enter my-distrobox -- make -j8 reu-probe-build
python3 tools/reu_probe.py
make check
```

The probe is destructive to its declared scratch RAM and selected REU test
locations. **Never load it into an already-running UDEKS.** The capacity
routine itself restores its probe bytes on success; injected hardware errors
keep it offline and restoration cannot be guaranteed on a failed device.

See [the implementation plan and remaining integration gates](../../../docs/GRAPHICS-REU.md).
