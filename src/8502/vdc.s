; SPDX-License-Identifier: GPL-3.0-or-later
;
; Bounded low-level transport for the 8563/8568 indirect register port.

        .setcpu "6502"

        .export _udeks_vdc_select
        .export _udeks_vdc_write_selected
        .export _udeks_vdc_read_selected
        .export _udeks_vdc_status

VDC_ADDRESS             = $d600
VDC_DATA                = $d601
VDC_OK                  = $00
VDC_TIMEOUT             = $01

        .segment "BSS"
_udeks_vdc_status:
        .res 1
vdc_argument:
        .res 1

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
