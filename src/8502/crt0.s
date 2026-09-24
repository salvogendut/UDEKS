; SPDX-License-Identifier: GPL-3.0-or-later
;
; RAM-loaded 8502 entry point. The loader contract guarantees that this image
; is resident in RAM bank 0 at $2000 before control arrives here.

        .include "mmu.inc"

        .export _start
        .import _kernel_main
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

        ; Establish the four native configurations before C code observes the
        ; machine. $FF00 remains reachable regardless of the inherited I/O map.
        lda #UDEKS_MMU_KERNEL_IO
        sta MMU_CR_ALWAYS
        sta MMU_PCR_KERNEL_IO
        lda #UDEKS_MMU_KERNEL_FLAT
        sta MMU_PCR_KERNEL_FLAT
        lda #UDEKS_MMU_WORKER_IO
        sta MMU_PCR_WORKER_IO
        lda #UDEKS_MMU_WORKER_FLAT
        sta MMU_PCR_WORKER_FLAT

        ; Share bank-0 $F000-$FFFF at the top of both bank views. Leave the
        ; VIC on bank 0 until the display service assigns its bank-1 window.
        lda #UDEKS_MMU_RCR_TOP_4K
        sta MMU_RCR

        ; Start with the architectural zero page and hardware stack in bank 0.
        ; The high-byte latches must be written before their low-byte commits.
        lda #$00
        sta MMU_PAGE0_BANK
        sta MMU_PAGE0_PAGE
        sta MMU_PAGE1_BANK
        lda #$01
        sta MMU_PAGE1_PAGE

        ; cc65's parameter/local stack lives in the reserved bank-0 high-RAM
        ; window and grows downward. This makes ordinary C service code legal;
        ; the hardware stack remains on physical bank-0 page one.
        lda #<UDEKS_C_STACK_TOP
        sta sp
        lda #>UDEKS_C_STACK_TOP
        sta sp+1

        ; Publish a compact readback record in common RAM. Emulator and
        ; hardware smoke tests use this before any console exists.
        lda #'U'
        sta BOOT_STATUS+0
        lda #'M'
        sta BOOT_STATUS+1
        sta BOOT_STATUS+2
        lda #'U'
        sta BOOT_STATUS+3
        lda #$01
        sta BOOT_STATUS+4
        sta BOOT_STATUS_STATE
        lda MMU_CR_ALWAYS
        sta BOOT_STATUS+6
        lda MMU_RCR
        sta BOOT_STATUS+7
        lda MMU_PAGE0_PAGE
        sta BOOT_STATUS+8
        lda MMU_PAGE0_BANK
        sta BOOT_STATUS+9
        lda MMU_PAGE1_PAGE
        sta BOOT_STATUS+10
        lda MMU_PAGE1_BANK
        sta BOOT_STATUS+11
        lda MMU_MODE
        sta BOOT_STATUS+12
        lda #$02
        sta BOOT_STATUS_STATE

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
