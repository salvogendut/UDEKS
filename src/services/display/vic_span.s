; SPDX-License-Identifier: GPL-3.0-or-later
; A clipped VIC-interleaved row: 1..40 bytes separated by eight addresses.
; Caller owns private parameters and display serialization. No banking, yield,
; callback, or service invocation. ptr1/tmp1 are caller-clobbered cc65 scratch.
        .setcpu "6502"
        .importzp ptr1, tmp1
        .import _udeks_vic_bitmap_shadow
        .import _udeks_span_offset, _udeks_span_count
        .import _udeks_span_first, _udeks_span_last, _udeks_span_color
        .export _udeks_span_fill_row
        .segment "CODE"
_udeks_span_fill_row:
        clc
        lda _udeks_span_offset
        adc #<_udeks_vic_bitmap_shadow
        sta ptr1
        lda _udeks_span_offset+1
        adc #>_udeks_vic_bitmap_shadow
        sta ptr1+1
        ; Dirty indices are *logical* shadow pages, not pointer high bytes:
        ; the production shadow is deliberately unaligned at $A1E0.
        ldy _udeks_span_offset+1
        lda #$01
        sta $e190,y
        ldy #$00
        ldx _udeks_span_count
        lda _udeks_span_first
next_mask:
        cpx #$01
        bne mask_ready
        and _udeks_span_last
mask_ready:
        sta tmp1
        lda _udeks_span_color
        bne clear
        lda (ptr1),y
        ora tmp1
        bne store              ; nonzero because clipped mask is nonzero
clear:
        lda tmp1
        eor #$ff
        and (ptr1),y
store:
        sta (ptr1),y
        dex
        beq done
        clc
        lda ptr1
        adc #$08
        sta ptr1
        bcc pointer_ready
        inc ptr1+1
pointer_ready:
        clc
        lda _udeks_span_offset
        adc #$08
        sta _udeks_span_offset
        bcc same_page
        inc _udeks_span_offset+1
        ldy _udeks_span_offset+1
        lda #$01
        sta $e190,y
        ldy #$00
same_page:
        lda #$ff
        bne next_mask
done:
        rts
