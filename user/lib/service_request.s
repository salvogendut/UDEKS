; SPDX-License-Identifier: GPL-3.0-or-later
; Synchronous console client: private runtime sp=$02, module sp=$06.
; No private kernel symbols or shared scratch outside the request record.
        .setcpu "6502"
        .export _udeks_service_control
        .import popa, _udeks_errno
        .importzp sp
        .assert sp = $02, lderror, "service console SDK requires private user ZP"
        .segment "BSS"
saved_zp: .res 30                  ; $02-$1F, never write CPU ports $00/$01
sequence: .res 1
        .segment "RODATA"
signature: .byte "UTRQ",0,19
        .segment "CODE"
_udeks_service_control:
        sta $f368
        stx $f369
        jsr popa
        sta $f367
        ldx #5
header: lda signature,x
        sta $f359,x
        dex
        bpl header
        lda #28
        sta $f360
        lda #3
        sta $f363
        lda #0
        sta $f362
        sta $f364
        sta $f365
        sta $f366
        inc $f361
        lda $f361
        sta sequence
        lda #1
        sta $f35f
        php
        cld
        ldx #31
save:   lda $00,x
        sta saved_zp-2,x
        dex
        cpx #1
        bne save
        lda $02
        sta $06
        lda $03
        sta $07
        jsr $cf30
        ldx #31
restore:
        lda saved_zp-2,x
        sta $00,x
        dex
        cpx #1
        bne restore
        plp
        lda $f361
        cmp sequence
        bne protocol
        lda $f35f
        cmp #2
        bne error
        lda $f365
        bne error
        lda $f364
        cmp #1
        bne protocol
        lda $f367
        cmp #3
        bcs protocol
        ldx #0
        stx _udeks_errno
        rts
protocol:
        lda #71
        bne failed
error:  lda $f365
        bne failed
        lda #5
failed: sta _udeks_errno
        lda #$ff
        ldx #0
        rts
