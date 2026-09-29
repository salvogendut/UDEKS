; SPDX-License-Identifier: GPL-3.0-or-later
;
; Bounded low-level transport for the 8563/8568 indirect register port.

        .setcpu "6502"

        .export _udeks_vdc_select
        .export _udeks_vdc_write_selected
        .export _udeks_vdc_read_selected
        .export _udeks_vdc_write_block
        .export _udeks_vdc_status
        .export _udeks_vdc_block_source
        .export _udeks_vdc_block_address
        .export _udeks_vdc_block_length

VDC_ADDRESS             = $d600
VDC_DATA                = $d601
VDC_REG_UPDATE_HI       = $12
VDC_REG_UPDATE_LO       = $13
VDC_REG_DATA            = $1f
VDC_OK                  = $00
VDC_TIMEOUT             = $01

        .segment "BSS"
_udeks_vdc_status:
        .res 1
vdc_argument:
        .res 1
_udeks_vdc_block_source:
        .res 2
_udeks_vdc_block_address:
        .res 2
_udeks_vdc_block_length:
        .res 2

        .segment "ZEROPAGE"
vdc_block_source_zp:
        .res 2

        .segment "CODE"

; Carry set means ready. The 16-bit counter bounds a missing/wedged VDC.
vdc_wait_ready:
        ldx #$00
        ldy #$00
wait_loop:
        bit VDC_ADDRESS
        bmi ready
        inx
        bne wait_loop
        iny
        bne wait_loop
        clc
        rts
ready:
        sec
        rts

_udeks_vdc_select:
        sta vdc_argument
        jsr vdc_wait_ready
        bcc select_timeout
        lda vdc_argument
        sta VDC_ADDRESS
        lda #VDC_OK
        sta _udeks_vdc_status
        rts
select_timeout:
        lda #VDC_TIMEOUT
        sta _udeks_vdc_status
        rts

_udeks_vdc_write_selected:
        sta vdc_argument
        jsr vdc_wait_ready
        bcc write_timeout
        lda vdc_argument
        sta VDC_DATA
        lda #VDC_OK
        sta _udeks_vdc_status
        rts
write_timeout:
        lda #VDC_TIMEOUT
        sta _udeks_vdc_status
        rts

_udeks_vdc_read_selected:
        jsr vdc_wait_ready
        bcc read_timeout
        lda #VDC_OK
        sta _udeks_vdc_status
        lda VDC_DATA
        rts
read_timeout:
        lda #VDC_TIMEOUT
        sta _udeks_vdc_status
        lda #$00
        rts

; Copy one arbitrary system-RAM run into auto-incrementing VDC RAM. C fills
; the exported source, destination, and length words before calling. Register
; selection and destination setup happen once; only the mandatory bounded
; ready poll remains inside the byte loop.
_udeks_vdc_write_block:
        lda _udeks_vdc_block_length
        ora _udeks_vdc_block_length+1
        beq block_success
        lda _udeks_vdc_block_source
        sta vdc_block_source_zp
        lda _udeks_vdc_block_source+1
        sta vdc_block_source_zp+1

        lda #VDC_REG_UPDATE_HI
        jsr _udeks_vdc_select
        lda _udeks_vdc_status
        bne block_timeout
        lda _udeks_vdc_block_address+1
        jsr _udeks_vdc_write_selected
        lda _udeks_vdc_status
        bne block_timeout

        lda #VDC_REG_UPDATE_LO
        jsr _udeks_vdc_select
        lda _udeks_vdc_status
        bne block_timeout
        lda _udeks_vdc_block_address
        jsr _udeks_vdc_write_selected
        lda _udeks_vdc_status
        bne block_timeout

        lda #VDC_REG_DATA
        jsr _udeks_vdc_select
        lda _udeks_vdc_status
        bne block_timeout

block_next:
        ldx #$00
        ldy #$00
block_wait:
        bit VDC_ADDRESS
        bmi block_ready
        inx
        bne block_wait
        iny
        bne block_wait
        jmp block_timeout

block_ready:
        ldy #$00
        lda (vdc_block_source_zp),y
        sta VDC_DATA
        inc vdc_block_source_zp
        bne block_source_ready
        inc vdc_block_source_zp+1
block_source_ready:
        inc _udeks_vdc_block_address
        bne block_address_ready
        inc _udeks_vdc_block_address+1
block_address_ready:
        lda _udeks_vdc_block_length
        bne block_decrement_low
        dec _udeks_vdc_block_length+1
block_decrement_low:
        dec _udeks_vdc_block_length
        lda _udeks_vdc_block_length
        ora _udeks_vdc_block_length+1
        bne block_next

block_success:
        lda #VDC_OK
        sta _udeks_vdc_status
        rts

block_timeout:
        lda #VDC_TIMEOUT
        sta _udeks_vdc_status
        rts
