; SPDX-License-Identifier: GPL-3.0-or-later
;
; Compact chunked read for the submitted terminal line. Capacity arrives in A;
; the destination pointer is the preceding cc65 software-stack argument.

        .setcpu "6502"
        .segment "CODE"

        .export _udeks_line_editor_read
        .import _udeks_line_editor_submitted_text
        .import _udeks_line_editor_submitted_length_value
        .import _udeks_line_editor_submitted_ready_value
        .import _udeks_line_editor_submitted_cursor
        .import popax
        .importzp tmp1, ptr1

_udeks_line_editor_read:
        sta tmp1
        jsr popax
        sta ptr1
        stx ptr1+1
        lda _udeks_line_editor_submitted_ready_value
        bne read_ready
        lda #$ff
        ldx #$00
        rts

read_ready:
        ldy #$00
read_byte:
        cpy tmp1
        bcs read_done
        ldx _udeks_line_editor_submitted_cursor
        cpx _udeks_line_editor_submitted_length_value
        bcs read_newline
        lda _udeks_line_editor_submitted_text,x
        sta (ptr1),y
        inc _udeks_line_editor_submitted_cursor
        iny
        bne read_byte

read_newline:
        lda #$0a
        sta (ptr1),y
        iny
        lda #$00
        sta _udeks_line_editor_submitted_ready_value
        sta _udeks_line_editor_submitted_cursor

read_done:
        tya
        ldx #$00
        rts
