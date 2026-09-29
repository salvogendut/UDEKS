# Bidirectional CPU-handoff benchmark

This suite measures the C128's real MMU ownership path in both directions. It
runs four cases, each for 64 round trips:

1. 8502 requester, bare ownership transfer;
2. 8502 requester, complete mailbox ABI transaction;
3. Z80 requester, bare ownership transfer;
4. Z80 requester, complete mailbox ABI transaction.

A round trip contains two writes to MMU register `$D505`: the requester gives
the bus to its peer and the peer returns it. The bare cases perform only the
minimum dispatch and a validated peer counter. The mailbox cases fill and
publish an ABI 0.1 NOP request, validate it on the peer, publish a response,
and validate the sequence and result after ownership returns. Subtracting the
bare time from the mailbox time isolates protocol work above arbitration.

CIA1 Timer B counts one-megahertz system ticks continuously while ownership
moves between processors. The result header records whether the 8502 ran at 1
or 2 MHz. The Z80 result is valid only with stock timing: two T-states per
system tick, `double_z80_frequency = 0`, and `tinker = 0`.

The PRG loads at BASIC 7.0's `$1C01` and contains a one-line `SYS 10192` stub,
so it can be loaded and started with `RUN"*"`. The machine-code image begins at
`$27D0`, makes the bottom and top 16 KiB common, starts its 8502 controller at
`$2800`, and wakes its Z80 peer at `$3000`. It uses the normative 64-byte
mailbox at `$F000`, private control bytes at `$F170`, and a 64-byte `HNDF`
result block at `$F180`.

```sh
make bench-handoff
python3 tools/handoff_decode.py run.vsf
```

The checked-in `1986-stock.conf` explicitly disables the Z80 accelerator and
Tinker mode. A headless 1 MHz run can be captured with:

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
C128_CONFIG_PATH=bench/handoff/1986-stock.conf \
../1986/1986 --rom ../1986/roms \
  --disk build/bench/handoff/8502/handoff.prg \
  --paste 'run"*"' --paste-at 100 --frames 500 --no-throttle \
  --save-snapshot /tmp/udeks-handoff-1mhz.vsf
```

Use `--paste 'fast:run"*"'` for the 2 MHz 8502 run. The result decoder also
checks the speed recorded by the payload, so a mislabeled run is visible.

The benchmark deliberately provides no timeout once ownership has moved. That
matches the architectural constraint: a stuck active processor cannot be
preempted by its inactive peer. Emulator agreement and real-hardware runs are
required before these figures influence the executive decision.
