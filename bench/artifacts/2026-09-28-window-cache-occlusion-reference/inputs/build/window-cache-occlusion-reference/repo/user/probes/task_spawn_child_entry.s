; SPDX-License-Identifier: GPL-3.0-or-later
;
; Probe entry veneer matching user/lib/entry.s, with a common-RAM capture of
; the launcher-created hardware-stack return frame before cc65 uses it.

        .setcpu "6502"
        .segment "STARTUP"

        .export _udeks_program_entry
        .import _udeks_program_main
        .import pusha
        .importzp tmp1, ptr1

_udeks_program_entry:
        tsx
        stx $f2a2
        lda $01fe
        sta $f2a0
        lda $01ff
        sta $f2a1

        lda #$00
        sta tmp1
        sta ptr1
        sta ptr1+1
        jsr pusha
        lda #$00
        tax
        jmp _udeks_program_main

        .assert _udeks_program_entry = $0200, error, "SPAWN child entry moved"
