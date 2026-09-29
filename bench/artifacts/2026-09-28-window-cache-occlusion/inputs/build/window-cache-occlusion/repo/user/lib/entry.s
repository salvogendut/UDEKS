; SPDX-License-Identifier: GPL-3.0-or-later

        .setcpu "6502"
        .segment "STARTUP"

        .export _udeks_program_entry
        .import _udeks_program_main
        .import pusha
        .importzp tmp1, ptr1

_udeks_program_entry:
        ; Binary ABI: A=argc, X=argv low, Y=argv high. Convert it to the cc65
        ; C convention used by this program without exposing that convention
        ; to the loader.
        sta tmp1
        stx ptr1
        sty ptr1+1
        lda tmp1
        jsr pusha
        lda ptr1
        ldx ptr1+1
        jmp _udeks_program_main

        .assert _udeks_program_entry = $0200, error, "user entry moved"
