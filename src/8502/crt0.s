; SPDX-License-Identifier: GPL-3.0-or-later
;
; Boot-time 8502 entry point. Stage 1 stages this image in the VIC shadow at
; $AE00, copies it over the dead stage-1 page at $1C00, and enters there. It
; is not part of the resident kernel: the resident core starts at $2000, and
; the $1C00 page becomes reclaimable once this code has run.

        .include "mmu.inc"

        .export _start
        .import _kernel_main
        .import __BSS_RUN__, __BSS_SIZE__
        .import __VICSHADOW_RUN__, __VICSHADOW_SIZE__
        .importzp sp

        ; Stage 1 retires its own $F8-$FC copy scratch before entering here.
        CLEAR_POINTER = $f8

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
        sta CLEAR_POINTER
        lda #>__BSS_RUN__
        sta CLEAR_POINTER+1

        lda #$00
        ldx #>__BSS_SIZE__
        beq clear_tail
        ldy #$00
clear_page:
        sta (CLEAR_POINTER),y
        iny
        bne clear_page
        inc CLEAR_POINTER+1
        dex
        bne clear_page

clear_tail:
        ldy #$00
clear_tail_loop:
        cpy #<__BSS_SIZE__
        beq bss_done
        sta (CLEAR_POINTER),y
        iny
        bne clear_tail_loop

bss_done:
        ; The VIC shadow is a separate BSS segment placed after ordinary BSS,
        ; so the linker-generated bounds are the only safe way to clear it.
        ; Stage 1 no longer clears any shadow range: staging payloads now live
        ; inside the shadow, and the reclaimed tail above it must survive.
        lda #<__VICSHADOW_RUN__
        sta CLEAR_POINTER
        lda #>__VICSHADOW_RUN__
        sta CLEAR_POINTER+1

        lda #$00
        ldx #>__VICSHADOW_SIZE__
        beq shadow_tail
        ldy #$00
shadow_page:
        sta (CLEAR_POINTER),y
        iny
        bne shadow_page
        inc CLEAR_POINTER+1
        dex
        bne shadow_page

shadow_tail:
        ldy #$00
shadow_tail_loop:
        cpy #<__VICSHADOW_SIZE__
        beq shadow_done
        sta (CLEAR_POINTER),y
        iny
        bne shadow_tail_loop

shadow_done:
        ; Enter the resident core without a return address: the $1C00 page is
        ; reclaimable and must not hold a live frame.
        jmp _kernel_main
