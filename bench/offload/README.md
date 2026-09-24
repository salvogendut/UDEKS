# End-to-end offload crossover benchmark

This suite determines when work delegated to the C128's other processor repays
the fixed mailbox and ownership-transfer cost. It measures both possible
executive arrangements over 16, 32, 64, 128, 256, 512, 1,024, and 2,048-byte
buffers:

- 8502 local execution versus a complete 8502-to-Z80 request;
- Z80 local execution versus a complete Z80-to-8502 request.

The three handwritten-assembly operations are `COPY`, unsigned `CHECKSUM16`,
and `XOR_ROL`. The last writes `ROL8(source[i] XOR $A5)` to the destination.
They use the provisional mailbox opcodes documented in `abi/mailbox.md`.

Local intervals contain the operation call and implementation. Delegated
intervals start before request encoding and end after ownership returns and the
requester validates mailbox state, status, sequence, and result. Buffer/result
checksum validation occurs after the timer stops in both paths, so verification
cannot make a deliberately incomplete operation appear faster.

## Memory and result contract

The dual-CPU PRG uses this provisional common-RAM layout:

| Range | Purpose |
|---|---|
| `$2800-$2FFF` | fixed 2 KiB 8502 controller window |
| `$3000-$37FF` | fixed 2 KiB Z80 controller window |
| `$C000-$C7FF` | deterministic source buffer |
| `$C800-$CFFF` | destination buffer |
| `$EFF0` downward | Z80 stack |
| `$F000-$F03F` | normative mailbox ABI |
| `$F080-$F08F` | private benchmark control |
| `$F400-$F59F` | 416-byte `XOFS` result block |

Every result record contains all four timings, independent expected and actual
checksums, and one validation bit per path. The decoder rejects incomplete
runs, timer overflow, malformed record order, partial validation, or checksum
errors.

The PRG loads at BASIC 7.0's `$1C01` and runs with `RUN"*"`. A green VIC border
means all 96 timed paths completed and validated; red means a self-check or
protocol failure. This signal remains useful when the selected display is VDC.

## Build and run under `1986`

```sh
make bench-offload

SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
C128_CONFIG_PATH=bench/handoff/1986-stock.conf \
../1986/1986 --rom ../1986/roms \
  --disk build/bench/offload/8502/offload.prg \
  --paste 'fast:run"*"' --paste-at 100 --frames 900 --no-throttle \
  --save-snapshot /tmp/udeks-offload-2mhz.vsf

python3 tools/offload_decode.py /tmp/udeks-offload-2mhz.vsf
```

Use `--paste 'run"*"'` and 1,000 frames for the 1 MHz run. The configuration
explicitly keeps `double_z80_frequency = 0` and `tinker = 0`; the result block
also records the observed 8502 speed. Z80 timing is not discoverable by target
code and must therefore be recorded externally.

## VICE and physical C128 capture

Use the archived PRG under `bench/artifacts/2026-09-24/` so a comparison runs
the exact tested bytes. In VICE, load and run the PRG in C128 mode with stock
Z80 timing, then save `$F400-$F59F` as a 416-byte binary block or take a
snapshot from which that bank-zero range can be extracted. The decoder accepts
a bare block with no offset option, a 64 KiB memory image, or a `1986` VSF.
VICE snapshot-module support will be added when the independent run is made.

On real hardware, run the same PRG from disk or SD storage, wait for the green
border, and capture exactly `$F400-$F59F` with a monitor cartridge, debugger,
or later UDEKS result-dumper. Record machine model, PAL/NTSC, selected display,
VDC RAM, accelerator state, and 8502 speed with the captured block. Do not
treat emulator agreement as hardware confirmation.
