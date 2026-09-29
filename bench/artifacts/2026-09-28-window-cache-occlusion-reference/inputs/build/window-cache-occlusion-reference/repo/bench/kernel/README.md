# Kernel-primitives benchmark

This suite combines shared C policy workloads with purpose-written assembly
mechanisms:

- direct `switch` dispatch through four C syscall handlers;
- indirect function-table dispatch through the same handlers;
- 32 event-queue pushes and pops through an eight-entry ring;
- 128 same-state MMU configuration-register write/read checks;
- 128 CIA1 data-direction-register write/read checks;
- 128 VDC ready/select/read transactions using register 18.

The MMU and CIA cases write back the value they first read, so the machine state
does not change. The VDC case selects a read-only observation of the current
update-address high byte. Each assembly adapter returns the number of successful
transactions; the decoder rejects partial access, timer overflow, malformed
records, or incorrect C workload checksums.

```sh
make bench-kernel
python3 tools/kernel_decode.py run.vsf
```

The 8502 PRG loads at `$2000` and starts with `SYS 8192`. The Z80 PRG contains
an 8502 launcher at `$1FE0` and starts with `SYS 8160`. Results occupy 128 bytes
at `$F180` with `KPRM` magic.

The corrected suite has run in both VICE and `1986`. Display-pressure variants
and real-hardware runs remain required to qualify production policy and detect
hardware-specific reversals.
