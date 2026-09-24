# Task-context save/restore benchmark

This suite measures four 64-iteration round-trip primitives, with eight raw
samples per configuration:

1. `empty`: call/return and loop calibration;
2. `cpu_core`: the CPU state used by generated C plus call-stacked PC and saved
   hardware SP;
3. `compiler`: all state required to preempt generated C at an arbitrary
   instruction;
4. `full`: all application-visible state admitted by the proposed UDEKS task
   ABI.

For the 8502, core state is P/A/X/Y, PC, and SP. The compiler and full paths
also copy all 26 bytes that cc65 declares as its zero-page runtime state,
including `sp`, `sreg`, pointers, temporaries, and the register bank. The
resulting provisional task context is 33 bytes, excluding the task's separate
C stack and the inactive portion of its hardware-stack allocation.

For the Z80, SDCC's compiler state is primary AF/BC/DE/HL plus IX, IY, PC, and
SP. The full path additionally preserves AF'/BC'/DE'/HL'. Its context sizes are
16 and 24 bytes. I, R, IFF, and interrupt mode are kernel-global under this
benchmark contract rather than task-local state.

The primitives store and reload the same context. This has the same transfer
cost as saving one runnable task and restoring another while allowing direct
register qualification without introducing a scheduler. Timings use CIA1
Timer B and exclude timer setup and result reporting through empty-loop
subtraction.

```sh
make bench-context
python3 tools/context_decode.py run.vsf
```

The 8502 PRG starts with `SYS 10240`; the Z80 launcher starts with `SYS 10192`.
The 128-byte `CTXB` result block begins at `$F180`.
