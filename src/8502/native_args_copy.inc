; SPDX-License-Identifier: GPL-3.0-or-later
; Inlined while the child's CPU pages are mapped. A/X/Y only: no stack,
; indirect kernel-ZP references or callbacks. Caller has zeroed the page;
; source is the bounded root parser, not task-supplied addresses/counts.
        lda _udeks_shell_native_argc
        sta NATIVE_ARGS_COUNT
        beq args_header
        tax
        dex
        ldy _udeks_shell_offsets,x
args_end:
        lda _udeks_shell_command_line,y
        beq args_text
        iny
        bne args_end
args_text:
        lda _udeks_shell_command_line,y
        sta a:NATIVE_ARGS_TEXT,y
        dey
        bpl args_text
        ldx _udeks_shell_native_argc
args_pointer:
        dex
        txa
        asl
        tay
        lda _udeks_shell_offsets,x
        clc
        adc #NATIVE_ARGS_TEXT
        sta a:NATIVE_ARGS_VECTOR,y
        cpx #0
        bne args_pointer
args_header:
        lda #'U'
        sta NATIVE_ARGS_BASE
        lda #'A'
        sta NATIVE_ARGS_BASE+1
        lda #'R'
        sta NATIVE_ARGS_BASE+2
        lda #'G'
        sta NATIVE_ARGS_BASE+3
        lda #1
        sta NATIVE_ARGS_MINOR
