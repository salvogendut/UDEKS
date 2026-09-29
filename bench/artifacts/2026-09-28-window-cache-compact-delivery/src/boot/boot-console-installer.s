; SPDX-License-Identifier: GPL-3.0-or-later
;
; Exact-length copy and checksum gate for the boot-only console composer.
; This routine runs from the unused boot-sector tail and is overwritten by
; probe.o immediately after it returns.

        .setcpu "6502"
        .include "boot-console-delivery.inc"

        .export boot_console_installer

BOOT_CHAIN_STATE = $f05c
BOOT_CHAIN_FAILURE = $f05d
BOOT_CONSOLE_INSTALL_FAILURE = $0c

        .segment "CODE"
boot_console_installer:
        lda #$00
        sta boot_console_sum
        sta boot_console_sum+1
        ldx #>BOOT_CONSOLE_IMAGE_SIZE
        ldy #$00

boot_console_page_byte:
boot_console_page_load:
        lda BOOT_CONSOLE_STAGE_SOURCE,y
boot_console_page_store:
        sta BOOT_CONSOLE_DESTINATION,y
        clc
        adc boot_console_sum
        sta boot_console_sum
        bcc boot_console_page_sum_ready
        inc boot_console_sum+1
boot_console_page_sum_ready:
        iny
        bne boot_console_page_byte
        inc boot_console_page_load+2
        inc boot_console_page_store+2
        dex
        bne boot_console_page_byte

        ldy #$00
boot_console_tail_byte:
boot_console_tail_load:
        lda BOOT_CONSOLE_STAGE_SOURCE+$0500,y
        sta BOOT_CONSOLE_DESTINATION+$0500,y
        clc
        adc boot_console_sum
        sta boot_console_sum
        bcc boot_console_tail_sum_ready
        inc boot_console_sum+1
boot_console_tail_sum_ready:
        iny
        cpy #<BOOT_CONSOLE_IMAGE_SIZE
        bne boot_console_tail_byte

        lda boot_console_sum
        cmp #<BOOT_CONSOLE_IMAGE_CHECKSUM
        bne boot_console_failed
        lda boot_console_sum+1
        cmp #>BOOT_CONSOLE_IMAGE_CHECKSUM
        bne boot_console_failed

        ; The bytes following the composer are linked for the common VIC
        ; gateway workspace. Install them there while this one-shot copier is
        ; still alive; init invokes them only after the composer is dead.
        ldy #TASK_SWITCH_ACTIVATION_SIZE-1
copy_task_activation:
        lda TASK_SWITCH_ACTIVATION_DESTINATION,y
        sta $f68a,y
        dey
        bpl copy_task_activation
        lda #$00
        rts

boot_console_failed:
        lda #BOOT_CONSOLE_INSTALL_FAILURE
        sta BOOT_CHAIN_FAILURE
        ora #$80
        sta BOOT_CHAIN_STATE
boot_console_failure_halt:
        jmp boot_console_failure_halt

boot_console_sum:
        .word $0000

boot_console_installer_end:
        .assert boot_console_installer = $0b50, error, "boot-console installer moved"
        .assert boot_console_installer_end <= $0bc0, error, "boot-console installer reaches busy sprite"
