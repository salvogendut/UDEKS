; SPDX-License-Identifier: GPL-3.0-or-later
; Trusted context tags: 1..8 native tasks, 9 synchronous foreground, 10 root
; loader/bootstrap. A tag is NOT the handle identity: its generation is the
; high byte. Retire always closes/releases BEFORE increment (including wrap).
; No untrusted request field supplies a tag. All entries are serialized.
        .setcpu "6502"
        .export _udeks_storage_context_request, _udeks_storage_context_retire
        .export _udeks_storage_generations, _udeks_storage_cleanup_error
        .segment "IECCODE"
_udeks_storage_generations:
        .res 11, 1
_udeks_storage_cleanup_error: .byte 0
        .segment "STORAGECODE"
_udeks_storage_context_request:
        jsr identify
        bcs invalid
        jmp $1200
_udeks_storage_context_retire:
        jsr identify
        bcs invalid
        pha
        jsr $1209
        sta _udeks_storage_cleanup_error
        pla
        tax
        inc _udeks_storage_generations,x
        lda _udeks_storage_cleanup_error
        rts
identify:
        cmp #1
        bcc invalid
        cmp #11
        bcs invalid
        tay
        ldx _udeks_storage_generations,y
        clc
        rts
invalid:
        lda #$ff
        sec
        rts
