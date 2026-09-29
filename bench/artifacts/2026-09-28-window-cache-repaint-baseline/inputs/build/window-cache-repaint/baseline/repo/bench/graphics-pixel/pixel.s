; SPDX-License-Identifier: GPL-3.0-or-later
; Public cc65 pixel entry: color in A; y then x (16-bit LE) on software stack.
; Signed clipping matches the C entry. Drawing is serialized, binary-mode,
; bank-0 only; no yield, callback, MMU change or service invocation.
        .setcpu "6502"
        .importzp sp, ptr1, tmp1, tmp2
        .import incsp4, _udeks_vic_bitmap_shadow
        .export _udeks_vic_bitmap_pixel
        .segment "CODE"

.macro compare_signed offset, bound
        ldy #offset
        lda (sp),y
        cmp bound
        iny
        lda (sp),y
        sbc bound+1
        bvc :+
        eor #$80
:
.endmacro

_udeks_vic_bitmap_pixel:
        sta tmp1                 ; retain color across comparisons
        compare_signed 2, $e1b0  ; x >= left
        bmi rejected
        compare_signed 2, $e1b4  ; x < right
        bpl rejected
        compare_signed 0, $e1b2  ; y >= top
        bmi rejected
        compare_signed 0, $e1b6  ; y < bottom
        bpl rejected
        jmp plot
rejected:
        jmp incsp4               ; every path consumes exactly y + x
plot:
        ldy #$00
        lda (sp),y
        asl a
        sta ptr1
        lda #$e0
        adc #$00                 ; row index high bit from ASL
        sta ptr1+1
        ldy #$01
        lda (ptr1),y
        tax
        dey
        lda (ptr1),y
        sta ptr1
        stx ptr1+1
        ldy #$02
        lda (sp),y
        and #$f8
        clc
        adc ptr1
        sta ptr1
        iny
        lda (sp),y
        adc ptr1+1
        sta ptr1+1
        ; Dirty page uses logical offset, before adding the unaligned base.
        ldy ptr1+1
        lda #$01
        sta $e190,y
        ldy #$02
        lda (sp),y
        and #$07
        tax
        lda masks,x
        sta tmp2
        clc
        lda ptr1
        adc #<_udeks_vic_bitmap_shadow
        sta ptr1
        lda ptr1+1
        adc #>_udeks_vic_bitmap_shadow
        sta ptr1+1
        ldy #$00
        lda tmp1
        bne clear
        lda (ptr1),y
        ora tmp2
        bne store                ; one-bit mask guarantees nonzero result
clear:
        lda tmp2
        eor #$ff
        and (ptr1),y
store:
        sta (ptr1),y
        jmp incsp4
masks:
        .byte $80,$40,$20,$10,$08,$04,$02,$01
