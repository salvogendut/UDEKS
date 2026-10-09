; SPDX-License-Identifier: GPL-3.0-or-later
; No shell argument pointers cross banks. UARG belongs to this task's ZP.
        .setcpu "6502"
        .include "native_args.inc"
        .export _udeks_program_entry
        .export _udeks_native_console_gate
        .export _udeks_native_console_record = $f359
        .import _udeks_program_main, pusha
        .segment "STARTUP"
_udeks_program_entry:
        ldx #5
check_args:
        lda NATIVE_ARGS_BASE,x
        cmp args_signature,x
        bne unsupported
        dex
        bpl check_args
        lda NATIVE_ARGS_COUNT
        cmp #NATIVE_ARGS_MAX+1
        bcs unsupported
        jsr pusha
        lda #NATIVE_ARGS_VECTOR
        ldx #0
        jmp _udeks_program_main
unsupported:
        lda #126                    ; fail closed on old/malformed launch ABI
        ldx #0
        rts
args_signature:
        .byte "UARG",0,1
        .segment "CODE"
_udeks_native_console_gate:
        jmp $ff16                   ; common context/runtime boundary, NOT CF20
