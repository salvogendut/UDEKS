# UDEKS framebuffer client API 0.1

The initial framebuffer client API is a provisional cc65 C interface for the
resident 8502 environment. It is intentionally separate from the compiler-
neutral service descriptor ABI; a syscall/request representation follows once
task identities and scheduling exist.

Clients include `udeks/framebuffer.h` and use one global ownership lease:

```c
unsigned char udeks_framebuffer_acquire(void);
unsigned char udeks_framebuffer_release(void);
```

Acquisition returns `UDEKS_FRAMEBUFFER_NOT_READY` before successful display
startup and `UDEKS_FRAMEBUFFER_BUSY` while another client holds the lease.
Release performs a verified flush before relinquishing ownership. A failed
flush retains the lease so the client can retry or report the device error.

While holding the lease, a client may call:

```c
unsigned char udeks_framebuffer_plot(
    unsigned int x, unsigned char y, unsigned char set);
unsigned char udeks_framebuffer_hline(
    unsigned int x, unsigned char y, unsigned int width, unsigned char set);
unsigned char udeks_framebuffer_fill_rect(
    unsigned int x, unsigned char y, unsigned int width,
    unsigned int height, unsigned char set);
unsigned char udeks_framebuffer_draw_char(
    unsigned int x, unsigned char y, unsigned char character);
unsigned char udeks_framebuffer_draw_text(
    unsigned int x, unsigned char y, const unsigned char *text);
unsigned char udeks_framebuffer_flush(void);
```

Coordinates are pixels on a 640x200 one-bit surface. Zero clears a pixel and a
nonzero value sets it to the foreground colour. Spans, rectangles, glyphs, and
strings clip at the right and bottom edges; an origin outside the surface is a
successful no-op. Text uses the UDEKS 5x7 font in an 8x8 cell and advances by
eight pixels per character.

Drawing changes the 16,000-byte system-RAM backing surface, not VDC RAM
directly. A 2,000-byte bitmap tracks each changed byte independently, retaining
multiple disjoint spans on the same scanline. `flush` writes only contiguous
dirty spans through the bounded VDC transport, reads each byte back, and clears
the corresponding dirty bits only after successful comparison.

The bring-up kernel runs with interrupts disabled, so the first lease is a
simple global guard. The scheduler milestone must make acquisition atomic and
associate ownership with a task before concurrent clients are admitted.
