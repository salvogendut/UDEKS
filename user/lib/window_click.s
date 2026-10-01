; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .export _udeks_window_take_click
        .segment "CODE"
_udeks_window_take_click:
        pha
        lda $cf54
        bne unsupported
        lda $cf55
        cmp #4
        bcc unsupported
        pla
        jmp ($cf5a)
unsupported:
        pla
        lda #0
        tax
        rts
