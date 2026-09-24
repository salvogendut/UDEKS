; SPDX-License-Identifier: GPL-3.0-or-later

        .setcpu "6502"
        .export _udeks_splash_bitmap
        .export _udeks_splash_bitmap_end

        .segment "RODATA"
_udeks_splash_bitmap:
        .incbin "build/assets/udekspipe-64.vdc"
_udeks_splash_bitmap_end:
        .assert _udeks_splash_bitmap_end - _udeks_splash_bitmap = 512, error, "VDC splash size drift"
