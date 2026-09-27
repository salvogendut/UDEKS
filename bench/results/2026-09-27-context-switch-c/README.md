# Compiled-C context-switch results

The r1 integration spike passed byte-identically in `1986` revision `4867cf2`
and VICE 3.10 at both 1 MHz and 2 MHz. Every run reports:

- `UCCS` format 1, 8502, complete with failure 0;
- 64 context switches and task progress 32/32;
- preserved C-local accumulators `$1444` and `$4741`;
- relocation strategy 2 and completion mask `$03`;
- restored cc65 software-stack pointers `$70F0` and `$71F0`;
- intact task-specific hardware and software-stack canaries.

Reproduction:

```sh
make bench-context-switch-c

# 1986
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ../1986/1986 --disk build/bench/context-switch-c/context-switch-c.prg \
  --paste 'BLOAD"*":SYS10246' --paste-at 180 --frames 400 --no-throttle \
  --save-snapshot /tmp/context-switch-c.vsf
python3 tools/snapshot_extract.py /tmp/context-switch-c.vsf /tmp/context-c.bin \
  --address 0xf1a0 --size 32
python3 tools/compiled_context_decode.py /tmp/context-c.bin

# VICE 3.10; add --fast for the 2 MHz repeat
python3 tools/vice_capture.py --raw-load --entry 0x2806 \
  --result-address 0xf1a0 --result-size 32 --state-offset 6 \
  --complete-value 2 build/bench/context-switch-c/context-switch-c.prg \
  /tmp/context-c-vice.bin
python3 tools/compiled_context_decode.py /tmp/context-c-vice.bin
```

The exact PRG is preserved under
`bench/artifacts/2026-09-27-context-switch-c-r1`.
