# VDC console service

The initial UDEKS display service is an 80-column text console split across the
microkernel boundary defined by ADR 0004.

`src/8502/vdc.s` is the assembly transport. It alone touches `$D600/$D601`,
polls the VDC ready bit with a bounded 65,536-iteration timeout, and exposes
three narrow C-callable operations: select a VDC register, write the selected
register, and read it.

`src/services/console/vdc_console.c` owns policy in C. It establishes display
and attribute bases, enables attributes, clears the 80×25 screen with hardware
block fill, and renders the retained 64×21 root terminal into direct VDC text
cells. Dirty spans are the unit of later repaint, and registers 14/15 drive the
hardware cursor.

`tools/xpm_to_vdc_text.py` converts the pipe and Japanese wordmark into 8×8
tiles, deduplicates identical patterns, and adds six window-edge glyphs. The
current package contains 63 glyphs. They replace only codes `$80-$BE` in the
upper half of the already-active VDC character generator; the stock lower 128
characters remain available for ordinary console text. The boot layout uses
the logo rail at left and custom line-drawing cells around the root console.
Lowercase cells select the VDC's alternate character set through attribute
bit 7 while uppercase cells retain the primary set, so one row can display
mixed case without switching the console-wide character generator.

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

This is currently a polled service. The retained model already provides
scrolling and terminal controls; IRQ-safe serialization, output queues, and
multiple terminal handles remain future work. It deliberately owns the VDC
directly rather than depending on the C128 ROM screen editor.

The register and RAM-access sequences follow chapter 10 of the
[Commodore 128 Programmer's Reference
Guide](https://www.pagetable.com/docs/Commodore%20128%20Programmer%27s%20Reference%20Guide.pdf).
