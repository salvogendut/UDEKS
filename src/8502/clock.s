; SPDX-License-Identifier: GPL-3.0-or-later
;
; Enter the C128's VDC-only 2 MHz operating state after VIC-based hardware
; discovery. This is a machine transition, so it remains an assembly mechanism
; behind a service descriptor rather than display-client policy.

        .setcpu "6502"
        .export _udeks_clock_start

VIC_CONTROL_1           = $d011
VIC_CLOCK               = $d030
CAPABILITY_STATE        = $f0c5
CLOCK_STATUS            = $f100

CLOCK_STARTING          = $01
CLOCK_READY             = $02
CLOCK_ERROR             = $80
CLOCK_ERROR_CAPABILITY  = $01
CLOCK_ERROR_VIC         = $02
CLOCK_ERROR_FAST        = $03

CLOCK_FLAG_VIC_BLANKED  = $01
CLOCK_FLAG_FAST_READBACK = $02
CLOCK_FLAG_CAPABILITY_READY = $04

        .segment "CODE"

_udeks_clock_start:
        lda #$00
        ldx #$0f
clear_status:
        sta CLOCK_STATUS,x
        dex
        bpl clear_status

        lda #'C'
        sta CLOCK_STATUS+0
        lda #'L'
        sta CLOCK_STATUS+1
        lda #'K'
        sta CLOCK_STATUS+2
        lda #'2'
        sta CLOCK_STATUS+3
        lda #$01
        sta CLOCK_STATUS+4
        lda #CLOCK_STARTING
        sta CLOCK_STATUS+5
        lda #$02
        sta CLOCK_STATUS+11

        lda CAPABILITY_STATE
        cmp #$02
        bne capability_failure
        lda #CLOCK_FLAG_CAPABILITY_READY
        sta CLOCK_STATUS+12

        ; Commodore documents that the VIC display must be blanked before
        ; selecting 2 MHz. Hardware discovery has already sampled its raster.
        lda VIC_CONTROL_1
        sta CLOCK_STATUS+9
        and #$ef
        sta VIC_CONTROL_1
        lda VIC_CONTROL_1
        sta CLOCK_STATUS+10
        and #$10
        bne vic_failure
        lda CLOCK_STATUS+12
        ora #CLOCK_FLAG_VIC_BLANKED
        sta CLOCK_STATUS+12

        ; Bit 0 selects 2 MHz. Bit 1 is the VIC-IIe test facility and must be
        ; clear during normal operation; preserve all other readback bits.
        lda VIC_CLOCK
        sta CLOCK_STATUS+7
        and #$fd
        ora #$01
        sta VIC_CLOCK
        lda VIC_CLOCK
        sta CLOCK_STATUS+8
        and #$03
        cmp #$01
        bne fast_failure
        lda CLOCK_STATUS+12
        ora #CLOCK_FLAG_FAST_READBACK
        sta CLOCK_STATUS+12

        lda #CLOCK_READY
        sta CLOCK_STATUS+5
        lda #$00
        rts

capability_failure:
        lda #CLOCK_ERROR_CAPABILITY
        bne publish_failure
vic_failure:
        lda #CLOCK_ERROR_VIC
        bne publish_failure
fast_failure:
        lda #CLOCK_ERROR_FAST
publish_failure:
        sta CLOCK_STATUS+6
        ora #CLOCK_ERROR
        sta CLOCK_STATUS+5
        lda CLOCK_STATUS+6
        rts
