; SPDX-License-Identifier: GPL-3.0-or-later
;
; Validate and install the scheduler page/tail loaded into bank 1 by stage 0.
; This executes from top common RAM and is replaced by the permanent task gate
; at the scheduler entry.

        .setcpu "6502"
        .include "scheduler-overlay-delivery.inc"
        .segment "CODE"

BOOT_CHAIN_STATE        = $f05c
BOOT_CHAIN_FAILURE      = $f05d
MMU_LCR_KERNEL_FLAT     = $ff02
MMU_LCR_WORKER_FLAT     = $ff04
INSTALL_FAILURE         = $0e
image_sum              = $f8
transfer_byte          = $fa

scheduler_tail_install:
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        ldy #$03
validate_header:
header_load:
        lda SCHEDULER_OVERLAY_LOAD,y
        cmp expected_identity,y
        beq :+
        jmp install_failed_worker
:
        dey
        bpl validate_header

        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        sta image_sum
        sta image_sum+1

        lda #<SCHEDULER_OVERLAY_PAGE_SOURCE
        sta copy_load+1
        lda #>SCHEDULER_OVERLAY_PAGE_SOURCE
        sta copy_load+2
        lda #<$1200
        sta copy_store+1
        lda #>$1200
        sta copy_store+2
        ldx #>SCHEDULER_OVERLAY_PAGE_SIZE
        lda #<SCHEDULER_OVERLAY_PAGE_SIZE
        jsr copy_image

        lda #<SCHEDULER_OVERLAY_TAIL_SOURCE
        sta copy_load+1
        lda #>SCHEDULER_OVERLAY_TAIL_SOURCE
        sta copy_load+2
        lda #<SCHEDULER_OVERLAY_TAIL_DESTINATION
        sta copy_store+1
        lda #>SCHEDULER_OVERLAY_TAIL_DESTINATION
        sta copy_store+2
        ldx #>SCHEDULER_OVERLAY_TAIL_SIZE
        lda #<SCHEDULER_OVERLAY_TAIL_SIZE
        jsr copy_image

        lda image_sum
        cmp #<SCHEDULER_OVERLAY_CHECKSUM
        bne install_failed_kernel
        lda image_sum+1
        cmp #>SCHEDULER_OVERLAY_CHECKSUM
        bne install_failed_kernel

        lda #$00
        ldy #SCHEDULER_OVERLAY_BSS_SIZE-1
clear_bss:
        sta SCHEDULER_OVERLAY_BSS,y
        dey
        bpl clear_bss
        rts

; X is the full-page count and A is the tail count. Operands are patched by
; the caller. The checksum covers page then tail in their linked order.
copy_image:
        pha
copy_page:
        ldy #$00
copy_page_byte:
        jsr copy_one
        iny
        bne copy_page_byte
        inc copy_load+2
        inc copy_store+2
        dex
        bne copy_page
copy_tail:
        pla
        tax
        beq copy_done
        ldy #$00
copy_tail_byte:
        jsr copy_one
        iny
        dex
        bne copy_tail_byte
copy_done:
        rts

copy_one:
        lda #$00
        sta MMU_LCR_WORKER_FLAT
copy_load:
        lda $ffff,y
        sta transfer_byte
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        lda transfer_byte
copy_store:
        sta $ffff,y
        clc
        adc image_sum
        sta image_sum
        bcc :+
        inc image_sum+1
:
        rts

install_failed_worker:
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
install_failed_kernel:
        lda #INSTALL_FAILURE
        sta BOOT_CHAIN_FAILURE
        ora #$80
        sta BOOT_CHAIN_STATE
install_failure_halt:
        jmp install_failure_halt

expected_identity:
        .byte 'U', 'S', 'O', 'V'

installer_end:
        .assert scheduler_tail_install = $ff05, error, "tail installer moved"
        .assert SCHEDULER_OVERLAY_PAGE_SIZE >= $0100, error, "page copy needs one full page"
        .assert SCHEDULER_OVERLAY_TAIL_SIZE >= $0100, error, "tail copy needs one full page"
        .assert SCHEDULER_OVERLAY_BSS_SIZE <= $80, error, "descending BSS clear exceeds branch range"
        .assert installer_end <= $ffc5, error, "tail installer exceeds task-gate reservation"
