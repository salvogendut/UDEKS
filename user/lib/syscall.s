; SPDX-License-Identifier: GPL-3.0-or-later
;
; User-side veneers. The ABI addresses are constants and never resolve against
; private symbols in the resident image.

        .setcpu "6502"
        .segment "CODE"

        .export _udeks_write_byte
        .export _udeks_write
        .import popa
        .importzp tmp1, ptr1

UDEKS_SYSCALL_WRITE_BYTE = $cf10
UDEKS_SYSCALL_WRITE      = $cf20

_udeks_write_byte:
        ; cc65 supplies value in A and descriptor on its software stack.
        sta tmp1
        jsr popa
        ldx tmp1
        jmp UDEKS_SYSCALL_WRITE_BYTE

_udeks_write:
        ; cc65 supplies the string pointer in AX and the descriptor on stack.
        sta ptr1
        stx ptr1+1
        jsr popa
        ldx ptr1
        ldy ptr1+1
        jmp UDEKS_SYSCALL_WRITE
