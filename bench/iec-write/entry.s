; SPDX-License-Identifier: GPL-3.0-or-later
; Destructive-to-DISPOSABLE-media standalone probe; never in the boot image.
        .setcpu "6502"
        .export __STARTUP__ : absolute = 1
        .import _main, zerobss
        .importzp sp
        .segment "STARTUP"
        sei
        cld
        ldx #$ff
        txs
        lda #$3e                ; bank 0 RAM + native I/O
        sta $ff00
        lda #$00
        sta sp
        lda #$70
        sta sp+1
        jsr zerobss
        jsr _main
halt:   jmp halt
