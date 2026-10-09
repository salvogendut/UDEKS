; SPDX-License-Identifier: GPL-3.0-or-later
; Shared retained-pool address/compaction primitives, cc65 calling convention.
; C callers validate slot/size/capacity BEFORE entry. Serialized, no callbacks.
; The pure C equivalents remain in retained_paths.c for differential tests.
        .setcpu "6502"
        .import _udeks_retained_lengths, _memmove, pushax, pusha, incsp1
        .importzp ptr1, sp
        .ifdef UDEKS_BITMAP_REU
        .import _udeks_bitmap_release
        .endif
        .export _udeks_retained_address, _udeks_retained_resize, _udeks_retained_discard
        .ifndef UDEKS_POOL_TEST
POOL = $1300
        .else
        .import _graphics_pool
POOL = _graphics_pool
        .endif
        .segment "BSS"
new_size: .res 2
slot:     .res 1
source:   .res 2
        .ifndef UDEKS_POOL_TEST
        .segment "GRAPHICSCODE"
        .else
        .segment "CODE"
        .endif
_udeks_retained_address:
        asl a
        tay
        lda #<POOL
        sta ptr1
        lda #>POOL
        sta ptr1+1
        cpy #0
        beq address_done
address_loop:
        dey
        dey
        clc
        lda _udeks_retained_lengths,y
        adc ptr1
        sta ptr1
        lda _udeks_retained_lengths+1,y
        and #$1f
        adc ptr1+1
        sta ptr1+1
        cpy #0
        bne address_loop
address_done:
        lda ptr1
        ldx ptr1+1
        rts

_udeks_retained_resize:
        sta new_size
        stx new_size+1
        ldy #0
        lda (sp),y              ; index is the sole stacked argument
        asl a
        sta slot
        lsr a
        jsr _udeks_retained_address
        ldy slot
        clc
        lda _udeks_retained_lengths,y
        adc ptr1
        sta source
        lda _udeks_retained_lengths+1,y
        and #$1f
        adc ptr1+1
        sta source+1           ; source = start + old length
        clc
        lda ptr1
        adc new_size
        pha
        lda ptr1+1
        adc new_size+1
        tax
        pla
        jsr pushax             ; memmove destination = start + new length
        lda source
        ldx source+1
        jsr pushax
        lda #4
        jsr _udeks_retained_address
        sec
        sbc source
        pha
        txa
        sbc source+1
        tax
        pla                    ; count = end - source
        jsr _memmove           ; overlap in either direction is legal
        ldy slot
        lda new_size
        sta _udeks_retained_lengths,y
        lda new_size+1
        sta _udeks_retained_lengths+1,y
        jmp incsp1

_udeks_retained_discard:
        .ifdef UDEKS_BITMAP_REU
        pha
        jsr _udeks_bitmap_release
        pla
        .endif
        jsr pusha
        lda #0
        tax
        jmp _udeks_retained_resize
