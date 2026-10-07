; SPDX-License-Identifier: GPL-3.0-or-later
; Transient console SDK uses CF30, never the native bank-task FF16 entry.
        .setcpu "6502"
        .export _udeks_fs_request
        .import popa, _udeks_errno
        .segment "CODE"
_udeks_fs_request:
        sta $f363
        jsr popa
        sta $f362
        jsr popa
        sta $f360
        ldx #5
copy:   lda signature,x
        sta $f359,x
        dex
        bpl copy
        lda #0
        sta $f364
        sta $f365
        sta $f366
        inc $f361
        lda #1
        sta $f35f
        jsr $cf30
        lda $f35f
        cmp #2
        bne error
        lda $f365
        bne error
        sta _udeks_errno
        lda $f364
        ldx #0
        rts
error:  lda $f365
        bne :+
        lda #5
:       sta _udeks_errno
        lda #$ff
        ldx #0
        rts
        .segment "RODATA"
signature: .byte "UTRQ",0,14
