# Preserved benchmark PRGs — 2026-09-24

> **Historical r1 bundle:** VICE exposed a missing explicit `IM 1` in the Z80
> interrupt-service case and non-atomic reads of running 16-bit CIA timers.
> Keep these files for provenance, but use
> [`../2026-09-24-r2/`](../2026-09-24-r2/) for new measurements.

These are the exact benchmark images used for the initial `1986` result set.
They are deliberately checked in even though normal build output is ignored,
so later VICE and physical-C128 runs can execute identical bytes. Verify them
with:

```sh
cd bench/artifacts/2026-09-24
sha256sum -c SHA256SUMS
```

| Files | Start command | Result block | Decoder |
|---|---|---|---|
| `shared-c-8502.prg`, `shared-c-z80.prg` | `SYS 8192`, `SYS 8160` | `$F100`, 128 bytes | `tools/bench_decode.py` |
| `irq-entry-8502.prg`, `irq-entry-z80.prg` | `SYS 10240`, `SYS 10192` | `$F180`, 128 bytes | `tools/irq_probe_decode.py` |
| `irq-service-8502.prg`, `irq-service-z80.prg` | `SYS 10240`, `SYS 10192` | `$F180`, 320 bytes | `tools/irq_service_decode.py` |
| `context-8502.prg`, `context-z80.prg` | `SYS 10240`, `SYS 10192` | `$F180`, 128 bytes | `tools/context_decode.py` |
| `kernel-8502.prg`, `kernel-z80.prg` | `SYS 8192`, `SYS 8160` | `$F180`, 128 bytes | `tools/kernel_decode.py` |
| `handoff-dual.prg` | `RUN"*"` | `$F180`, 64 bytes | `tools/handoff_decode.py` |
| `offload-dual.prg` | `RUN"*"` | `$F400`, 416 bytes | `tools/offload_decode.py` |

The `SYS` addresses apply after loading each PRG at its embedded address with
the equivalent of `LOAD "*",8,1`. The two dual-CPU images contain BASIC 7.0
stubs and load/run atomically with `RUN"*"`.

Do not replace files in this directory when the harness changes. Create a new
dated directory, regenerate hashes, and record the source revision, toolchain,
machine configuration, and result-format version. That preserves comparable
historical inputs instead of silently moving the baseline.

The PRGs are GPL-3.0-or-later generated forms of the corresponding sources in
`bench/`. The preferred form for modification remains those source files.
