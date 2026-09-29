; SPDX-License-Identifier: GPL-3.0-or-later
; Diagnostic-only binding, measured but NOT admitted to the resident image.
        .setcpu "6502"
        .include "layout.inc"
        .export _private_repaint_policy_call
        .segment "CODE"
_private_repaint_policy_call:
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
        .incbin "/var/home/salvogendut/Dev/UDEKS/build/window-manager-bounded-repaint/build/window-repaint-raster/gateway.bin"
image_end:
        .assert image_end-image < $100, error, "binding copy exceeds one page"
