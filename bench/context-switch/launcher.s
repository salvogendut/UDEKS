; SPDX-License-Identifier: GPL-3.0-or-later
;
; Bank-0 launcher for the standalone context-switch spike.

        .setcpu "6502"
        .segment "CODE"

RESULT                  = $f180
RESULT_FORMAT           = RESULT + 4
RESULT_CPU              = RESULT + 5
RESULT_STATE            = RESULT + 6
RESULT_ROUNDS           = RESULT + 8

MMU_CR                  = $ff00
MMU_PCR_KERNEL_IO       = $d501
MMU_PCR_KERNEL_FLAT     = $d502
MMU_PCR_WORKER_IO       = $d503
MMU_PCR_WORKER_FLAT     = $d504
MMU_RCR                 = $d506
MMU_PAGE0_PAGE          = $d507
MMU_PAGE0_BANK          = $d508
MMU_PAGE1_PAGE          = $d509
MMU_PAGE1_BANK          = $d50a

GATEWAY                 = $f800
ROUNDS                  = 64
COPY_SOURCE             = $f8
COPY_DESTINATION        = $fa
COPY_LENGTH             = $fc

start:
        sei
        cld
        ldx #$ff
        txs

        lda #$3e
        sta MMU_CR
        sta MMU_PCR_KERNEL_IO
        lda #$3f
        sta MMU_PCR_KERNEL_FLAT
        lda #$7e
        sta MMU_PCR_WORKER_IO
        lda #$7f
        sta MMU_PCR_WORKER_FLAT
        lda #$09
        sta MMU_RCR

        lda #$00
        sta MMU_PAGE0_BANK
        sta MMU_PAGE0_PAGE
        sta MMU_PAGE1_BANK
        lda #$01
        sta MMU_PAGE1_PAGE

        lda #$a0
        sta $8000

        lda #$00
        ldx #$00
clear_result:
        sta RESULT,x
        inx
        cpx #$20
        bne clear_result

        lda #'C'
        sta RESULT+0
        lda #'X'
        sta RESULT+1
        lda #'S'
        sta RESULT+2
        lda #'W'
        sta RESULT+3
        lda #$01
        sta RESULT_FORMAT
        sta RESULT_CPU
        sta RESULT_STATE
        lda #ROUNDS
        sta RESULT_ROUNDS

        lda #<gateway_image
        sta COPY_SOURCE
        lda #>gateway_image
        sta COPY_SOURCE+1
        lda #<GATEWAY
        sta COPY_DESTINATION
        lda #>GATEWAY
        sta COPY_DESTINATION+1
        lda #<(gateway_image_end-gateway_image)
        sta COPY_LENGTH
        lda #>(gateway_image_end-gateway_image)
        sta COPY_LENGTH+1

        ldy #$00
copy_gateway:
        lda COPY_LENGTH
        ora COPY_LENGTH+1
        beq gateway_ready
        lda (COPY_SOURCE),y
        sta (COPY_DESTINATION),y
        inc COPY_SOURCE
        bne source_advanced
        inc COPY_SOURCE+1
source_advanced:
        inc COPY_DESTINATION
        bne destination_advanced
        inc COPY_DESTINATION+1
destination_advanced:
        lda COPY_LENGTH
        bne decrement_low
        dec COPY_LENGTH+1
decrement_low:
        dec COPY_LENGTH
        jmp copy_gateway

gateway_ready:
        jmp GATEWAY

gateway_image:
        .incbin "build/bench/context-switch/gateway.bin"
gateway_image_end:
        .assert gateway_image_end-gateway_image <= $0700, error, "switch core exceeds common reservation"
