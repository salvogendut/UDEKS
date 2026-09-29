; SPDX-License-Identifier: GPL-3.0-or-later
;
; Stack-independent one-shot veneer for service startup. Application slot 1
; is reused after hardware discovery, so a repeated call must return before
; compiled C adjusts or reads the currently active cc65 software stack.

        .setcpu "6502"

        .import _udeks_service_start_all_once
        .export _udeks_service_start_all

SERVICE_STATUS = $f090
SERVICE_STATE = SERVICE_STATUS + 5
SERVICE_READY = $02

        .segment "RODATA"
service_magic:
        .byte 'S', 'R', 'E', 'G'

        .segment "CODE"
_udeks_service_start_all:
        ldx #$03
check_magic:
        lda SERVICE_STATUS,x
        cmp service_magic,x
        bne start_services
        dex
        bpl check_magic
        lda SERVICE_STATE
        cmp #SERVICE_READY
        bne start_services
        lda #$00
        tax
        rts

start_services:
        jmp _udeks_service_start_all_once
