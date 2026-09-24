; SPDX-License-Identifier: GPL-3.0-or-later
;
; Executes from top common RAM while copying the Z80 staging image from bank 0
; $D000-$EFFF to its resident bank-1 location at $2000-$3FFF.

        .setcpu "6502"
        .segment "CODE"

BOOT_CHAIN              = $f050
BOOT_CHAIN_STATE        = BOOT_CHAIN + 12
BOOT_CHAIN_FAILURE      = BOOT_CHAIN + 13
BOOT_CHAIN_SOURCE_SUM   = BOOT_CHAIN + 14
BOOT_CHAIN_DEST_SUM     = BOOT_CHAIN + 16

MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_KERNEL_FLAT     = $ff02
MMU_LCR_WORKER_FLAT     = $ff04

gateway_start:
        ; Confirm that the two nominal banks are physically distinct.
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        lda #$a0
        sta $8000
        sta MMU_LCR_WORKER_FLAT
        lda #$a1
        sta $8000
        cmp $8000
        beq bank1_ready
        jmp bank1_failure
bank1_ready:
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        lda $8000
        cmp #$a0
        beq bank0_ready
        jmp bank0_failure
bank0_ready:

        lda #$00
        sta source_sum_low
        sta source_sum_high
        lda #$20
        sta page_count
        lda #$d0
        sta source_load+2
        lda #$20
        sta destination_store+2

copy_page:
        ldy #$00
copy_byte:
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
source_load:
        lda $d000,y
        sta transfer_byte
        clc
        adc source_sum_low
        sta source_sum_low
        bcc source_sum_ready
        inc source_sum_high
source_sum_ready:
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        lda transfer_byte
destination_store:
        sta $2000,y
        iny
        bne copy_byte
        inc source_load+2
        inc destination_store+2
        dec page_count
        bne copy_page

        ; Compare every installed byte and independently checksum bank 1.
        lda #$00
        sta destination_sum_low
        sta destination_sum_high
        lda #$20
        sta page_count
        lda #$d0
        sta source_verify+2
        lda #$20
        sta destination_verify+2

verify_page:
        ldy #$00
verify_byte:
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
source_verify:
        lda $d000,y
        sta transfer_byte
        lda #$00
        sta MMU_LCR_WORKER_FLAT
destination_verify:
        lda $2000,y
        cmp transfer_byte
        bne copy_failure
        clc
        adc destination_sum_low
        sta destination_sum_low
        bcc destination_sum_ready
        inc destination_sum_high
destination_sum_ready:
        iny
        bne verify_byte
        inc source_verify+2
        inc destination_verify+2
        dec page_count
        bne verify_page

        lda source_sum_low
        cmp destination_sum_low
        bne checksum_failure
        sta BOOT_CHAIN_SOURCE_SUM
        lda source_sum_high
        cmp destination_sum_high
        bne checksum_failure
        sta BOOT_CHAIN_SOURCE_SUM+1
        lda destination_sum_low
        sta BOOT_CHAIN_DEST_SUM
        lda destination_sum_high
        sta BOOT_CHAIN_DEST_SUM+1

        lda #'Z'
        sta BOOT_CHAIN+8
        lda #'8'
        sta BOOT_CHAIN+9
        lda #'0'
        sta BOOT_CHAIN+10
        lda #'!'
        sta BOOT_CHAIN+11
        lda #$00
        sta BOOT_CHAIN_FAILURE
        lda #$02
        sta BOOT_CHAIN_STATE
        lda #$00
        sta MMU_LCR_KERNEL_IO
        jmp $2000

bank1_failure:
        lda #$02
        bne failure
bank0_failure:
        lda #$03
        bne failure
copy_failure:
        lda #$04
        bne failure
checksum_failure:
        lda #$05
failure:
        sta BOOT_CHAIN_FAILURE
        ora #$80
        sta BOOT_CHAIN_STATE
        lda #$00
        sta MMU_LCR_KERNEL_IO
failure_halt:
        jmp failure_halt

page_count:             .byte $00
transfer_byte:          .byte $00
source_sum_low:         .byte $00
source_sum_high:        .byte $00
destination_sum_low:    .byte $00
destination_sum_high:   .byte $00

gateway_end:
        .assert gateway_end - gateway_start <= $0700, error, "stage-1 gateway exceeds common region"
