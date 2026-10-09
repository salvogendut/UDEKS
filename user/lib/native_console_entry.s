; SPDX-License-Identifier: GPL-3.0-or-later
; Initial execution proof only: no shell argument pointers cross banks.
        .setcpu "6502"
        .export _udeks_program_entry
        .export _udeks_native_console_gate
        .export _udeks_native_console_record = $f359
        .import _udeks_program_main, pusha
        .segment "STARTUP"
_udeks_program_entry:
        lda #0                      ; argc=0 until argument delivery is defined
        jsr pusha
        lda #0                      ; argv=NULL, task-private cc65 runtime
        tax
        jmp _udeks_program_main
        .segment "CODE"
_udeks_native_console_gate:
        jmp $ff16                   ; common context/runtime boundary, NOT CF20
