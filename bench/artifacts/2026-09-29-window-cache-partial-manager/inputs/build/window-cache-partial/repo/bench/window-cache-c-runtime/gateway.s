; SPDX-License-Identifier: GPL-3.0-or-later
; Common-RAM gateway. Preserve all 26 published cc65 ZP bytes on hardware
; stack; no bank-0 instruction fetch, C, interrupt or callback in worker map.
        .setcpu "6502"
        .include "layout.inc"
        .export c_gateway, c_gateway_end
        .segment "GATEWAY"
c_gateway:
        php
        sei
        cld
        ldx #ZP_BYTES-1
save_zp:
        lda ZP_FIRST,x
        pha
        dex
        bpl save_zp
        lda #$00
        sta WORKER
        lda #<STACK_TOP
        sta ZP_FIRST
        lda #>STACK_TOP
        sta ZP_FIRST+1
        jsr DISPATCH
        lda ZP_FIRST
        sta RETURN_SP
        lda ZP_FIRST+1
        sta RETURN_SP+1
        lda #$00
        sta KERNEL
        ldx #$00
restore_zp:
        pla
        sta ZP_FIRST,x
        inx
        cpx #ZP_BYTES
        bcc restore_zp
        plp
        lda RESULT
        ldx #$00
        rts
c_gateway_end:
        .assert c_gateway = RUN, error, "private C gateway moved"
        .assert c_gateway_end < $f740, error, "C gateway reaches diagnostic IRQ"
