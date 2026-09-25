; SPDX-License-Identifier: GPL-3.0-or-later
;
; C128 11-column keyboard matrix snapshot. Eight columns are selected through
; CIA1 port A and three C128-only columns through VIC-IIe register $D02F.

        .setcpu "6502"

        .export _udeks_keyboard_scan
        .export _udeks_keyboard_matrix
        .export _udeks_keyboard_caps
        .export _udeks_keyboard_display_80

CIA1_PRA                = $dc00
CIA1_PRB                = $dc01
CIA1_DDRA               = $dc02
CIA1_DDRB               = $dc03
VIC_KEYBOARD_SELECT     = $d02f
MMU_MODE                = $d505
CPU_PORT                = $0001

        .segment "RODATA"
scan_masks:
        .byte $fe, $fd, $fb, $f7, $ef, $df, $bf, $7f

        .segment "BSS"
_udeks_keyboard_matrix:
        .res 11
_udeks_keyboard_caps:
        .res 1
_udeks_keyboard_display_80:
        .res 1
saved_pra:
        .res 1
saved_ddra:
        .res 1
saved_ddrb:
        .res 1
saved_vic_select:
        .res 1

        .segment "CODE"

_udeks_keyboard_scan:
        ; A raster IRQ may become due between the C-level permission check and
        ; this routine.  Keep each short matrix scan atomic so it cannot alter
        ; the POT mux during the mouse conversion window.
        php
        sei
        lda CIA1_PRA
        sta saved_pra
        lda CIA1_DDRA
        sta saved_ddra
        lda CIA1_DDRB
        sta saved_ddrb
        lda VIC_KEYBOARD_SELECT
        sta saved_vic_select

        lda #$ff
        sta CIA1_DDRA
        sta VIC_KEYBOARD_SELECT
        lda #$00
        sta CIA1_DDRB

        ldx #$00
scan_standard:
        lda scan_masks,x
        sta CIA1_PRA
        ; Discard one sample after changing the selected matrix column. This
        ; provides settling time at 2 MHz before the value we publish.
        lda CIA1_PRB
        lda CIA1_PRB
        eor #$ff
        sta _udeks_keyboard_matrix,x
        inx
        cpx #$08
        bne scan_standard

        lda #$ff
        sta CIA1_PRA
        ldx #$00
scan_extended:
        lda scan_masks,x
        sta VIC_KEYBOARD_SELECT
        lda CIA1_PRB
        lda CIA1_PRB
        eor #$ff
        sta _udeks_keyboard_matrix+8,x
        inx
        cpx #$03
        bne scan_extended

        lda CPU_PORT
        and #$40
        bne caps_open
        lda #$01
        bne store_caps
caps_open:
        lda #$00
store_caps:
        sta _udeks_keyboard_caps

        lda MMU_MODE
        and #$80
        beq display_40
        lda #$01
        bne store_display
display_40:
        lda #$00
store_display:
        sta _udeks_keyboard_display_80

        ; Deselect all columns before restoring the caller's port state.
        lda #$ff
        sta CIA1_PRA
        sta VIC_KEYBOARD_SELECT
        lda saved_pra
        sta CIA1_PRA
        lda saved_ddra
        sta CIA1_DDRA
        lda saved_ddrb
        sta CIA1_DDRB
        lda saved_vic_select
        sta VIC_KEYBOARD_SELECT
        plp
        rts
