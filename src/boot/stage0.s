; SPDX-License-Identifier: GPL-3.0-or-later
;
; C128 native autoboot sector. KERNAL interprets the header, loads 212 raw
; sectors into bank 0 at $1C00, then calls the inline code below at $0B0E.

        .setcpu "6502"
        .segment "CODE"

BOOT_CHAIN              = $f050
BOOT_CHAIN_STATE        = BOOT_CHAIN + 12
BOOT_CHAIN_BLOCKS       = BOOT_CHAIN + 18
BOOT_CHAIN_VERSION      = BOOT_CHAIN + 19

        .byte 'C', 'B', 'M'
        .word $1c00
        .byte $00
        .byte $d4
        .byte "UDEKS", $00
        .byte $00

stage0:
        sei
        cld
        lda #$00
        ldx #$17
clear_chain:
        sta BOOT_CHAIN,x
        dex
        bpl clear_chain

        lda #'S'
        sta BOOT_CHAIN+0
        lda #'0'
        sta BOOT_CHAIN+1
        lda #'O'
        sta BOOT_CHAIN+2
        lda #'K'
        sta BOOT_CHAIN+3
        lda #$01
        sta BOOT_CHAIN_STATE
        sta BOOT_CHAIN_VERSION
        lda #$d4
        sta BOOT_CHAIN_BLOCKS
        jmp $1c00

stage0_end:
        .assert stage0_end - $0b00 <= $0100, error, "stage 0 exceeds boot sector"
