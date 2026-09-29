; SPDX-License-Identifier: GPL-3.0-or-later
; No resident C runtime or BSS. Reinstall after every common-workspace user.
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
        plp
        jmp RUN
image:
        .incbin "build/bench/window-cache-controller/gateway.bin"
image_end:
        .assert image_end-image < $100, error, "gateway needs wider copy"
