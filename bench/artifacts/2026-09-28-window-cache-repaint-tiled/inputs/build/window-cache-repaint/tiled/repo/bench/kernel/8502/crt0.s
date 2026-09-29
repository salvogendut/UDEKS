; SPDX-License-Identifier: GPL-3.0-or-later

        .export _start
        .import _bench_main
        .import __BSS_RUN__, __BSS_SIZE__
        .importzp sp

        .segment "ZEROPAGE"
bss_ptr:
        .res 2

        .segment "STARTUP"
_start:
        sei
        cld
        ldx #$ff
        txs
        lda #$3e
        sta $ff00

        lda #<$d000
        sta sp
        lda #>$d000
        sta sp+1

        lda #<__BSS_RUN__
        sta bss_ptr
        lda #>__BSS_RUN__
        sta bss_ptr+1
        lda #$00
        ldx #>__BSS_SIZE__
        beq clear_tail
        ldy #$00
clear_page:
        sta (bss_ptr),y
        iny
        bne clear_page
        inc bss_ptr+1
        dex
        bne clear_page
clear_tail:
        ldy #$00
clear_tail_loop:
        cpy #<__BSS_SIZE__
        beq bss_done
        sta (bss_ptr),y
        iny
        bne clear_tail_loop

bss_done:
        lda $d030
        and #$01
        clc
        adc #$01
        sta $f186               ; configuration: 1 MHz or 2 MHz
        jsr _bench_main
halt:
        sei
        jmp halt
