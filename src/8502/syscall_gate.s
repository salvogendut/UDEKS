; SPDX-License-Identifier: GPL-3.0-or-later
;
; Stable 8502 user/kernel call gate. Each vector is one absolute JMP so a
; caller may JSR the published address and receive the implementation's RTS.

        .setcpu "6502"
        .segment "SYSCALLS"

        .export _udeks_syscall_table
        .export _udeks_syscall_write_byte_gate
        .export _udeks_syscall_write_gate
        .import _udeks_stream_write_byte
        .import _udeks_stream_write
        .import pusha
        .importzp tmp1, ptr1

_udeks_syscall_table:
        .byte 'U', 'S', 'Y', 'S'
        .byte $00, $01
        .byte $02, $10
        .res 8, $00

        ; $CF10: A=descriptor, X=byte. Marshal to the resident C service.
_udeks_syscall_write_byte_gate:
        stx tmp1
        jsr pusha
        lda tmp1
        ldx #$00
        jmp _udeks_stream_write_byte
        .res 4, $ea

        ; $CF20: A=descriptor, X=pointer low, Y=pointer high.
        ; ptr1 is part of the kernel's reserved runtime zero page.
_udeks_syscall_write_gate:
        stx ptr1
        sty ptr1+1
        jsr pusha
        lda ptr1
        ldx ptr1+1
        jmp _udeks_stream_write
        .res 2, $ea

        .assert _udeks_syscall_table = $cf00, error, "syscall table moved"
        .assert _udeks_syscall_write_byte_gate = $cf10, error, "write-byte gate moved"
        .assert _udeks_syscall_write_gate = $cf20, error, "write gate moved"
        .assert * = $cf30, error, "syscall vector layout drifted"
