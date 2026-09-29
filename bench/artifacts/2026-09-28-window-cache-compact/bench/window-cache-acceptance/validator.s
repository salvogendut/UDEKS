; SPDX-License-Identifier: GPL-3.0-or-later
; Trusted kernel-sourced common code, NOT part of the unvalidated module.
; One bounded page per call; no C, ZP, software stack or callbacks.
        .setcpu "6502"
        .include "layout.inc"
        .include "acceptance.inc"
        .segment "GATEWAY"
validator:
        lda #$00
        sta WORKER
        ldx #$0f
header:
        lda $5210,x
        cmp expected_header,x
        bne bad
        dex
        bpl header
        clc
        lda PARAM
        adc #>CORE
        sta read+2
        ldy #$00
scan:
read:
        lda CORE,y
        clc
        adc PARAM+1
        sta PARAM+1
        bcc :+
        inc PARAM+2
:
        iny
        cpy PARAM+3
        bne scan
        lda #$00
        beq finish
bad:
        lda #$ff
finish:
        sta RESULT
        sta KERNEL
        rts
expected_header:
        CACHE_EXPECTED_HEADER
validator_end:
        .assert validator = RUN, error, "validator moved"
        .assert validator_end <= PARAM, error, "validator reaches parameters"
        .assert validator_end-validator < $100, error, "validator copy needs wider loop"
