# Scheduler delivery installer measurement

Reclaim step 5 wants the protected `$F700-$F7FF` final installer to:

1. gather a scattered scheduler image into a temporary application slot before
   crt0 runs,
2. copy it into `$1C00-$1FFF` after crt0 returns, and
3. enter `_kernel_main` at `$2000`.

`scatter.s` is the minimal self-contained implementation of those two
routines: a manifest parser plus per-chunk copy loop, and a 1,024-byte
page-copy plus entry jump. `scatter.cfg` links it at `$F700` to measure the
exact code size.

## Reproduction

```sh
distrobox enter my-distrobox -- sh -c \
  "ca65 --cpu 6502 -o scatter.o scatter.s && \
   ld65 -C scatter.cfg -o scatter.bin scatter.o"
```

Output:

```text
gather=97 install=35 total=132
```

The current FINAL segment ends at `$F7CD` (206 of 256 bytes used), leaving 50
bytes before the `$F800` boundary, so the delivery logic exceeds the protected
page by **82 bytes**. The increment stops there; the installer must not spill
into `$F800` or another live region.
