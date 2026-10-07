; SPDX-License-Identifier: GPL-3.0-or-later
; One-shot bank-1 installer, before the Z80 staging copy overwrites $2300-$3FFF.
; Owns no runtime allocation. IRQs masked, hardware pages pinned to bank 0.
; Enter/return worker I/O with upper common visible. No C runtime required.
        .setcpu "6502"
        .segment "CODE"
        jmp start
        .byte "SINS",0,1
start:
        lda #$7f
        sta $dd0d
        lda $dd0d
        lda $d506
        and #$f7
        sta $d506
        ldx #15
page:   ldy #0
load:   lda $2300,y
store:  sta $f000,y
        iny
        bne load
        inc load+2
        inc store+2
        dex
        bne page
        lda $d506
        ora #8
        sta $d506
        jmp $120c
        .assert * <= $3300, lderror, "storage installer escapes staging page"
