; SPDX-License-Identifier: GPL-3.0-or-later
; Serialized graphics-service renderer, no foreign callbacks or task yields.
; Uses the ordinary clipped/dirty-tracked pixel primitive. Transparent zero
; bits, MSB first; row padding was checked before the image was committed.
        .setcpu "6502"
        .macpack longbranch
        .ifdef UDEKS_BITMAP_REU
        .export _udeks_bitmap_paint_hidden, _udeks_bitmap_row_stride
_udeks_bitmap_paint_hidden = _udeks_retained_bitmap_paint
        .import _udeks_bitmap_fetch_row, _udeks_bitmap_row_buffer
        .import _udeks_bitmap_row_offset
        .segment "BITMAPSTATE"
index:  .res 1
external:.res 1
        .else
        .export _udeks_retained_bitmap_paint
        .segment "BSS"
        .endif
        .import _udeks_retained_lengths, _udeks_retained_address
        .import _udeks_graphics_origin_x, _udeks_graphics_origin_y
        .import _udeks_vic_bitmap_pixel, pushax
        .importzp ptr1
left:   .res 2
px:     .res 2
py:     .res 2
pixels: .res 2
stride: .res 1
        .ifdef UDEKS_BITMAP_REU
_udeks_bitmap_row_stride = stride
        .endif
columns:.res 1
rows:   .res 1
bits:   .res 1
count:  .res 1
        .ifdef UDEKS_BITMAP_REU
        .segment "BITMAPCODE"
        .else
        .segment "CODE"
        .endif
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
        .ifdef UDEKS_BITMAP_REU
        sta index
        .endif
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
        .ifdef UDEKS_BITMAP_REU
        sta external
        and #$7f
        .endif
        sta stride
        .ifdef UDEKS_BITMAP_REU
        lda #0
        sta _udeks_bitmap_row_offset
        sta _udeks_bitmap_row_offset+1
        .endif
row:
        .ifdef UDEKS_BITMAP_REU
        bit external
        bpl local_row
        lda index
        jsr _udeks_bitmap_fetch_row
        cmp #0
        jne done                  ; never plot a partially fetched row
        lda #<_udeks_bitmap_row_buffer
        sta pixels
        lda #>_udeks_bitmap_row_buffer
        sta pixels+1
        clc
        lda _udeks_bitmap_row_offset
        adc stride
        sta _udeks_bitmap_row_offset
        bcc local_row
        inc _udeks_bitmap_row_offset+1
local_row:
        .endif
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
        jne row
done:   rts
