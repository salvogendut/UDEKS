; SPDX-License-Identifier: GPL-3.0-or-later
;
; Last-resort 8502 panic path. It publishes common-RAM diagnostics first, then
; makes one bounded best-effort attempt to display the panic code on the VDC.
; It neither calls C nor depends on the cc65 software stack.

        .setcpu "6502"
        .export _udeks_panic

PANIC_STATUS            = $f0b0
PANIC_STATE             = PANIC_STATUS+5
PANIC_CODE              = PANIC_STATUS+6
PANIC_VDC_FLAGS         = PANIC_STATUS+11
PANIC_STATE_PUBLISHED   = $02

MMU_CR                  = $ff00
MMU_MODE                = $d505
VDC_ADDRESS             = $d600
VDC_DATA                = $d601

        .segment "RODATA"
panic_text:
        ; Native VDC screen codes for "UDEKS PANIC ".
        .byte $15, $04, $05, $0b, $13, $20, $10, $01, $0e, $09, $03, $20
panic_text_end:

        .segment "CODE"

; __fastcall__ receives the eight-bit panic code in A and never returns.
_udeks_panic:
        sei
        pha

        lda #$00
        ldx #$0f
clear_status:
        sta PANIC_STATUS,x
        dex
        bpl clear_status

        lda #'P'
        sta PANIC_STATUS+0
        lda #'A'
        sta PANIC_STATUS+1
        lda #'N'
        sta PANIC_STATUS+2
        lda #'I'
        sta PANIC_STATUS+3
        lda #$01
        sta PANIC_STATUS+4
        pla
        sta PANIC_CODE
        php
        pla
        sta PANIC_STATUS+8
        lda MMU_CR
        sta PANIC_STATUS+9
        lda MMU_MODE
        sta PANIC_STATUS+10

        lda #$01
        sta PANIC_VDC_FLAGS

        ; Force display and update addresses to VDC RAM $0000.
        ldx #$0c
        lda #$00
        jsr panic_write_register
        bcc publish
        ldx #$0d
        lda #$00
        jsr panic_write_register
        bcc publish
        ldx #$12
        lda #$00
        jsr panic_write_register
        bcc publish
        ldx #$13
        lda #$00
        jsr panic_write_register
        bcc publish

        lda #$1f
        jsr panic_select_register
        bcc publish

        ldy #$00
text_loop:
        cpy #panic_text_end-panic_text
        beq write_code
        tya
        pha
        lda panic_text,y
        jsr panic_write_data
        pla
        tay
        bcc publish
        iny
        bne text_loop

write_code:
        lda PANIC_CODE
        lsr a
        lsr a
        lsr a
        lsr a
        jsr panic_nibble
        jsr panic_write_data
        bcc publish
        lda PANIC_CODE
        jsr panic_nibble
        jsr panic_write_data
        bcc publish
        lda #$03
        sta PANIC_VDC_FLAGS

publish:
        lda #PANIC_STATE_PUBLISHED
        sta PANIC_STATE
halt:
        jmp halt

; Convert a low nibble to a native VDC screen code.
panic_nibble:
        and #$0f
        cmp #$0a
        bcc decimal_digit
        sec
        sbc #$09
        rts
decimal_digit:
        ora #$30
        rts

; X is the register and A is the value. Carry reports success.
panic_write_register:
        pha
        txa
        pha
        jsr panic_wait_ready
        bcc register_select_failed
        pla
        sta VDC_ADDRESS
        jsr panic_wait_ready
        bcc register_data_failed
        pla
        sta VDC_DATA
        sec
        rts
register_select_failed:
        pla
register_data_failed:
        pla
        clc
        rts

; A is the register number. Carry reports success.
panic_select_register:
        pha
        jsr panic_wait_ready
        bcc select_failed
        pla
        sta VDC_ADDRESS
        sec
        rts
select_failed:
        pla
        clc
        rts

; A is the data byte. Carry reports success.
panic_write_data:
        pha
        jsr panic_wait_ready
        bcc data_failed
        pla
        sta VDC_DATA
        sec
        rts
data_failed:
        pla
        clc
        rts

; A full 16-bit wrap is the hard upper bound for an absent or wedged VDC.
panic_wait_ready:
        ldx #$00
        ldy #$00
wait_loop:
        bit VDC_ADDRESS
        bmi vdc_ready
        inx
        bne wait_loop
        iny
        bne wait_loop
        clc
        rts
vdc_ready:
        sec
        rts
