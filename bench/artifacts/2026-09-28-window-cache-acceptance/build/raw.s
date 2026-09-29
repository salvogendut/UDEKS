; SPDX-License-Identifier: GPL-3.0-or-later
; No resident C runtime or BSS. Reinstall after every common-workspace user.
        .setcpu "6502"
        .include "layout.inc"
        .import _udeks_nmi_drain
        .export _cache_raw_call
        .segment "CODE"
_cache_raw_call:
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
        jsr _udeks_nmi_drain
        plp
        jmp RUN
image:
        .incbin "build/bench/window-cache-acceptance/gateway.bin"
image_end:
        .assert image_end-image < $100, error, "gateway needs wider copy"
