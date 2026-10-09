; SPDX-License-Identifier: GPL-3.0-or-later
; Serialized graphics-service renderer, no foreign callbacks or task yields.
; Uses the ordinary clipped/dirty-tracked pixel primitive. Transparent zero
; bits, MSB first; row padding was checked before the image was committed.
        .setcpu "6502"
        .macpack longbranch
        .export _udeks_retained_bitmap_paint
        .import _udeks_retained_lengths, _udeks_retained_address
        .import _udeks_graphics_origin_x, _udeks_graphics_origin_y
        .import _udeks_vic_bitmap_pixel, pushax
        .importzp ptr1
        .segment "BSS"
left:   .res 2
px:     .res 2
py:     .res 2
pixels: .res 2
stride: .res 1
columns:.res 1
rows:   .res 1
bits:   .res 1
count:  .res 1
        .segment "CODE"
_udeks_retained_bitmap_paint:
        cmp #4
        jcs done
        pha
        asl a
        tax
        lda _udeks_retained_lengths+1,x
        and #$e0
        cmp #$40                  ; only a committed bitmap is drawable
        beq committed
        pla
        rts
committed:
        pla
        jsr _udeks_retained_address
        ; Address helper returns the header in AX and ptr1.
        clc
        adc #8
        sta pixels
        txa
        adc #0
        sta pixels+1
        ldy #0
        clc
        lda (ptr1),y
        adc _udeks_graphics_origin_x
        sta left
        iny
        lda (ptr1),y
        adc _udeks_graphics_origin_x+1
        sta left+1
        iny
        clc
        lda (ptr1),y
        adc _udeks_graphics_origin_y
        sta py
        lda #0
        adc #0
        sta py+1
        ldy #4
        lda (ptr1),y
        sta rows
        iny
        lda (ptr1),y
        sta stride
row:
        lda left
        sta px
        lda left+1
        sta px+1
        lda stride
        sta columns
byte:
        lda pixels
        sta ptr1
        lda pixels+1
        sta ptr1+1
        ldy #0
        lda (ptr1),y
        sta bits
        inc pixels
        bne :+
        inc pixels+1
:       lda #8
        sta count
pixel_bit:
        asl bits
        bcc advance
        lda px
        ldx px+1
        jsr pushax
        lda py
        ldx py+1
        jsr pushax
        lda #0                    ; black ink, cc65 fastcall color
        tax
        jsr _udeks_vic_bitmap_pixel
advance:
        inc px
        bne :+
        inc px+1
:       dec count
        bne pixel_bit
        dec columns
        bne byte
        inc py
        bne :+
        inc py+1
:       dec rows
        bne row
done:   rts
