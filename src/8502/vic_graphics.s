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
        .export _udeks_vic_pointer_select_shape
        .export _udeks_vic_pointer_busy_begin
        .export _udeks_vic_pointer_busy_end
        .export _udeks_vic_pointer_busy_tick
        .export _udeks_vic_bitmap_commit_page
        .export _udeks_vic_bitmap_outline_blit
        .import _udeks_vic_bitmap_shadow
        .import _udeks_vic_buffer_restore

MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_WORKER_FLAT     = $ff04
MMU_RCR                 = $d506
CPU_PORT                = $0001
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

COMMON_GATEWAY          = $f68a
COMMON_PAGE             = $f3ee
OUTLINE_GATEWAY_TAG     = $f3ed
OUTLINE_COUNT           = $f37f
COMMON_BUFFER           = $f400
OUTLINE_BUFFER          = $f380
VIC_SCREEN              = $5c00
VIC_BITMAP              = $6000
VIC_SPRITE_NORMAL       = $4100
VIC_SPRITE_BUSY         = $4140
VIC_SPRITE              = $7fc0
VIC_SPRITE_POINTER      = $5ff8
VIC_STATUS_STATE        = $f1b5
VIC_STATUS_POINTER_SHAPE = $f1c7
POINTER_FRAME_LOW       = $f1e2
VIC_STATE_ACTIVE        = $03
BUSY_RELEASE_PENDING    = $03
BUSY_HOLD_FRAMES        = $03

        .segment "BSS"
saved_chargen_overlay:
        .res 1
busy_release_frame:
        .res 1

        .segment "CODE"
_udeks_vic_graphics_enable:
        ; Hide the VIC canvas while the common-RAM gateway changes its bank
        ; and prepares the new bitmap.  The gateway reveals bitmap mode only
        ; after the screen, bitmap, and pointer are all coherent.
        lda VIC_CONTROL_1
        and #$ef
        sta VIC_CONTROL_1
        ; On the C128, CPU port bit 2 controls the character-ROM overlay seen
        ; by the VIC-IIe in every 16 KiB VIC bank.  Our screen matrix is at
        ; VIC-relative $1C00, inside that overlay window, so expose RAM before
        ; the first bitmap badline and preserve the caller's prior setting.
        lda CPU_PORT
        and #$04
        sta saved_chargen_overlay
        lda CPU_PORT
        ora #$04
        sta CPU_PORT
        lda #$00
        sta VIC_STATUS_POINTER_SHAPE
        sta OUTLINE_GATEWAY_TAG
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
        lda saved_chargen_overlay
        beq restore_chargen_overlay
        lda CPU_PORT
        ora #$04
        bne store_chargen_overlay
restore_chargen_overlay:
        lda CPU_PORT
        and #$fb
store_chargen_overlay:
        sta CPU_PORT
        lda #$00
        sta VIC_STATUS_POINTER_SHAPE
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

_udeks_vic_pointer_busy_begin:
        tax
        lda VIC_STATUS_STATE
        cmp #VIC_STATE_ACTIVE
        bne pointer_busy_done
        lda VIC_STATUS_POINTER_SHAPE
        beq pointer_busy_install
        cmp #BUSY_RELEASE_PENDING
        bne pointer_busy_done
        stx VIC_STATUS_POINTER_SHAPE
        rts
pointer_busy_install:
        stx VIC_STATUS_POINTER_SHAPE
        lda #$01
        jmp _udeks_vic_pointer_select_shape
pointer_busy_done:
        rts

_udeks_vic_pointer_busy_end:
        tax
        cpx VIC_STATUS_POINTER_SHAPE
        bne pointer_busy_done
        lda POINTER_FRAME_LOW
        clc
        adc #BUSY_HOLD_FRAMES
        sta busy_release_frame
        lda #BUSY_RELEASE_PENDING
        sta VIC_STATUS_POINTER_SHAPE
        rts

_udeks_vic_pointer_busy_tick:
        lda VIC_STATUS_POINTER_SHAPE
        cmp #BUSY_RELEASE_PENDING
        bne pointer_busy_done
        lda POINTER_FRAME_LOW
        cmp busy_release_frame
        bne pointer_busy_done
        lda #$00
        sta VIC_STATUS_POINTER_SHAPE
        jmp _udeks_vic_pointer_select_shape

_udeks_vic_pointer_select_shape:
        sta COMMON_PAGE
        ldx #$00
copy_sprite_swap_gateway:
        lda sprite_swap_gateway,x
        sta COMMON_GATEWAY,x
        inx
        cpx #sprite_swap_gateway_end-sprite_swap_gateway
        bne copy_sprite_swap_gateway
        jsr COMMON_GATEWAY
        rts

_udeks_vic_bitmap_commit_page:
        pha
        lda #$00
        sta OUTLINE_GATEWAY_TAG
        ldx #$00
copy_page_gateway:
        lda page_gateway,x
        sta COMMON_GATEWAY,x
        inx
        cpx #page_gateway_end-page_gateway
        bne copy_page_gateway
        pla
        sta COMMON_PAGE
        jsr COMMON_GATEWAY
        rts

_udeks_vic_bitmap_outline_blit:
        lda OUTLINE_GATEWAY_TAG
        cmp #$a5
        beq run_outline_gateway
        ldx #$00
copy_outline_gateway_0:
        lda outline_gateway,x
        sta COMMON_GATEWAY,x
        inx
        bne copy_outline_gateway_0
        ldx #$00
copy_outline_gateway_1:
        lda outline_gateway+$100,x
        sta COMMON_GATEWAY+$100,x
        inx
        cpx #outline_gateway_end-outline_gateway-$100
        bne copy_outline_gateway_1
        lda #$a5
        sta OUTLINE_GATEWAY_TAG
run_outline_gateway:
        jsr COMMON_GATEWAY
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

        php
        sei
        lda MMU_RCR
        ; Make the bank transition explicit and keep the complete VIC/MMU
        ; setup atomic with respect to the console's periodic IRQ work.
        and #$bf
        sta MMU_RCR
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
        lda #$3b
        sta VIC_CONTROL_1
        plp
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

sprite_swap_gateway:
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        lda COMMON_PAGE
        beq sprite_restore_normal
        ldx #$3e
sprite_save_normal:
        lda VIC_SPRITE,x
        sta VIC_SPRITE_NORMAL,x
        lda VIC_SPRITE_BUSY,x
        sta VIC_SPRITE,x
        dex
        bpl sprite_save_normal
        bmi sprite_swap_done
sprite_restore_normal:
        ldx #$3e
sprite_restore_copy:
        lda VIC_SPRITE_NORMAL,x
        sta VIC_SPRITE,x
        dex
        bpl sprite_restore_copy
sprite_swap_done:
        lda #$00
        sta MMU_LCR_KERNEL_IO
        rts
sprite_swap_gateway_end:
        .assert sprite_swap_gateway_end-sprite_swap_gateway < $40, error, "VIC sprite swap gateway is too large"

page_gateway:
        lda COMMON_PAGE
        clc
        adc #>_udeks_vic_bitmap_shadow
        sta COMMON_GATEWAY+(page_load_shadow-page_gateway)+2
        lda COMMON_PAGE
        clc
        adc #>VIC_BITMAP
        sta COMMON_GATEWAY+(page_store_bitmap-page_gateway)+2
        ldy #$00
page_stage:
page_load_shadow:
        lda _udeks_vic_bitmap_shadow,y
        sta COMMON_BUFFER,y
        iny
        bne page_stage

        lda #$00
        sta MMU_LCR_WORKER_FLAT
        ldy #$00
        lda COMMON_PAGE
        cmp #$1f
        beq page_copy_last
page_copy_full:
        lda COMMON_BUFFER,y
page_store_bitmap:
        sta VIC_BITMAP,y
        iny
        bne page_copy_full
        beq page_copy_done
page_copy_last:
        lda COMMON_BUFFER,y
        sta VIC_BITMAP+$1f00,y
        iny
        cpy #$40
        bne page_copy_last
page_copy_done:
        jmp _udeks_vic_buffer_restore
page_gateway_end:
        .assert page_gateway_end-page_gateway < $f0, error, "VIC page gateway overlaps parameters"

; Each 15-byte record in OUTLINE_BUFFER contains precomputed bitmap addresses:
; top, bottom, horizontal byte count/masks, left/right vertical start/mask,
; vertical pixel count, and the starting scanline within its character row.
outline_gateway:
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        sta COMMON_GATEWAY+(outline_record-outline_gateway)
        lda OUTLINE_COUNT
        sta COMMON_GATEWAY+(outline_left-outline_gateway)
        bne outline_next
        jmp COMMON_GATEWAY+(outline_done-outline_gateway)

outline_next:
        ldy COMMON_GATEWAY+(outline_record-outline_gateway)
        lda OUTLINE_BUFFER+4,y
        sta COMMON_GATEWAY+(horizontal_count-outline_gateway)
        lda OUTLINE_BUFFER+5,y
        sta COMMON_GATEWAY+(horizontal_first-outline_gateway)
        lda OUTLINE_BUFFER+6,y
        sta COMMON_GATEWAY+(horizontal_last-outline_gateway)

        lda OUTLINE_BUFFER,y
        sta COMMON_GATEWAY+(horizontal_load-outline_gateway)+1
        sta COMMON_GATEWAY+(horizontal_store-outline_gateway)+1
        lda OUTLINE_BUFFER+1,y
        sta COMMON_GATEWAY+(horizontal_load-outline_gateway)+2
        sta COMMON_GATEWAY+(horizontal_store-outline_gateway)+2
        jsr COMMON_GATEWAY+(draw_horizontal-outline_gateway)

        lda OUTLINE_BUFFER+2,y
        sta COMMON_GATEWAY+(horizontal_load-outline_gateway)+1
        sta COMMON_GATEWAY+(horizontal_store-outline_gateway)+1
        lda OUTLINE_BUFFER+3,y
        sta COMMON_GATEWAY+(horizontal_load-outline_gateway)+2
        sta COMMON_GATEWAY+(horizontal_store-outline_gateway)+2
        jsr COMMON_GATEWAY+(draw_horizontal-outline_gateway)

        lda OUTLINE_BUFFER+13,y
        sta COMMON_GATEWAY+(vertical_count-outline_gateway)
        lda OUTLINE_BUFFER+14,y
        sta COMMON_GATEWAY+(vertical_row-outline_gateway)
        lda OUTLINE_BUFFER+7,y
        sta COMMON_GATEWAY+(vertical_load-outline_gateway)+1
        sta COMMON_GATEWAY+(vertical_store-outline_gateway)+1
        lda OUTLINE_BUFFER+8,y
        sta COMMON_GATEWAY+(vertical_load-outline_gateway)+2
        sta COMMON_GATEWAY+(vertical_store-outline_gateway)+2
        lda OUTLINE_BUFFER+9,y
        sta COMMON_GATEWAY+(vertical_mask-outline_gateway)
        jsr COMMON_GATEWAY+(draw_vertical-outline_gateway)

        ldy COMMON_GATEWAY+(outline_record-outline_gateway)
        lda OUTLINE_BUFFER+13,y
        sta COMMON_GATEWAY+(vertical_count-outline_gateway)
        lda OUTLINE_BUFFER+14,y
        sta COMMON_GATEWAY+(vertical_row-outline_gateway)
        lda OUTLINE_BUFFER+10,y
        sta COMMON_GATEWAY+(vertical_load-outline_gateway)+1
        sta COMMON_GATEWAY+(vertical_store-outline_gateway)+1
        lda OUTLINE_BUFFER+11,y
        sta COMMON_GATEWAY+(vertical_load-outline_gateway)+2
        sta COMMON_GATEWAY+(vertical_store-outline_gateway)+2
        lda OUTLINE_BUFFER+12,y
        sta COMMON_GATEWAY+(vertical_mask-outline_gateway)
        jsr COMMON_GATEWAY+(draw_vertical-outline_gateway)

        lda COMMON_GATEWAY+(outline_record-outline_gateway)
        clc
        adc #$0f
        sta COMMON_GATEWAY+(outline_record-outline_gateway)
        dec COMMON_GATEWAY+(outline_left-outline_gateway)
        beq outline_done
        jmp COMMON_GATEWAY+(outline_next-outline_gateway)
outline_done:
        lda #$00
        sta MMU_LCR_KERNEL_IO
        rts

draw_horizontal:
        ldx COMMON_GATEWAY+(horizontal_count-outline_gateway)
        cpx #$01
        bne horizontal_multiple
        lda COMMON_GATEWAY+(horizontal_first-outline_gateway)
        and COMMON_GATEWAY+(horizontal_last-outline_gateway)
        sta COMMON_GATEWAY+(horizontal_mask-outline_gateway)
        jmp COMMON_GATEWAY+(horizontal_toggle-outline_gateway)
horizontal_multiple:
        lda COMMON_GATEWAY+(horizontal_first-outline_gateway)
        sta COMMON_GATEWAY+(horizontal_mask-outline_gateway)
        jsr COMMON_GATEWAY+(horizontal_toggle-outline_gateway)
        jsr COMMON_GATEWAY+(horizontal_advance-outline_gateway)
        dex
horizontal_middle:
        cpx #$01
        beq horizontal_final
        lda #$ff
        sta COMMON_GATEWAY+(horizontal_mask-outline_gateway)
        jsr COMMON_GATEWAY+(horizontal_toggle-outline_gateway)
        jsr COMMON_GATEWAY+(horizontal_advance-outline_gateway)
        dex
        bne horizontal_middle
horizontal_final:
        lda COMMON_GATEWAY+(horizontal_last-outline_gateway)
        sta COMMON_GATEWAY+(horizontal_mask-outline_gateway)
horizontal_toggle:
horizontal_load:
        lda $ffff
        eor COMMON_GATEWAY+(horizontal_mask-outline_gateway)
horizontal_store:
        sta $ffff
        rts

horizontal_advance:
        clc
        lda COMMON_GATEWAY+(horizontal_load-outline_gateway)+1
        adc #$08
        sta COMMON_GATEWAY+(horizontal_load-outline_gateway)+1
        sta COMMON_GATEWAY+(horizontal_store-outline_gateway)+1
        bcc horizontal_advance_done
        inc COMMON_GATEWAY+(horizontal_load-outline_gateway)+2
        inc COMMON_GATEWAY+(horizontal_store-outline_gateway)+2
horizontal_advance_done:
        rts

draw_vertical:
        ldx COMMON_GATEWAY+(vertical_count-outline_gateway)
        beq vertical_done
vertical_next:
vertical_load:
        lda $ffff
        eor COMMON_GATEWAY+(vertical_mask-outline_gateway)
vertical_store:
        sta $ffff
        dex
        beq vertical_done
        inc COMMON_GATEWAY+(vertical_row-outline_gateway)
        lda COMMON_GATEWAY+(vertical_row-outline_gateway)
        cmp #$08
        bne vertical_advance_one
        lda #$00
        sta COMMON_GATEWAY+(vertical_row-outline_gateway)
        clc
        lda COMMON_GATEWAY+(vertical_load-outline_gateway)+1
        adc #$39
        sta COMMON_GATEWAY+(vertical_load-outline_gateway)+1
        sta COMMON_GATEWAY+(vertical_store-outline_gateway)+1
        lda COMMON_GATEWAY+(vertical_load-outline_gateway)+2
        adc #$01
        sta COMMON_GATEWAY+(vertical_load-outline_gateway)+2
        sta COMMON_GATEWAY+(vertical_store-outline_gateway)+2
        jmp COMMON_GATEWAY+(vertical_next-outline_gateway)
vertical_advance_one:
        inc COMMON_GATEWAY+(vertical_load-outline_gateway)+1
        inc COMMON_GATEWAY+(vertical_store-outline_gateway)+1
        bne vertical_next
        inc COMMON_GATEWAY+(vertical_load-outline_gateway)+2
        inc COMMON_GATEWAY+(vertical_store-outline_gateway)+2
        jmp COMMON_GATEWAY+(vertical_next-outline_gateway)
vertical_done:
        rts

outline_record:          .byte $00
outline_left:            .byte $00
horizontal_count:        .byte $00
horizontal_first:        .byte $00
horizontal_last:         .byte $00
horizontal_mask:         .byte $00
vertical_count:          .byte $00
vertical_row:            .byte $00
vertical_mask:           .byte $00
outline_gateway_end:
        .assert outline_gateway_end-outline_gateway > $100, error, "VIC outline gateway unexpectedly fits one page"
        .assert outline_gateway_end-outline_gateway < $200, error, "VIC outline gateway exceeds common workspace"
