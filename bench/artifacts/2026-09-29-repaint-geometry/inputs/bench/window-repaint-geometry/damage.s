; SPDX-License-Identifier: GPL-3.0-or-later
; Private 8502 damage-box value primitives, NOT in the production kernel.
; Input AX: pointer to the compact manager's eight-byte value prefix.
; Fields are flags@0, x@1..2, y@3, width@4..5, height@6, rank@7.
; ptr1/ptr2 are caller-clobbered cc65 runtime scratch, not persistent state.
        .setcpu "6502"
        .importzp ptr1, ptr2
        .import _damage_left, _damage_top, _damage_right, _damage_bottom
        .export _damage_set, _damage_add
        .segment "CODE"

_damage_set:
        sta ptr1
        stx ptr1+1
        ldy #$01
        lda (ptr1),y
        sta _damage_left
        iny
        lda (ptr1),y
        sta _damage_left+1
        iny
        lda (ptr1),y
        sta _damage_top
        clc
        ldy #$04
        lda (ptr1),y
        adc _damage_left
        sta _damage_right
        iny
        lda (ptr1),y
        adc _damage_left+1
        sta _damage_right+1
        iny
        lda (ptr1),y
        clc
        adc _damage_top
        sta _damage_bottom
        rts

_damage_add:
        sta ptr1
        stx ptr1+1
        ; left := min(left,x), unsigned 16-bit high byte first.
        ldy #$02
        lda (ptr1),y
        cmp _damage_left+1
        bcc set_left
        bne left_done
        dey
        lda (ptr1),y
        cmp _damage_left
        bcs left_done
set_left:
        ldy #$01
        lda (ptr1),y
        sta _damage_left
        iny
        lda (ptr1),y
        sta _damage_left+1
left_done:
        ldy #$03
        lda (ptr1),y
        cmp _damage_top
        bcs top_done
        sta _damage_top
top_done:
        ; right := max(right,(x+width) mod 65536).
        ldy #$01
        lda (ptr1),y
        clc
        ldy #$04
        adc (ptr1),y
        sta ptr2
        ldy #$02
        lda (ptr1),y
        ldy #$05
        adc (ptr1),y
        sta ptr2+1
        cmp _damage_right+1
        bcc right_done
        bne set_right
        lda ptr2
        cmp _damage_right
        bcc right_done
        beq right_done
set_right:
        lda ptr2
        sta _damage_right
        lda ptr2+1
        sta _damage_right+1
right_done:
        ; bottom := max(bottom,(y+height) mod 256).
        ldy #$03
        lda (ptr1),y
        clc
        ldy #$06
        adc (ptr1),y
        cmp _damage_bottom
        bcc bottom_done
        beq bottom_done
        sta _damage_bottom
bottom_done:
        rts
