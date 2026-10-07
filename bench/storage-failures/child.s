; SPDX-License-Identifier: GPL-3.0-or-later
; Real native SPAWN child holds a written file until parent CANCEL/WAITPID.
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
        ldx #9
copy:   lda name,x
        sta $f367,x
        dex
        bpl copy
        lda #10
        sta $f363
        ldx #3
        lda #6
        jsr request
        lda $f365
        bne fail
        lda $f364
        cmp #4
        bne fail
        ldx #23
data:   txa
        sta $f367,x
        dex
        bpl data
        lda #24
        sta $f363
        ldx #4
        lda #2
        jsr request
        lda $f365
        bne fail
        lda $f364
        cmp #24
        bne fail
        lda #2
        sta $02f0
loop:   lda #0
        sta $f363
        tax
        lda #10
        jsr request
        jmp loop
fail:   lda #$80
        sta $02f0
        rts
request:
        sta $f360
        stx $f362
        ldx #5
sig:    lda signature,x
        sta $f359,x
        dex
        bpl sig
        lda #0
        sta $f366
        lda #1
        sta $f35f
        inc $f361
        jmp $ff16
signature: .byte "UTRQ",0,14
name: .byte "/mnt/CHILD"
        .assert * <= $02f0, lderror, "child stage byte overlaps code"
