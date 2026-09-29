; SPDX-License-Identifier: GPL-3.0-or-later
; Serialized private lease. No I/O, callbacks, IRQ, scheduler or nested call
; while worker FLAT is selected. RESTORE's production common stub is separate.
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
        .assert c_gateway = RUN, error, "gateway moved"
        .assert c_gateway_end < $f740, error, "gateway reaches diagnostic IRQ"
