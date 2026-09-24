# UDEKS visual identity

The default UDEKS colour scheme is **black foreground on yellow background**.
It applies consistently to the boot splash, software-defined fonts, system
console, hardware-information screen, widgets, and text-mode fallback.

The canonical boot composition reference is `assets/bootscreen.png`: a pipe
logo rail on the left and a bordered system console on the right. The native
boot rail adds the Japanese UDEKS wordmark from `assets/udekusu-64.xpm`
directly below the pipe. Target
implementations preserve this hierarchy while adapting it to native resolution
and available font metrics.

On the VDC, black is colour index `$0` and yellow is `$D`. In monochrome bitmap
mode, register 26 is therefore `$0D`: set pixels use the black foreground and
clear pixels use the yellow background. In attribute text mode, cells use
foreground attribute `$00` over the same register-26 background.

Applications may request other colours through future surface and theme APIs,
but system-owned displays return to black-on-yellow by default. Contrast and
legibility on RGBI monitors and converters remain a real-hardware qualification
gate.
