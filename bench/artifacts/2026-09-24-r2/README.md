# Preserved benchmark PRGs — 2026-09-24 r2

This bundle supersedes `../2026-09-24/` for new measurements. The original
bundle remains immutable as historical input. VICE 3.10 exposed two harness
preconditions that `1986` had masked:

- the Z80 interrupt-service suite described IM1 but did not execute `IM 1`;
- running CIA timers were read low-byte then high-byte and could cross a
  256-tick boundary between reads.

Revision 2 explicitly selects Z80 IM1, samples running Timer A counters with a
stable high/low/high sequence, and stops Timer B before reading elapsed time.
These changes affect instrumentation, so results from the original bundle must
not be mixed numerically with r2 results.

Verify the exact images with:

```sh
cd bench/artifacts/2026-09-24-r2
sha256sum -c SHA256SUMS
```

| Files | Entry | Result block | Decoder |
|---|---:|---|---|
| `shared-c-8502.prg`, `shared-c-z80.prg` | `$2000`, `$1FE0` | `$F100`, 128 bytes | `tools/bench_decode.py` |
| `irq-entry-8502.prg`, `irq-entry-z80.prg` | `$2800`, `$27D0` | `$F180`, 128 bytes | `tools/irq_probe_decode.py` |
| `irq-service-8502.prg`, `irq-service-z80.prg` | `$2800`, `$27D0` | `$F180`, 320 bytes | `tools/irq_service_decode.py` |
| `context-8502.prg`, `context-z80.prg` | `$2800`, `$27D0` | `$F180`, 128 bytes | `tools/context_decode.py` |
| `kernel-8502.prg`, `kernel-z80.prg` | `$2000`, `$1FE0` | `$F180`, 128 bytes | `tools/kernel_decode.py` |
| `handoff-dual.prg` | `$27D0` | `$F180`, 64 bytes | `tools/handoff_decode.py` |
| `offload-dual.prg` | `$27D0` | `$F400`, 416 bytes | `tools/offload_decode.py` |

The standalone images remain pure machine-code PRGs. `tools/vice_capture.py`
creates a temporary BASIC `SYS` wrapper while leaving every payload byte at
its archived address. The two dual images already contain BASIC stubs and use
the runner's `--autostart` mode.

Do not replace files in this directory. A later harness change requires a new
bundle and a new result set.
