; SPDX-License-Identifier: GPL-3.0-or-later
; Compact implementation of the existing bounded whitespace tokenizer.
; Retain user/lib/shell_parser.c as the CPU differential-test reference.
; Reclaims MODULECODE for task-private argument initialization, not new RAM.
        .setcpu "6502"
        .export _udeks_shell_tokenize
        .import popax
        .importzp ptr1, ptr2, tmp1, tmp2
        .segment "MODULECODE"
_udeks_shell_tokenize:
        sta tmp1                    ; capacity (fastcall final argument)
        jsr popax
        sta ptr2                    ; offsets
        stx ptr2+1
        jsr popax
        sta ptr1                    ; line
        stx ptr1+1
        ldx #0                      ; token count
        ldy #0                      ; line position
scan:
        lda (ptr1),y
        beq complete
        cmp #' '
        beq advance
        cmp #9
        beq advance
        cpx tmp1
        beq too_many
        sty tmp2
        txa
        tay
        lda tmp2
        sta (ptr2),y
        inx
        ldy tmp2
token:
        lda (ptr1),y
        beq complete
        cmp #' '
        beq cut
        cmp #9
        beq cut
        iny
        bne token
        beq too_many                ; never wrap past a 255-byte input
cut:
        lda #0
        sta (ptr1),y
advance:
        iny
        bne scan
too_many:
        ldx #$ff
complete:
        txa
        ldx #0
        rts
