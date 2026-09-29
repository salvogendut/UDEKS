; SPDX-License-Identifier: GPL-3.0-or-later
; Diagnostic-only binding, measured but NOT admitted to the resident image.
        .setcpu "6502"
        .include "layout.inc"
        .export _private_cache_policy_call
        .segment "CODE"
_private_cache_policy_call:
        php
        sei
        lda #$00
        sta $f3ed
        ldx #$00
install:
        lda image,x
        sta RUN,x
        inx
        cpx #image_end-image
        bcc install
        ; Keep IRQ disabled from publication through map/lease restoration.
        jsr RUN
        plp
        rts
image:
        .incbin "build/bench/window-repaint-bank/gateway.bin"
image_end:
        .assert image_end-image < $100, error, "binding copy exceeds one page"
