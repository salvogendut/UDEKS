; SPDX-License-Identifier: GPL-3.0-or-later
; Measured private resident binding candidate, NOT linked into UDEKS.
; Kernel-profile callers have validated/populated the common row parameters.
; Delivery of bank-1 CORE is deliberately NOT hidden inside this binding.
        .setcpu "6502"
        .include "layout.inc"
        .export _vic_cache_row_candidate
        .segment "CODE"
_vic_cache_row_candidate:
        php
        sei
        lda #$00
        sta $f3ed               ; every other VIC gateway may replace this one
        ldx #$00
install:
        lda image,x
        sta RUN,x
        inx
        cpx #image_end-image
        bcc install
        plp
        jmp RUN                 ; row_entry masks the complete worker interval
image:
        .incbin "build/bench/window-cache-overlay/gateway.bin"
image_end:
        .assert image_end-image < $100, error, "row gateway installer needs one page"
