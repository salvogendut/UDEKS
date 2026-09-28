; SPDX-License-Identifier: GPL-3.0-or-later
; Bank-0 byte packing and masked paste. Private, non-reentrant prototype;
; ptr1 and scratch are caller-clobbered cc65 temporaries. No banking/yield.
        .setcpu "6502"
        .import _cache_row_offset, _cache_row_shift
        .import _cache_row_next_count, _cache_row_last_mask
        .importzp ptr1
        .export _cache_capture_row, _cache_paste_row
COUNT = $f382
STAGE = $f400
SHADOW = $a1e0
DIRTY = $e190

        .segment "BSS"
first:  .res 1
second: .res 1
mask1:  .res 1
mask2:  .res 1
lastpage: .res 1

        .segment "CODE"
setup:
        clc
        lda _cache_row_offset
        adc #<SHADOW
        sta ptr1
        lda _cache_row_offset+1
        adc #>SHADOW
        sta ptr1+1
        ldx #$00
        rts
advance:
        clc
        lda ptr1
        adc #$08
        sta ptr1
        bcc advanced
        inc ptr1+1
advanced:
        rts

_cache_capture_row:
        jsr setup
capture:
        ldy #$00
        lda (ptr1),y
        sta first
        jsr advance
        lda #$00
        sta second
        lda _cache_row_shift
        beq aligned
        cpx _cache_row_next_count
        bcs no_next
        lda (ptr1),y
        sta second
no_next:
        ldy _cache_row_shift
        lda first
left:
        asl second
        rol a
        dey
        bne left
        jmp packed
aligned:
        lda first
packed:
        inx
        cpx COUNT
        bne full_byte
        and _cache_row_last_mask
full_byte:
        dex
        sta STAGE,x
        inx
        cpx COUNT
        bcc capture
        rts

_cache_paste_row:
        jsr setup
        lda #$ff
        sta mask1
        lda #$00
        sta mask2
        ldy _cache_row_shift
        beq paste
body_masks:
        lsr mask1
        ror mask2
        dey
        bne body_masks
paste:
        lda #$00
        sta second
        lda STAGE,x
        ldy _cache_row_shift
        beq split
right:
        lsr a
        ror second
        dey
        bne right
split:
        sta first
        inx
        cpx COUNT
        bne merge
        lda _cache_row_last_mask
        sta mask1
        lda #$00
        sta mask2
        ldy _cache_row_shift
        beq merge
tail_masks:
        lsr mask1
        ror mask2
        dey
        bne tail_masks
merge:
        ldy #$00
        lda (ptr1),y
        eor first
        and mask1
        eor (ptr1),y
        sta (ptr1),y
        jsr advance
        lda mask2
        beq next
        lda (ptr1),y
        eor second
        and mask2
        eor (ptr1),y
        sta (ptr1),y
next:
        cpx COUNT
        bcc paste
        ; ptr1 is now the optional second byte of the last packed byte.
        ; If its mask is zero it was not touched, so exclude it from damage.
        lda mask2
        bne end_pointer
        sec
        lda ptr1
        sbc #$08
        sta ptr1
        bcs end_pointer
        dec ptr1+1
end_pointer:
        sec
        lda ptr1
        sbc #<SHADOW
        lda ptr1+1
        sbc #>SHADOW
        sta lastpage
        ldy _cache_row_offset+1
        lda #$01
mark:
        sta DIRTY,y
        cpy lastpage
        bcs done
        iny
        bne mark
done:
        rts
