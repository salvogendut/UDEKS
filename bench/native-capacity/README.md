# Generic larger-app qualification

These are independent UDEX 0.2 clients, not kernel-linked applications or
production boot-disk contents. `client.c` has 4,600 initialized data bytes and
submits drawing commands beyond the old allocation boundary. `console.c`
uses the same-sized zero-filled BSS instead, does bounded work without a
window, and returns normally. Both verify data, BSS and ongoing state.

Build in the reference container, then run VICE from the host:

```sh
distrobox-enter my-distrobox -- make -j8 boot native-capacity-fixtures graphics-apps-check placement-check
make native-capacity-probe
```

The three runs preserve disposable disks, captures, hashes and `result.json`
under `build/native-capacity/vice-{d64,d71,d81}`. D64/D71 test public shell
launch and coexistence; their nearly full first side does not have room for
the extra large rejection fixtures. D81 also exercises the actual private
loader through its normal root poll, before graphics owns that scratch area:

- Exact 7,168-byte image and image+BSS, exact 7,424-byte file, one-byte excess.
- Malformed relocation and failed-open rollback; whole request preservation.
- Donor load/activate/release/reap rejection while loaned; no donor writes.
- An owned but not activated neighbour prevents joining.
- A large relocation tail with a small installed image releases the donor.
- Large graphical and windowless C clients, guarded relocated C/CPU stacks,
  effective drawing-source bounds, three-client coexistence, normal exit and
  four-small-client reuse. No app-name whitelist or slot chosen by the client.

Native 1986, compiled in the container against the **unmodified** sibling:

```sh
distrobox-enter my-distrobox -- python3 tools/1986_storage_smoke_build.py \
  --native-capacity --emulator /var/home/salvogendut/Dev/1986 \
  --roms /var/home/salvogendut/Dev/1986/roms \
  --disk build/boot/udeks.d64 --drive 1571 \
  --output build/native-capacity/1986-d64-final
```

This types commands and drives the real 1351/keyboard APIs: four window
drags, console after mouse use, rejected fourth client while joined, release,
four small clients, windowless natural return, graphical Ctrl+C, then the
four bundled apps and their ordinary stack guards. No application/request
or lifecycle state is injected. Output has the disk hashes and emulator rev.

2026-10-07: all three VICE formats pass; native 1986 `19386ef8` D64/1571
passes. LARGE measures 5,467 file / 5,343 image+BSS; BIGCON 402 / 4,950.
Host tests: 1,347; actual-build layout gates pass. Physical C128 acceptance
of this capacity extension is still pending.

Probe corrections and scope: VICE physical-page checks use `bank ram01`,
verified through the monitor bank list, rather than an MMU-aliased CPU read.
`ram1` is **not** a valid bank name in the installed VICE. The first native
console fixture only slept indefinitely and did not honor cooperative close;
it was replaced by bounded work. This gate does not claim forced cancellation,
interactive stdin/argv, or expansion of the old synchronous console pool.
Only the `*-final` native result and latest complete VICE results qualify;
earlier failed diagnostic directories under build are not acceptance records.
