; SPDX-License-Identifier: GPL-3.0-or-later
;
; Establish the first VIC-IIe graphics surface in physical bank 1.  The copy
; gateway runs from top common RAM so it can change complete MMU profiles
; without fetching code from the bank being replaced.

        .setcpu "6502"
        .export _udeks_vic_graphics_enable
        .export _udeks_vic_graphics_disable
        .export _udeks_vic_pointer_set_x
        .export _udeks_vic_pointer_set_y

MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_WORKER_FLAT     = $ff04
MMU_RCR                 = $d506
CIA2_PRA                = $dd00
CIA2_DDRA               = $dd02
VIC_SPRITE0_X           = $d000
VIC_SPRITE0_Y           = $d001
VIC_SPRITE_X_MSB        = $d010
VIC_CONTROL_1           = $d011
VIC_SPRITE_ENABLE       = $d015
VIC_CONTROL_2           = $d016
VIC_SPRITE_Y_EXPAND     = $d017
VIC_MEMORY              = $d018
VIC_SPRITE_PRIORITY     = $d01b
VIC_SPRITE_MULTICOLOR   = $d01c
VIC_SPRITE_X_EXPAND     = $d01d
VIC_BORDER_COLOR        = $d020
VIC_BACKGROUND_COLOR    = $d021
VIC_SPRITE0_COLOR       = $d027

COMMON_GATEWAY          = $f800
VIC_SCREEN              = $5c00
VIC_BITMAP              = $6000
VIC_SPRITE              = $7fc0
VIC_SPRITE_POINTER      = $5ff8

        .segment "CODE"
_udeks_vic_graphics_enable:
        ldx #$00
copy_gateway:
        lda vic_gateway,x
        sta COMMON_GATEWAY,x
        inx
        cpx #vic_gateway_end-vic_gateway
        bne copy_gateway
        jsr COMMON_GATEWAY
        lda #$00
        rts

_udeks_vic_graphics_disable:
        lda VIC_SPRITE_ENABLE
        and #$fe
        sta VIC_SPRITE_ENABLE
        lda VIC_CONTROL_1
        and #$cf
        sta VIC_CONTROL_1
        lda MMU_RCR
        and #$bf
        sta MMU_RCR
        lda #$00
        rts

_udeks_vic_pointer_set_x:
        sta VIC_SPRITE0_X
        pha
        lda VIC_SPRITE_X_MSB
        cpx #$00
        beq pointer_x_low
        ora #$01
        bne pointer_x_store
pointer_x_low:
        and #$fe
pointer_x_store:
        sta VIC_SPRITE_X_MSB
        pla
        rts

_udeks_vic_pointer_set_y:
        sta VIC_SPRITE0_Y
        rts

vic_gateway:
        lda #>VIC_BITMAP
        sta COMMON_GATEWAY+(clear_bitmap-vic_gateway)+2
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        ldx #$20
        ldy #$00
        lda #$00
clear_bitmap:
        sta VIC_BITMAP,y
        iny
        bne clear_bitmap
        inc COMMON_GATEWAY+(clear_bitmap-vic_gateway)+2
        dex
        bne clear_bitmap

        lda #>VIC_SCREEN
        sta COMMON_GATEWAY+(clear_screen-vic_gateway)+2
        ldx #$04
        lda #$07
clear_screen:
        sta VIC_SCREEN,y
        iny
        bne clear_screen
        inc COMMON_GATEWAY+(clear_screen-vic_gateway)+2
        dex
        bne clear_screen

        ldx #$3e
copy_sprite:
        lda COMMON_GATEWAY+(sprite_data-vic_gateway),x
        sta VIC_SPRITE,x
        dex
        bpl copy_sprite
        lda #$ff
        sta VIC_SPRITE_POINTER

        lda #$00
        sta MMU_LCR_KERNEL_IO

        lda MMU_RCR
        ora #$40
        sta MMU_RCR
        lda CIA2_DDRA
        ora #$03
        sta CIA2_DDRA
        lda CIA2_PRA
        and #$fc
        ora #$02
        sta CIA2_PRA

        lda #$07
        sta VIC_BORDER_COLOR
        sta VIC_BACKGROUND_COLOR
        lda #$78
        sta VIC_MEMORY
        lda #$08
        sta VIC_CONTROL_2
        lda #$3b
        sta VIC_CONTROL_1

        lda VIC_SPRITE_X_MSB
        and #$fe
        sta VIC_SPRITE_X_MSB
        lda VIC_SPRITE_MULTICOLOR
        and #$fe
        sta VIC_SPRITE_MULTICOLOR
        lda VIC_SPRITE_PRIORITY
        and #$fe
        sta VIC_SPRITE_PRIORITY
        lda VIC_SPRITE_X_EXPAND
        and #$fe
        sta VIC_SPRITE_X_EXPAND
        lda VIC_SPRITE_Y_EXPAND
        and #$fe
        sta VIC_SPRITE_Y_EXPAND
        lda #$ac
        sta VIC_SPRITE0_X
        lda #$8c
        sta VIC_SPRITE0_Y
        lda #$00
        sta VIC_SPRITE0_COLOR
        lda VIC_SPRITE_ENABLE
        ora #$01
        sta VIC_SPRITE_ENABLE
        rts

sprite_data:
        .byte $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
        .byte $00, $00, $00, $03, $00, $c0, $03, $00, $c0, $00, $c3, $00
        .byte $00, $c3, $00, $00, $3c, $00, $00, $3c, $00, $00, $3c, $00
        .byte $00, $c3, $00, $00, $c3, $00, $03, $00, $c0, $03, $00, $c0
        .byte $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00
        .byte $00, $00, $00
sprite_data_end:
        .assert sprite_data_end-sprite_data = 63, error, "VIC pointer sprite size drift"
vic_gateway_end:
        .assert vic_gateway_end-vic_gateway < $100, error, "VIC common gateway exceeds one-page installer"
