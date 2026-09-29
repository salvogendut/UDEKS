; SPDX-License-Identifier: GPL-3.0-or-later
;
; Standalone launcher and fixed task-entry vectors for the compiled-C context
; integration spike. Load at $2800 and enter at $2806.

        .setcpu "6502"
        .import _task_a_main, _task_b_main
        .export _start

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

GATEWAY                 = $f400
DONE_GATE               = $f406
COPY_SOURCE             = $f0
COPY_DESTINATION        = $f2
COPY_LENGTH             = $f4

        .segment "STARTUP"
task_a_vector:
        jmp task_a_entry
task_b_vector:
        jmp task_b_entry
_start:
        .assert _start = $2806, error, "compiled-context entry moved"
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
        bne :+
        inc COPY_SOURCE+1
:
        inc COPY_DESTINATION
        bne :+
        inc COPY_DESTINATION+1
:
        lda COPY_LENGTH
        bne :+
        dec COPY_LENGTH+1
:
        dec COPY_LENGTH
        jmp copy_gateway

gateway_ready:
        jmp GATEWAY

task_a_entry:
        jsr _task_a_main
        lda #$01
        jmp DONE_GATE

task_b_entry:
        jsr _task_b_main
        lda #$02
        jmp DONE_GATE

gateway_image:
        .incbin "build/bench/context-switch-c/gateway.bin"
gateway_image_end:
        .assert gateway_image_end-gateway_image <= $0300, error, "compiled switch core too large"
