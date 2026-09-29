; SPDX-License-Identifier: GPL-3.0-or-later
;
; Runs from top common RAM while the 8502 changes complete MMU profiles.

        .setcpu "6502"
        .segment "CODE"

RESULT                  = $f100
RESULT_STATE            = RESULT + 5
RESULT_TESTS            = RESULT + 6
RESULT_PASSED           = RESULT + 7
RESULT_FAILURE          = RESULT + 8
RESULT_PROFILE          = RESULT + 9
RESULT_EXPECTED         = RESULT + 10
RESULT_ACTUAL           = RESULT + 11
OBSERVATIONS            = RESULT + 16
COMMON_SENTINEL         = RESULT + 64

MMU_CR                  = $ff00
MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_KERNEL_FLAT     = $ff02
MMU_LCR_WORKER_IO       = $ff03
MMU_LCR_WORKER_FLAT     = $ff04
MMU_CR_IO               = $d500
MMU_MODE                = $d505
MMU_RCR                 = $d506
MMU_PAGE0_PAGE          = $d507
MMU_PAGE0_BANK          = $d508
MMU_PAGE1_PAGE          = $d509
MMU_PAGE1_BANK          = $d50a

PROFILE_KERNEL_IO       = 1
PROFILE_KERNEL_FLAT     = 2
PROFILE_WORKER_IO       = 3
PROFILE_WORKER_FLAT     = 4

        .macro check_a expected, failure_code
        .local passed
        sta RESULT_ACTUAL
        lda #expected
        sta RESULT_EXPECTED
        inc RESULT_TESTS
        lda RESULT_ACTUAL
        cmp #expected
        beq passed
        lda #failure_code
        sta RESULT_FAILURE
        jmp failure
passed:
        inc RESULT_PASSED
        .endmacro

gateway_start:
        lda #$5c
        sta COMMON_SENTINEL

        lda #PROFILE_KERNEL_IO
        sta RESULT_PROFILE
        lda MMU_CR
        sta OBSERVATIONS+0
        check_a $3e, $01
        lda MMU_RCR
        and #$4f
        sta OBSERVATIONS+1
        check_a $09, $02
        lda MMU_MODE
        and #$41
        sta OBSERVATIONS+2
        check_a $01, $03

        ; Bank 0 with I/O hidden: seed and verify private RAM below $D500.
        lda #PROFILE_KERNEL_FLAT
        sta RESULT_PROFILE
        sta MMU_LCR_KERNEL_FLAT
        lda MMU_CR
        sta OBSERVATIONS+3
        check_a $3f, $04
        lda #$d0
        sta $d500
        lda $d500
        sta OBSERVATIONS+4
        check_a $d0, $05
        lda #$a0
        sta $8000

        ; Bank 1 flat: seed independent private RAM and relocation targets.
        lda #PROFILE_WORKER_FLAT
        sta RESULT_PROFILE
        sta MMU_LCR_WORKER_FLAT
        lda MMU_CR
        sta OBSERVATIONS+5
        check_a $7f, $06
        lda #$d1
        sta $d500
        lda $d500
        sta OBSERVATIONS+6
        check_a $d1, $07
        lda #$a1
        sta $8000
        lda #$5a
        sta $8002
        lda #$a5
        sta $8100

        ; Bank 1 with I/O visible: $D500 is the MMU again, not private RAM.
        lda #PROFILE_WORKER_IO
        sta RESULT_PROFILE
        sta MMU_LCR_WORKER_IO
        lda MMU_CR
        sta OBSERVATIONS+7
        check_a $7e, $08
        lda MMU_CR_IO
        sta OBSERVATIONS+8
        check_a $7e, $09
        lda $8000
        sta OBSERVATIONS+9
        check_a $a1, $0a

        ; Return to bank 0 flat and prove both banks retained distinct bytes.
        lda #PROFILE_KERNEL_FLAT
        sta RESULT_PROFILE
        sta MMU_LCR_KERNEL_FLAT
        lda $8000
        sta OBSERVATIONS+10
        check_a $a0, $0b
        lda $d500
        sta OBSERVATIONS+11
        check_a $d0, $0c

        lda #PROFILE_KERNEL_IO
        sta RESULT_PROFILE
        sta MMU_LCR_KERNEL_IO
        lda MMU_CR_IO
        sta OBSERVATIONS+12
        check_a $3e, $0d
        lda COMMON_SENTINEL
        sta OBSERVATIONS+13
        check_a $5c, $0e

        ; Relocate logical pages zero and one into bank-1 pages $80/$81.
        ; No stack operation is allowed until the original page one is restored.
        lda #$01
        sta MMU_PAGE0_BANK
        lda #$80
        sta MMU_PAGE0_PAGE
        lda #$01
        sta MMU_PAGE1_BANK
        lda #$81
        sta MMU_PAGE1_PAGE

        lda $0002
        sta OBSERVATIONS+14
        check_a $5a, $0f
        lda $0100
        sta OBSERVATIONS+15
        check_a $a5, $10
        lda #$6b
        sta $0002
        lda #$b6
        sta $0100

        ; Restore the architectural pages before verifying physical targets.
        lda #$00
        sta MMU_PAGE0_BANK
        sta MMU_PAGE0_PAGE
        sta MMU_PAGE1_BANK
        lda #$01
        sta MMU_PAGE1_PAGE

        lda #PROFILE_WORKER_FLAT
        sta RESULT_PROFILE
        sta MMU_LCR_WORKER_FLAT
        lda $8002
        sta OBSERVATIONS+16
        check_a $6b, $11
        lda $8100
        sta OBSERVATIONS+17
        check_a $b6, $12

        lda #PROFILE_KERNEL_IO
        sta RESULT_PROFILE
        sta MMU_LCR_KERNEL_IO
        lda MMU_CR
        sta OBSERVATIONS+18
        check_a $3e, $13
        lda MMU_PAGE0_PAGE
        sta OBSERVATIONS+19
        check_a $00, $14
        lda MMU_PAGE0_BANK
        and #$01
        sta OBSERVATIONS+20
        check_a $00, $15
        lda MMU_PAGE1_PAGE
        sta OBSERVATIONS+21
        check_a $01, $16
        lda MMU_PAGE1_BANK
        and #$01
        sta OBSERVATIONS+22
        check_a $00, $17

        lda #$00
        sta RESULT_PROFILE
        lda #$02
        sta RESULT_STATE
halt:
        lda #$00
        beq halt

failure:
        ; Recover a debuggable bank-0/I/O state without using the stack.
        lda #$00
        sta MMU_PAGE0_BANK
        sta MMU_PAGE0_PAGE
        sta MMU_PAGE1_BANK
        lda #$01
        sta MMU_PAGE1_PAGE
        lda #$00
        sta MMU_LCR_KERNEL_IO
        lda #$80
        ora RESULT_FAILURE
        sta RESULT_STATE
failure_halt:
        lda #$00
        beq failure_halt

gateway_end:
        .assert gateway_end - gateway_start <= $0800, error, "gateway exceeds common code reservation"
