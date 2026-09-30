; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .import _udeks_storage_dispatch, __BSS_RUN__, __BSS_SIZE__
        .segment "STARTUP"
entry:
        jmp dispatch
        .byte "UIEC", 0, 1
dispatch:
        lda initialized
        bne ready
        ldx #0
        lda #0
clear:
        sta __BSS_RUN__,x
        inx
        bne clear
        ldx #$80
clear_high:
        dex
        sta __BSS_RUN__+$100,x
        bne clear_high
        inc initialized
ready:  jmp _udeks_storage_dispatch
        .assert entry = $1200, lderror, "storage entry moved"
        .assert __BSS_RUN__ = $e000, lderror, "storage BSS moved"
        .assert __BSS_SIZE__ > 0 .and __BSS_SIZE__ <= $180, lderror, "storage BSS reaches stack guard"
        .segment "DATA"
initialized: .byte 0
