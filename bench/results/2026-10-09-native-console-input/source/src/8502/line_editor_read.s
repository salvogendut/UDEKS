; SPDX-License-Identifier: GPL-3.0-or-later
;
; Compact chunked read for the submitted terminal line. Capacity arrives in A;
; the destination pointer is the preceding cc65 software-stack argument.

        .setcpu "6502"
        .segment "CODE"

        .export _udeks_line_editor_read
        .export _udeks_line_editor_get_line
        .import _udeks_line_editor_submitted_text
        .import _udeks_line_editor_submitted_length_value
        .import _udeks_line_editor_submitted_ready_value
        .import _udeks_line_editor_submitted_cursor
        .import popax
        .importzp tmp1, ptr1
        .import _udeks_shell_foreground_job, _udeks_root_terminal_input
        .export _udeks_terminal_input_access

        .segment "MODULECODE"
; Return zero only for the root shell without a foreground child, or the
; actual foreground native task. EIO rejects background reads, no mutation.
_udeks_terminal_input_access:
        jsr $c8fc
        cmp #2
        bcc shell_input
        sec
        sbc #3
        tax
        cpx #4
        bcs input_denied
        lda input_bits,x
        cmp _udeks_shell_foreground_job
        bne input_denied
        jsr _udeks_root_terminal_input
        beq input_allowed
        bne input_denied
shell_input:
        lda _udeks_shell_foreground_job
        bne input_denied
input_allowed:
        rts
input_denied:
        lda #5                      ; EIO: not the terminal's foreground owner
        rts
input_bits: .byte 1,2,4,8
        .segment "CODE"

_udeks_line_editor_read:
        jsr read_destination
        lda _udeks_line_editor_submitted_ready_value
        bne read_ready
        lda #$ff
        ldx #$00
        rts

; The compatibility whole-line reader shares the same bounded copy adapter.
; C remains the host reference. This keeps terminal ownership within the
; existing resident reservation, without shrinking any buffer or stack.
_udeks_line_editor_get_line:
        jsr read_destination
        lda _udeks_line_editor_submitted_ready_value
        beq line_empty
        lda _udeks_line_editor_submitted_length_value
        cmp tmp1
        bcs line_small
        tay
copy_line:
        lda _udeks_line_editor_submitted_text,y
        sta (ptr1),y
        dey
        bpl copy_line
        lda #0
        sta _udeks_line_editor_submitted_ready_value
        sta _udeks_line_editor_submitted_cursor
        beq line_done
line_empty:
        lda #1
        bne line_done
line_small:
        lda #2
line_done:
        ldx #0
        rts

read_destination:
        sta tmp1
        jsr popax
        sta ptr1
        stx ptr1+1
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
