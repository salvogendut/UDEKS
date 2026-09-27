; SPDX-License-Identifier: GPL-3.0-or-later
;
; Boot-only exact-length copy and checksum gate. This routine is staged after
; the capability image in the lower VIC shadow and is erased with that shadow
; by crt0 after it has copied the service into application slot 1.

        .setcpu "6502"
        .include "capability-delivery.inc"

        .export capability_installer

BOOT_CHAIN_STATE = $f05c
BOOT_CHAIN_FAILURE = $f05d
CAPABILITY_INSTALL_FAILURE = $0b

        .segment "CODE"
capability_installer:
        lda #$00
        sta capability_sum
        sta capability_sum+1
        ldx #>CAPABILITY_IMAGE_SIZE
        ldy #$00

capability_page_byte:
capability_page_load:
        lda CAPABILITY_STAGE_SOURCE,y
capability_page_store:
        sta CAPABILITY_DESTINATION,y
        clc
        adc capability_sum
        sta capability_sum
        bcc capability_page_sum_ready
        inc capability_sum+1
capability_page_sum_ready:
        iny
        bne capability_page_byte
        inc capability_page_load+2
        inc capability_page_store+2
        dex
        bne capability_page_byte

        ldy #$00
capability_tail_byte:
capability_tail_load:
        lda CAPABILITY_STAGE_SOURCE+$0300,y
        sta CAPABILITY_DESTINATION+$0300,y
        clc
        adc capability_sum
        sta capability_sum
        bcc capability_tail_sum_ready
        inc capability_sum+1
capability_tail_sum_ready:
        iny
        cpy #<CAPABILITY_IMAGE_SIZE
        bne capability_tail_byte

        lda capability_sum
        cmp #<CAPABILITY_IMAGE_CHECKSUM
        bne capability_failed
        lda capability_sum+1
        cmp #>CAPABILITY_IMAGE_CHECKSUM
        bne capability_failed
        lda #$00
        sta CAPABILITY_BSS
        rts

capability_failed:
        lda #CAPABILITY_INSTALL_FAILURE
        sta BOOT_CHAIN_FAILURE
        ora #$80
        sta BOOT_CHAIN_STATE
        lda #$01
        rts

capability_sum:
        .word $0000
