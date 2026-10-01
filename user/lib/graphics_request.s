; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .export _gfx_request, _gfx_sleep
        .segment "CODE"
_gfx_request:
        sta $f367
        lda #24
        sta $f363
        lda #23
        bne request
_gfx_sleep:
        lda #2
        sta $f367
        sta $f363
        lda #0
        sta $f368
        lda #13
request:
        sta $f360
        ldx #5
copy:   lda signature,x
        sta $f359,x
        dex
        bpl copy
        lda #0
        sta $f362
        sta $f366
        lda #1
        sta $f35f
        inc $f361
        jsr $ff16
        lda $f365
        ldx #0
        rts
        .segment "RODATA"
signature: .byte "UTRQ",0,9
