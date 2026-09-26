; SPDX-License-Identifier: GPL-3.0-or-later
;
; Runs from top common RAM while it alternates two synthetic 8502 tasks with
; relocated page-zero and page-one allocations and different MMU profiles.

        .setcpu "6502"
        .segment "CODE"

RESULT                  = $f180
RESULT_FORMAT           = RESULT + 4
RESULT_CPU              = RESULT + 5
RESULT_STATE            = RESULT + 6
RESULT_FAILURE          = RESULT + 7
RESULT_ROUNDS           = RESULT + 8
RESULT_SWITCHES         = RESULT + 9
RESULT_SWITCHES_HI      = RESULT + 10
RESULT_IRQ              = RESULT + 11
RESULT_CHECKS_OK        = RESULT + 12
RESULT_CHECKS_BAD       = RESULT + 13
RESULT_CANARY_BAD       = RESULT + 14
RESULT_FLAGS            = RESULT + 15
RESULT_STRATEGY         = RESULT + 16
RESULT_CURRENT          = RESULT + 17
RESULT_STEP_A           = RESULT + 18
RESULT_STEP_B           = RESULT + 19
RESULT_XFER_LO          = RESULT + 20
RESULT_XFER_HI          = RESULT + 21

MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_WORKER_IO       = $ff03
MMU_PAGE0_PAGE          = $d507
MMU_PAGE0_BANK          = $d508
MMU_PAGE1_PAGE          = $d509
MMU_PAGE1_BANK          = $d50a
IRQ_VECTOR_LO           = $fffe
IRQ_VECTOR_HI           = $ffff
CIA1_ICR                = $dc0d
CIA1_TA_LO              = $dc04
CIA1_TA_HI              = $dc05
CIA1_CRA                = $dc0e
CIA2_ICR                = $dd0d
VIC_IRQ_STATUS          = $d019
VIC_IRQ_MASK            = $d01a

PROFILE_KERNEL_IO       = 1
PROFILE_WORKER_IO       = 3

SENTINEL_A              = $a5
SENTINEL_B              = $5a
STACK_A                 = $3c
STACK_B                 = $c3
BANK_A                  = $a0
BANK_B                  = $b0
ROUNDS                  = 64
SWITCH_BUDGET_HI        = $04
TIMER_PERIOD            = $80

ZP_SENTINEL             = $02
ZP_STEP                 = $03
ZP_SEEN_A               = $07
ZP_SEEN_X               = $08
ZP_SEEN_Y               = $09
ZP_STATE                = $0a
STACK_CANARY            = $0100

STRATEGY_RELOCATE       = 2
FLAG_RELOCATE           = $02

        .macro require_imm value, code
        .local ok
        cmp #value
        beq ok
        lda #code
        jmp fail_common
ok:
        .endmacro

        .macro require_mem address, code
        .local ok
        cmp address
        beq ok
        lda #code
        jmp fail_common
ok:
        .endmacro

gateway_start:
        ; Seed the bank-1 sentinel and both tasks' relocated pages.
        lda #PROFILE_WORKER_IO
        sta MMU_LCR_WORKER_IO
        lda #BANK_B
        sta $8000
        lda #PROFILE_KERNEL_IO
        sta MMU_LCR_KERNEL_IO

        lda #$01
        sta MMU_PAGE0_BANK
        sta MMU_PAGE1_BANK
        lda #$80
        sta MMU_PAGE0_PAGE
        lda #$81
        sta MMU_PAGE1_PAGE
        lda #SENTINEL_A
        sta ZP_SENTINEL
        lda #STACK_A
        sta STACK_CANARY
        lda #$00
        sta ZP_STEP
        sta ZP_STATE

        lda #$82
        sta MMU_PAGE0_PAGE
        lda #$83
        sta MMU_PAGE1_PAGE
        lda #SENTINEL_B
        sta ZP_SENTINEL
        lda #STACK_B
        sta STACK_CANARY
        lda #$00
        sta ZP_STEP
        sta ZP_STATE

        lda #$00
        sta MMU_PAGE0_BANK
        sta MMU_PAGE0_PAGE
        sta MMU_PAGE1_BANK
        lda #$01
        sta MMU_PAGE1_PAGE

        lda #<irq_handler
        sta IRQ_VECTOR_LO
        lda #>irq_handler
        sta IRQ_VECTOR_HI

        lda #$00
        sta VIC_IRQ_MASK
        lda VIC_IRQ_STATUS
        sta VIC_IRQ_STATUS
        lda #$7f
        sta CIA2_ICR
        lda #$7f
        sta CIA1_ICR
        lda #$00
        sta CIA1_CRA
        lda #TIMER_PERIOD
        sta CIA1_TA_LO
        lda #$00
        sta CIA1_TA_HI
        lda #$81
        sta CIA1_ICR
        lda #$11
        sta CIA1_CRA

        lda #STRATEGY_RELOCATE
        sta RESULT_STRATEGY
        lda #$01
        sta current
        jmp dispatch_task

; Dispatch the current task: select its ownership and profile, restore its
; context, and resume through the return address kept on its own stack.
dispatch_task:
        lda current
        sta RESULT_CURRENT
        lda #PROFILE_KERNEL_IO
        sta MMU_LCR_KERNEL_IO

        lda current
        cmp #1
        bne dispatch_task_b

        lda #$01
        sta MMU_PAGE0_BANK
        sta MMU_PAGE1_BANK
        lda #$80
        sta MMU_PAGE0_PAGE
        lda #$81
        sta MMU_PAGE1_PAGE

        lda a_primed
        bne dispatch_task_a_ready
        lda #<task_entry
        sta save_pc
        lda #>task_entry
        sta save_pc+1
        lda #$ff
        sta save_sp
        lda #$01
        sta save_a
        lda #SENTINEL_A
        sta save_x
        lda #$33
        sta save_y
        lda #$05
        sta save_p
        lda #$01
        sta a_primed
dispatch_task_a_ready:
        lda #PROFILE_KERNEL_IO
        sta MMU_LCR_KERNEL_IO
        jmp dispatch_finish

dispatch_task_b:
        lda #$01
        sta MMU_PAGE0_BANK
        sta MMU_PAGE1_BANK
        lda #$82
        sta MMU_PAGE0_PAGE
        lda #$83
        sta MMU_PAGE1_PAGE

        lda b_primed
        bne dispatch_task_b_ready
        lda #<task_entry
        sta save_pc
        lda #>task_entry
        sta save_pc+1
        lda #$ff
        sta save_sp
        lda #$02
        sta save_a
        lda #SENTINEL_B
        sta save_x
        lda #$33
        sta save_y
        lda #$05
        sta save_p
        lda #$01
        sta b_primed
dispatch_task_b_ready:
        lda #PROFILE_WORKER_IO
        sta MMU_LCR_WORKER_IO

dispatch_finish:
        lda save_a
        sta disp_a
        lda save_x
        sta disp_x
        lda save_y
        sta disp_y

        ldx save_sp
        txs
        lda save_p
        pha
        plp
        lda save_a
        ldx save_x
        ldy save_y
        jmp (save_pc)

; A task reaches here with jmp after storing its resume address. The core
; saves registers, processor status, and the stack pointer.
yield_core:
        sei
        sta save_a
        stx save_x
        sty save_y
        php
        pla
        sta save_p
        tsx
        stx save_sp

        lda ZP_SEEN_A
        require_mem disp_a, 5
        lda ZP_SEEN_X
        require_mem disp_x, 5
        lda ZP_SEEN_Y
        require_mem disp_y, 5

        lda ZP_STATE
        require_imm $00, 8

        lda save_y
        require_imm $33, 5
        lda save_x
        require_mem ZP_SENTINEL, 5
        lda save_a
        require_mem ZP_STEP, 5

        lda save_p
        and #$01
        bne :+
        lda #6
        jmp fail_common
:

        lda current
        cmp #1
        bne yield_validate_b

        lda ZP_SENTINEL
        cmp #SENTINEL_A
        beq :+
        lda #2
        jmp fail_canary
:
        lda STACK_CANARY
        cmp #STACK_A
        beq :+
        lda #3
        jmp fail_canary
:
        lda $8000
        require_imm BANK_A, 4

        lda a_step
        clc
        adc #$01
        cmp ZP_STEP
        beq :+
        lda #7
        jmp fail_common
:
        lda ZP_STEP
        sta a_step
        sta RESULT_STEP_A
        jmp yield_accept

yield_validate_b:
        lda ZP_SENTINEL
        cmp #SENTINEL_B
        beq :+
        lda #2
        jmp fail_canary
:
        lda STACK_CANARY
        cmp #STACK_B
        beq :+
        lda #3
        jmp fail_canary
:
        lda $8000
        require_imm BANK_B, 4

        lda b_step
        clc
        adc #$01
        cmp ZP_STEP
        beq :+
        lda #7
        jmp fail_common
:
        lda ZP_STEP
        sta b_step
        sta RESULT_STEP_B

yield_accept:
        inc checks_ok
        inc switches_lo
        bne :+
        inc switches_hi
:
        lda switches_hi
        cmp #SWITCH_BUDGET_HI
        bcc :+
        lda #10
        jmp fail_common
:
        lda current
        cmp #1
        bne yield_after_b
        lda #2
        sta current
        jmp dispatch_task
yield_after_b:
        inc round_index
        lda round_index
        cmp #ROUNDS
        beq strategy_done
        lda #1
        sta current
        jmp dispatch_task

strategy_done:
        lda switches_lo
        sta RESULT_SWITCHES
        lda switches_hi
        sta RESULT_SWITCHES_HI
        lda checks_ok
        sta RESULT_CHECKS_OK
        lda irq_count
        sta RESULT_IRQ
        bne :+
        lda #9
        jmp fail_common
:
        lda #FLAG_RELOCATE
        sta RESULT_FLAGS
        lda #$00
        sta RESULT_XFER_LO
        sta RESULT_XFER_HI
        lda #$02
        sta RESULT_STATE

        lda #PROFILE_KERNEL_IO
        sta MMU_LCR_KERNEL_IO
        lda #$00
        sta MMU_PAGE0_BANK
        sta MMU_PAGE0_PAGE
        sta MMU_PAGE1_BANK
        lda #$01
        sta MMU_PAGE1_PAGE
        ldx #$ff
        txs
halt:
        jmp halt

fail_canary:
        inc canary_bad
fail_common:
        sta fail_code
        sta RESULT_FAILURE
        inc checks_bad
        lda checks_ok
        sta RESULT_CHECKS_OK
        lda checks_bad
        sta RESULT_CHECKS_BAD
        lda canary_bad
        sta RESULT_CANARY_BAD
        lda current
        sta RESULT_CURRENT
        lda switches_lo
        sta RESULT_SWITCHES
        lda switches_hi
        sta RESULT_SWITCHES_HI
        lda #$80
        ora fail_code
        sta RESULT_STATE
fail_halt:
        jmp fail_halt

; Both tasks share this body. Entry registers were restored by the core; the
; carry flag must arrive set, proving the saved processor status was restored.
task_entry:
        bcc task_carry_bad
        cli
        sta ZP_SEEN_A
        stx ZP_SEEN_X
        sty ZP_SEEN_Y
        inc ZP_STEP
        lda ZP_STEP
        ldx ZP_SENTINEL
        ldy #$33
        sec
        sei
        lda #<task_resume
        sta save_pc
        lda #>task_resume
        sta save_pc+1
        lda ZP_STEP
        jmp yield_core

task_resume:
        jmp task_entry

task_carry_bad:
        lda #$ff
        sta ZP_STATE
        lda #$00
        ldx #$00
        ldy #$00
        sec
        sei
        lda #<task_carry_resume
        sta save_pc
        lda #>task_carry_resume
        sta save_pc+1
        jmp yield_core

task_carry_resume:
        jmp task_carry_bad

irq_handler:
        inc irq_count
        lda CIA1_ICR
        rti

current:        .byte $00
round_index:    .byte $00
switches_lo:    .byte $00
switches_hi:    .byte $00
irq_count:      .byte $00
checks_ok:      .byte $00
checks_bad:     .byte $00
canary_bad:     .byte $00
fail_code:      .byte $00
a_step:         .byte $00
b_step:         .byte $00
a_primed:       .byte $00
b_primed:       .byte $00
save_a:         .byte $00
save_x:         .byte $00
save_y:         .byte $00
save_p:         .byte $00
save_sp:        .byte $00
disp_a:         .byte $00
disp_x:         .byte $00
disp_y:         .byte $00
save_pc:        .word $0000

gateway_end:
        .assert gateway_end - gateway_start <= $0700, error, "switch core exceeds common reservation"
        .assert gateway_start = $f800, error, "switch core moved"
