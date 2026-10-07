; SPDX-License-Identifier: GPL-3.0-or-later
; Fixed native SPAWN child deliberately holds fd4 until its parent cancels it.
        .setcpu "6502"
        .segment "CODE"
entry:
        lda #1
        sta $02f0
        ldx #37
        lda #0
clear:  sta $f359,x
        dex
        bpl clear
        ldx #5
copy:   lda name,x
        sta $f367,x
        dex
        bpl copy
        lda #6
        sta $f363
        jsr request
        lda $f365
        bne fail
        lda $f364
        cmp #4
        bne fail
        lda #2
        sta $02f0
loop:   lda #0
        sta $f363
        lda #10
        jsr request
        jmp loop
fail:   lda #$80
        sta $02f0
        rts
request:
        sta $f360
        ldx #5
sig:    lda signature,x
        sta $f359,x
        dex
        bpl sig
        lda #0
        sta $f362
        sta $f366
        lda #1
        sta $f35f
        inc $f361
        jmp $ff16
signature: .byte "UTRQ",0,13
name: .byte "/hello"
        .assert * <= $02f0, lderror, "child stage byte overlaps code"
