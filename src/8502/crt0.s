; SPDX-License-Identifier: GPL-3.0-or-later
;
; Provisional RAM-loaded 8502 entry point. The real boot contract, MMU state,
; interrupt vectors, and image format are roadmap work.

        .export _start
        .import _kernel_main
        .import __BSS_RUN__, __BSS_SIZE__

        .segment "ZEROPAGE"
bss_ptr:
        .res 2

        .segment "STARTUP"
_start:
        sei
        cld
        ldx #$ff
        txs

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
        jsr _kernel_main

halt:
        sei
        jmp halt
