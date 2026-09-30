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
        ldx #<__BSS_SIZE__
        lda #0
clear:  dex
        sta __BSS_RUN__,x
        bne clear
        inc initialized
ready:  jmp _udeks_storage_dispatch
        .assert entry = $1200, lderror, "storage entry moved"
        .assert __BSS_SIZE__ > 0 .and __BSS_SIZE__ < 256, lderror, "storage BSS exceeds page"
        .segment "DATA"
initialized: .byte 0
