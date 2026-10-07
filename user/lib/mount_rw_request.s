; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .export _udeks_mount_rw_request
        .import popa
        .segment "CODE"
_udeks_mount_rw_request:
        sta path_count+1
        jsr popa
        sta $f366
        jsr popa
        sta $f360
        jsr popa
        sta $f367
        ldx #0
        lda $f360
        cmp #17
        bne :+
        inx
:       ldy #0
path:   lda mount_path,y
        sta $f367,x
        inx
        iny
path_count:
        cpy #4
        bcc path
        stx $f363
        ldx #5
header: lda signature,x
        sta $f359,x
        dex
        bpl header
        lda #0
        sta $f362
        sta $f364
        sta $f365
        inc $f361
        lda #1
        sta $f35f
        jsr $cf30
        lda $f35f
        cmp #2
        bne error
        lda $f365
        ldx #0
        rts
error:  lda $f365
        bne :+
        lda #5
:       ldx #0
        rts
        .segment "RODATA"
signature: .byte "UTRQ",0,14
mount_path: .byte "/mnt"
