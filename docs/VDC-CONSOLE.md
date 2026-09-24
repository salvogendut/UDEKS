# VDC console service

The initial UDEKS display service is an 80-column text console split across the
microkernel boundary defined by ADR 0004.

`src/8502/vdc.s` is the assembly transport. It alone touches `$D600/$D601`,
polls the VDC ready bit with a bounded 65,536-iteration timeout, and exposes
three narrow C-callable operations: select a VDC register, write the selected
register, and read it.

`src/services/console/vdc_console.c` owns policy in C. It establishes display
and attribute bases, enables attributes, clears the 80×25 screen, converts the
banner text to VDC screen codes, and hides the cursor. It then reads the first
title character and its attribute back from independent VDC RAM.

Record format 2 changes the system-owned palette to the UDEKS default: black
foreground attribute `$00` on the yellow register-26 background `$0D`. The
decoder continues to accept preserved format-1 white-on-black qualification
records.

The service publishes a 24-byte `VCON` diagnostic record at `$F070`. State 2
means the screen and attribute readbacks both matched. Error states have bit 7
set and place the failing phase in byte 6. Validate a raw record or VSF with:

```sh
python3 tools/vdc_console_decode.py console.bin
python3 tools/vdc_console_decode.py run.vsf
```

This is a polled bring-up service. IRQ-safe serialization, output queues,
scrolling, cursor policy, terminal controls, and VDC-size detection remain
future service work.

The register and RAM-access sequences follow chapter 10 of the
[Commodore 128 Programmer's Reference
Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf).
