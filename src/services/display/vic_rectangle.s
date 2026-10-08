; SPDX-License-Identifier: GPL-3.0-or-later
; Same cc65 entry: color in A, height/width/y/x LE16 on the software stack.
; Four clipped fills, including the original duplicate corner writes. The
; service is serialized/nonrecursive; IRQ/NMI handlers never draw.
        .setcpu "6502"
        .macpack longbranch
        .importzp sp
        .import pushax, incsp8, _udeks_vic_bitmap_fill
        .export _udeks_vic_bitmap_rectangle
        .segment "BSS"
rect_values: .res 14             ; x,y,w,h,right,bottom,constant one
rect_color:  .res 1
rect_cursor: .res 1
        .segment "CODE"
_udeks_vic_bitmap_rectangle:
        sta rect_color
        ldy #3                  ; reject nonpositive signed width/height
        lda (sp),y
        jmi rejected
        dey
        ora (sp),y
        jeq rejected
        dey
        lda (sp),y
        jmi rejected
        dey
        ora (sp),y
        jeq rejected
        ldx #0
        ldy #6
copy_pair:
        lda (sp),y
        sta rect_values,x
        iny
        inx
        lda (sp),y
        sta rect_values,x
        inx
        dey
        dey
        dey
        bpl copy_pair
        ldx #2
last_coordinate:
        sec                     ; last = origin + extent - 1 (16-bit)
        lda rect_values+4,x
        sbc #1
        sta rect_values+8,x
        lda rect_values+5,x
        sbc #0
        sta rect_values+9,x
        clc
        lda rect_values,x
        adc rect_values+8,x
        sta rect_values+8,x
        lda rect_values+1,x
        adc rect_values+9,x
        sta rect_values+9,x
        dex
        dex
        beq last_coordinate
        lda #1
        sta rect_values+12
        lda #0
        sta rect_values+13
        sta rect_cursor
argument:
        ldx rect_cursor
        ldy arguments,x
        lda rect_values+1,y
        tax
        lda rect_values,y
        jsr pushax
        inc rect_cursor
        lda rect_cursor
        and #3
        bne argument
        lda rect_color
        jsr _udeks_vic_bitmap_fill
        lda rect_cursor
        cmp #16
        bne argument
rejected:
        jmp incsp8
arguments:
        .byte 0,2,4,12          ; x,y,width,1
        .byte 0,10,4,12         ; x,bottom,width,1
        .byte 0,2,12,6          ; x,y,1,height
        .byte 8,2,12,6          ; right,y,1,height
