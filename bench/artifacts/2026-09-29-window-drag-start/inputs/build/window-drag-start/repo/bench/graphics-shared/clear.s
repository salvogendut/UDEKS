; SPDX-License-Identifier: GPL-3.0-or-later
; Existing cc65 fastcall entry: color in A. Clear the whole 8,000-byte shadow,
; ignoring clip, then mark all 32 logical pages. Serialized binary-mode draw.
        .setcpu "6502"
        .importzp ptr1
        .import _udeks_vic_bitmap_shadow
        .export _udeks_vic_bitmap_clear
        .segment "CODE"
_udeks_vic_bitmap_clear:
        cmp #$00
        beq black
        lda #$00
        beq setup
black:
        lda #$ff
setup:
        tax
        lda #<_udeks_vic_bitmap_shadow
        sta ptr1
        lda #>_udeks_vic_bitmap_shadow
        sta ptr1+1
        txa
        ldx #31
        ldy #$00
page:
        sta (ptr1),y
        iny
        bne page
        inc ptr1+1
        dex
        bne page
tail:
        sta (ptr1),y
        iny
        cpy #64
        bne tail
        ldx #31
        lda #$01
dirty:
        sta $e190,x
        dex
        bpl dirty
        rts
