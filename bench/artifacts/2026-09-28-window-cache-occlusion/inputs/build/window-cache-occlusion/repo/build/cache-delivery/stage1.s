; SPDX-License-Identifier: GPL-3.0-or-later
;
; Bank-0 native loader. It establishes the proposed MMU contract, confirms
; stage 0 ran, copies a common-RAM gateway into place, and transfers to it.

        .setcpu "6502"
        .include "scheduler-overlay-delivery.inc"
        .segment "CODE"

BOOT_CHAIN              = $f050
BOOT_CHAIN_STATE        = BOOT_CHAIN + 12
BOOT_CHAIN_FAILURE      = BOOT_CHAIN + 13

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

GATEWAY                 = $f700
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

        lda BOOT_CHAIN+0
        cmp #'S'
        bne stage0_missing
        lda BOOT_CHAIN+1
        cmp #'0'
        bne stage0_missing
        lda BOOT_CHAIN+2
        cmp #'O'
        bne stage0_missing
        lda BOOT_CHAIN+3
        cmp #'K'
        bne stage0_missing

        lda #'S'
        sta BOOT_CHAIN+4
        lda #'1'
        sta BOOT_CHAIN+5
        lda #'O'
        sta BOOT_CHAIN+6
        lda #'K'
        sta BOOT_CHAIN+7
        lda #$01
        sta BOOT_CHAIN_STATE
        lda #$00
        sta BOOT_CHAIN_FAILURE

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

stage0_missing:
        lda #$01
        sta BOOT_CHAIN_FAILURE
        lda #$81
        sta BOOT_CHAIN_STATE
halt:
        jmp halt

gateway_image:
        .incbin "build/boot/stage1-gateway.bin"
gateway_image_end:
        .assert gateway_image_end-gateway_image <= $0300, error, "stage-1 gateway exceeds boot reservation"
        .assert gateway_image_end <= $1fbb, error, "stage-1 gateway overlaps the secondary loader"

        ; Called by stage 0 while the inherited KERNAL jump table is still
        ; mapped. LOAD relocates SCHEDOVR into bank 1; UDEKS never calls the
        ; KERNAL again after this routine returns.
        .segment "PRELOAD"
secondary_payload_load:
        lda #$00
        jsr $ff90                   ; SETMSG: keep native boot quiet
        lda #scheduler_name_end-scheduler_name
        ldx #<scheduler_name
        ldy #>scheduler_name
        jsr $ffbd                   ; SETNAM
        lda #$01                    ; data bank 1
        ldx #$00                    ; filename in bank 0
        jsr $ff68                   ; SETBNK
        lda #$00
        ldx $ba                     ; preserve the device that booted us
        cpx #$08
        bcs :+
        ldx #$08
:
        ldy #$00                    ; relocation load
        jsr $ffba                   ; SETLFS
        lda #$00                    ; LOAD, not VERIFY
        ldx #<$4200
        ldy #>$4200
        jsr $ffd5
        bcs secondary_load_failed
        cpx #<SCHEDULER_OVERLAY_END
        bne secondary_load_failed
        cpy #>SCHEDULER_OVERLAY_END
        bne secondary_load_failed
        lda #$00
        rts
secondary_load_failed:
        lda #$0d
        rts
scheduler_name:
        .byte "SCHEDOVR"
scheduler_name_end:
        .assert secondary_payload_load = $1fbb, error, "secondary loader moved"
        .assert scheduler_name_end <= $2000, error, "secondary loader exceeds stage-1 page"
