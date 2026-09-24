# Bounded Z80 worker service 0.1

The resident 8502 remains the UDEKS executive and grants the Z80 one
synchronous, bounded mailbox operation per lease. The CPUs do not run
concurrently. Input, display, interrupts, and device ownership remain on the
8502; the Z80 is admitted only for operations whose complete handoff cost and
failure surface are understood.

At native-disk boot, stage 1 installs the worker image in physical bank 1 at
`$2000-$3FFF`. The worker service confirms the `Z80!` loader marker, installs
two small Z80 gateways in common RAM, and submits a `NOP` self-test:

- `$FFED-$FFF4` resumes the C128 reset-time Z80 continuation, selects the
  worker-I/O profile (`$7E`), and jumps to `$2000`. It is used once.
- `$FFD0-$FFE1` selects the kernel-I/O profile (`$3E`), returns ownership to
  the 8502 through `$D505`, restores the worker profile on the next lease, and
  returns to the suspended Z80 caller.

The common return gateway is mandatory. Returning CPU ownership while bank 1
remains selected would resume the 8502 at the right logical program counter in
the wrong physical RAM bank.

`udeks_z80_submit()` publishes one ABI 0.1 mailbox request, transfers
ownership, and validates response state, status, and sequence. It is currently
synchronous because the C128 arbitration hardware stops the 8502 completely
while the Z80 owns the bus. There is no executive-side timeout capable of
recovering from a wedged worker; admitted Z80 operations therefore belong to
the trusted kernel and must have statically bounded paths.

Only `NOP` is admitted in this revision. It returns result zero. Unsupported
opcodes and malformed requests publish an error before returning ownership.
The worker does not enable interrupts or access devices.

The implementation assumes stock C128 Z80 timing. It does not enable or
depend on emulator-specific doubled/8 MHz modes. Emulator qualification must
keep `double_z80_frequency = 0` and `tinker = 0` where those controls exist.

## Diagnostic record

The 32-byte `ZWRK` record begins at `$F190` in top common RAM:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | ASCII magic `ZWRK` |
| 4 | 1 | Record format (`1`) |
| 5 | 1 | Offline (`0`), starting (`1`), ready (`2`), or error (`$80`) |
| 6 | 1 | Service error |
| 7 | 1 | Last opcode |
| 8 | 2 | Last sequence |
| 10 | 1 | Last mailbox status |
| 11 | 1 | Boot self-test result |
| 12 | 2 | Successful transactions |
| 14 | 2 | Failed transactions |
| 16 | 2 | Mailbox ABI major/minor |
| 18 | 1 | Worker image staged |
| 19 | 1 | Common gateways installed |
| 20 | 1 | Timing policy (`1` = stock) |
| 21 | 1 | Last mailbox state |
| 22 | 10 | Reserved |

The service is optional at the registry level: a direct-loaded 8502 image can
remain usable without a staged bank-1 worker. A native disk boot that reaches
`READY` has completed one real 8502-to-Z80-to-8502 transaction.
