; SPDX-License-Identifier: GPL-3.0-or-later
; Transient UTRQ 0.5 marshaling only. Paths/command policy remain C.
        .setcpu "6502"
        .export _file_request
        .import popa
        .import __BSS_SIZE__, __BSS_RUN__
        .assert __BSS_SIZE__ <= $40, lderror, "filetools UDEX BSS reservation too small"
        .assert __BSS_RUN__+$40 <= $0c00, lderror, "filetools allocation exceeds APP1"
        .segment "CODE"
_file_request:
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
        lda $f364
        ldx #0
        rts
error:  lda #$ff
        ldx #0
        rts
        .segment "RODATA"
signature: .byte "UTRQ",0,5
