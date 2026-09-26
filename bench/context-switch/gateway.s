; SPDX-License-Identifier: GPL-3.0-or-later
;
; Runs from top common RAM while it alternates two synthetic 8502 tasks with
; relocated page-zero and page-one allocations and different MMU profiles.
;
; Each task owns a separate context record, a distinct seed/yield register
; pattern, stack pointer, stack marker, and two alternating resume addresses.
; Validation compares the observed state against formulas derived from the
; current step, not against the context record, so a stale or cross-wired
; record cannot pass. P is captured before any flag-changing instruction,
; restored after A/X/Y, and verified against a replay of the task tail.

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
RESULT_BOUNDARY_LO      = RESULT + 22
RESULT_BODY_LO          = RESULT + 23
RESULT_BOUNDARY_HI      = RESULT + 24
RESULT_BODY_HI          = RESULT + 25

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
VDC_ADDRESS             = $d600
VDC_DATA                = $d601
VIC_IRQ_STATUS          = $d019
VIC_IRQ_MASK            = $d01a

PROFILE_KERNEL_IO       = 1
PROFILE_WORKER_IO       = 3

A_SENTINEL              = $a5
B_SENTINEL              = $5a
A_YTAG                  = $a1
B_YTAG                  = $b2
A_ATAG                  = $40
B_ATAG                  = $80
A_MARK_HIGH             = $a5
B_MARK_HIGH             = $5a
A_PAD                   = $11
B_PAD                   = $22
A_CANARY                = $3c
B_CANARY                = $c3
BANK_A                  = $a0
BANK_B                  = $b0
A_SP_BASE               = $ff
B_SP_BASE               = $f5
A_SP_EVEN               = A_SP_BASE - 2
A_SP_ODD                = A_SP_BASE - 4
B_SP_EVEN               = B_SP_BASE - 2
B_SP_ODD                = B_SP_BASE - 4
SEED_P_A                = $29
SEED_P_B                = $21
DEC_A                   = $42
DEC_B                   = $3c
P_MASK                  = $cb
RESUME_A_EVEN           = $e0
RESUME_A_ODD            = $e1
RESUME_B_EVEN           = $e2
RESUME_B_ODD            = $e3
ROUNDS                  = 64
SWITCH_BUDGET_HI        = $04
TIMER_PERIOD            = $40

ZP_SENTINEL             = $02
ZP_STEP                 = $03
ZP_SEEN_P               = $04
ZP_RESUME_SEEN          = $05
ZP_DEC_RESULT           = $0b
ZP_SEEN_A               = $07
ZP_SEEN_X               = $08
ZP_SEEN_Y               = $09
ZP_STATE                = $0a
STACK_PAGE_BASE         = $0100
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
        lda #A_SENTINEL
        sta ZP_SENTINEL
        lda #$00
        sta ZP_STEP
        sta ZP_STATE
        sta ZP_SEEN_P
        sta ZP_RESUME_SEEN
        sta ZP_SEEN_A
        sta ZP_SEEN_X
        sta ZP_SEEN_Y
        lda #A_CANARY
        sta STACK_CANARY

        lda #$82
        sta MMU_PAGE0_PAGE
        lda #$83
        sta MMU_PAGE1_PAGE
        lda #B_SENTINEL
        sta ZP_SENTINEL
        lda #$00
        sta ZP_STEP
        sta ZP_STATE
        sta ZP_SEEN_P
        sta ZP_RESUME_SEEN
        sta ZP_SEEN_A
        sta ZP_SEEN_X
        sta ZP_SEEN_Y
        lda #B_CANARY
        sta STACK_CANARY

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

; Dispatch the current task: select its ownership and profile, restore its own
; record with P last so A/X/Y loads cannot overwrite the restored flags, and
; resume at the saved program counter.
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
        lda #A_ATAG
        sta a_ctx_a
        lda #A_SENTINEL
        sta a_ctx_x
        lda #A_YTAG
        sta a_ctx_y
        lda #SEED_P_A
        sta a_ctx_p
        sta a_last_p
        lda #A_SP_BASE
        sta a_ctx_sp
        lda #<task_a_first
        sta a_ctx_pc
        lda #>task_a_first
        sta a_ctx_pc+1
        lda #$01
        sta a_primed
dispatch_task_a_ready:
        lda #PROFILE_KERNEL_IO
        sta MMU_LCR_KERNEL_IO

        ldx a_ctx_sp
        txs
        lda #$01
        sta window_flag
        lda a_ctx_p
        pha
        lda a_ctx_a
        ldx a_ctx_x
        ldy a_ctx_y
        plp
        jmp (a_ctx_pc)

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
        lda #B_ATAG
        sta b_ctx_a
        lda #B_SENTINEL
        sta b_ctx_x
        lda #B_YTAG
        sta b_ctx_y
        lda #SEED_P_B
        sta b_ctx_p
        sta b_last_p
        lda #B_SP_BASE
        sta b_ctx_sp
        lda #<task_b_first
        sta b_ctx_pc
        lda #>task_b_first
        sta b_ctx_pc+1
        lda #$01
        sta b_primed
dispatch_task_b_ready:
        lda #PROFILE_WORKER_IO
        sta MMU_LCR_WORKER_IO

        ldx b_ctx_sp
        txs
        lda #$01
        sta window_flag
        lda b_ctx_p
        pha
        lda b_ctx_a
        ldx b_ctx_x
        ldy b_ctx_y
        plp
        jmp (b_ctx_pc)

; A task reaches here with jmp after pushing its stack marker and storing its
; resume address. PHP runs before SEI so the captured status is the task's.
yield_core:
        sta tmp_a
        stx tmp_x
        sty tmp_y
        php
        sei
        pla
        sta tmp_p
        cld
        lda #$00
        sta window_flag
        tsx
        stx tmp_sp

        lda current
        cmp #1
        beq :+
        jmp yield_validate_b
:
yield_validate_a:

        ; Restored A/X/Y observations against formulas, not the record.
        lda ZP_STEP
        sec
        sbc #$01
        clc
        adc #A_ATAG
        cmp ZP_SEEN_A
        beq :+
        lda #5
        jmp fail_common
:
        lda ZP_SEEN_X
        cmp #A_SENTINEL
        beq :+
        lda #5
        jmp fail_common
:
        lda ZP_SEEN_Y
        cmp #A_YTAG
        beq :+
        lda #5
        jmp fail_common
:
        lda ZP_STATE
        require_imm $00, 8

        ; Restored D must have driven decimal arithmetic for this task.
        lda ZP_DEC_RESULT
        require_imm DEC_A, 16

        ; Restored P must match the task's last verified yield status.
        lda ZP_SEEN_P
        and #P_MASK
        sta tmp_cmp
        lda a_last_p
        and #P_MASK
        cmp tmp_cmp
        beq :+
        lda #6
        jmp fail_common
:

        ; The resume marker must match the parity of the PC that was dispatched.
        lda ZP_STEP
        sec
        sbc #$01
        and #$01
        beq :+
        lda #RESUME_A_ODD
        jmp :++
:
        lda #RESUME_A_EVEN
:
        cmp ZP_RESUME_SEEN
        beq :+
        lda #14
        jmp fail_common
:

        ; Replay the task tail: the yield status must equal the replay.
        lda ZP_STEP
        clc
        adc #A_ATAG
        ldx #A_SENTINEL
        ldy #A_YTAG
        sec
        sed
        php
        pla
        cld
        and #P_MASK
        sta tmp_cmp
        lda tmp_p
        and #P_MASK
        cmp tmp_cmp
        beq :+
        lda #6
        jmp fail_common
:
        lda tmp_p
        sta a_last_p

        lda ZP_SENTINEL
        cmp #A_SENTINEL
        beq :+
        lda #2
        jmp fail_canary
:
        ; SP must equal the designated base minus the variable pad and marker.
        lda ZP_STEP
        and #$03
        asl a
        sta tmp_pad
        lda #(A_SP_BASE-2)
        sec
        sbc tmp_pad
        cmp tmp_sp
        beq :+
        lda #15
        jmp fail_canary
:
        ldx tmp_sp
        lda STACK_PAGE_BASE+1,x
        cmp #A_MARK_HIGH
        beq :+
        lda #11
        jmp fail_canary
:
        lda STACK_PAGE_BASE+2,x
        cmp ZP_STEP
        beq :+
        lda #11
        jmp fail_canary
:
        lda STACK_CANARY
        cmp #A_CANARY
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

        lda tmp_a
        sta a_ctx_a
        lda tmp_x
        sta a_ctx_x
        lda tmp_y
        sta a_ctx_y
        lda tmp_p
        sta a_ctx_p
        lda tmp_sp
        sta a_ctx_sp
        jmp yield_accept

yield_validate_b:

        lda ZP_STEP
        sec
        sbc #$01
        clc
        adc #B_ATAG
        cmp ZP_SEEN_A
        beq :+
        lda #5
        jmp fail_common
:
        lda ZP_SEEN_X
        cmp #B_SENTINEL
        beq :+
        lda #5
        jmp fail_common
:
        lda ZP_SEEN_Y
        cmp #B_YTAG
        beq :+
        lda #5
        jmp fail_common
:
        lda ZP_STATE
        require_imm $00, 8

        ; Restored D must have kept B binary even after A ran decimal.
        lda ZP_DEC_RESULT
        require_imm DEC_B, 16

        lda ZP_SEEN_P
        and #P_MASK
        sta tmp_cmp
        lda b_last_p
        and #P_MASK
        cmp tmp_cmp
        beq :+
        lda #6
        jmp fail_common
:

        lda ZP_STEP
        sec
        sbc #$01
        and #$01
        beq :+
        lda #RESUME_B_ODD
        jmp :++
:
        lda #RESUME_B_EVEN
:
        cmp ZP_RESUME_SEEN
        beq :+
        lda #14
        jmp fail_common
:

        lda ZP_STEP
        clc
        adc #B_ATAG
        ldx #B_SENTINEL
        ldy #B_YTAG
        sec
        cld
        php
        pla
        and #P_MASK
        sta tmp_cmp
        lda tmp_p
        and #P_MASK
        cmp tmp_cmp
        beq :+
        lda #6
        jmp fail_common
:
        lda tmp_p
        sta b_last_p

        lda ZP_SENTINEL
        cmp #B_SENTINEL
        beq :+
        lda #2
        jmp fail_canary
:
        lda ZP_STEP
        and #$03
        asl a
        sta tmp_pad
        lda #(B_SP_BASE-2)
        sec
        sbc tmp_pad
        cmp tmp_sp
        beq :+
        lda #15
        jmp fail_canary
:
        ldx tmp_sp
        lda STACK_PAGE_BASE+1,x
        cmp #B_MARK_HIGH
        beq :+
        lda #11
        jmp fail_canary
:
        lda STACK_PAGE_BASE+2,x
        cmp ZP_STEP
        beq :+
        lda #11
        jmp fail_canary
:
        lda STACK_CANARY
        cmp #B_CANARY
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

        lda tmp_a
        sta b_ctx_a
        lda tmp_x
        sta b_ctx_x
        lda tmp_y
        sta b_ctx_y
        lda tmp_p
        sta b_ctx_p
        lda tmp_sp
        sta b_ctx_sp

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
        lda boundary_lo
        sta RESULT_BOUNDARY_LO
        lda boundary_hi
        sta RESULT_BOUNDARY_HI
        lda body_lo
        sta RESULT_BODY_LO
        lda body_hi
        sta RESULT_BODY_HI
        lda boundary_lo
        clc
        adc body_lo
        sta RESULT_IRQ
        lda boundary_lo
        ora boundary_hi
        bne :+
        lda #12
        jmp fail_common
:
        lda body_lo
        ora body_hi
        bne :+
        lda #13
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
        jmp readout

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
        jmp readout

; Task A. The two resume labels are distinct code, so the resume marker proves
; which program counter actually ran.
task_a_first:
        sta ZP_SEEN_A
        stx ZP_SEEN_X
        sty ZP_SEEN_Y
        php
        pla
        sta ZP_SEEN_P
        ldx #RESUME_A_EVEN
        stx ZP_RESUME_SEEN
        lda #$00
        sta window_flag
        jmp task_a_body

task_a_resume0:
        sta ZP_SEEN_A
        stx ZP_SEEN_X
        sty ZP_SEEN_Y
        php
        pla
        sta ZP_SEEN_P
        ldx #RESUME_A_EVEN
        stx ZP_RESUME_SEEN
        jmp task_a_resume_check

task_a_resume1:
        sta ZP_SEEN_A
        stx ZP_SEEN_X
        sty ZP_SEEN_Y
        php
        pla
        sta ZP_SEEN_P
        ldx #RESUME_A_ODD
        stx ZP_RESUME_SEEN

task_a_resume_check:
        ; The previous marker and pad must have survived the other task.
        cld
        tsx
        lda STACK_PAGE_BASE+1,x
        cmp #A_MARK_HIGH
        beq :+
        lda #17
        jmp fail_canary
:
        lda STACK_PAGE_BASE+2,x
        cmp ZP_STEP
        beq :+
        lda #17
        jmp fail_canary
:
        ; Pop the previous pad and marker, restoring the base stack pointer.
        lda ZP_STEP
        and #$03
        asl a
        clc
        adc #$02
        sta tmp_pad
        txa
        clc
        adc tmp_pad
        tax
        txs
        sed
        lda #$00
        sta window_flag
        jmp task_a_body

task_a_body:

        inc ZP_STEP

        ; Uses the restored D flag: A must run decimal, B must run binary.
        lda #$15
        clc
        adc #$27
        sta ZP_DEC_RESULT
        cld

        ; Live stack use varies with the step: zero to three words of pad.
        lda ZP_STEP
        and #$03
        tax
        beq no_pad_a
pad_loop_a:
        lda #A_PAD
        pha
        pha
        dex
        bne pad_loop_a
no_pad_a:
        lda ZP_STEP
        pha
        lda #A_MARK_HIGH
        pha

        lda ZP_STEP
        and #$01
        bne :+
        lda #<task_a_resume0
        sta a_ctx_pc
        lda #>task_a_resume0
        sta a_ctx_pc+1
        jmp :++
:
        lda #<task_a_resume1
        sta a_ctx_pc
        lda #>task_a_resume1
        sta a_ctx_pc+1
:
        lda #$01
        sta window_flag
        lda ZP_STEP
        clc
        adc #A_ATAG
        ldx #A_SENTINEL
        ldy #A_YTAG
        sec
        sed
        jmp yield_core

; Task B. Same contract with distinct seed, tag, marker, pad, stack pointer,
; resume markers, and resume addresses.
task_b_first:
        sta ZP_SEEN_A
        stx ZP_SEEN_X
        sty ZP_SEEN_Y
        php
        pla
        sta ZP_SEEN_P
        ldx #RESUME_B_EVEN
        stx ZP_RESUME_SEEN
        lda #$00
        sta window_flag
        jmp task_b_body

task_b_resume0:
        sta ZP_SEEN_A
        stx ZP_SEEN_X
        sty ZP_SEEN_Y
        php
        pla
        sta ZP_SEEN_P
        ldx #RESUME_B_EVEN
        stx ZP_RESUME_SEEN
        jmp task_b_resume_check

task_b_resume1:
        sta ZP_SEEN_A
        stx ZP_SEEN_X
        sty ZP_SEEN_Y
        php
        pla
        sta ZP_SEEN_P
        ldx #RESUME_B_ODD
        stx ZP_RESUME_SEEN

task_b_resume_check:
        ; The previous marker and pad must have survived the other task.
        cld
        tsx
        lda STACK_PAGE_BASE+1,x
        cmp #B_MARK_HIGH
        beq :+
        lda #17
        jmp fail_canary
:
        lda STACK_PAGE_BASE+2,x
        cmp ZP_STEP
        beq :+
        lda #17
        jmp fail_canary
:
        ; Pop the previous pad and marker, restoring the base stack pointer.
        lda ZP_STEP
        and #$03
        asl a
        clc
        adc #$02
        sta tmp_pad
        txa
        clc
        adc tmp_pad
        tax
        txs
        cld
        lda #$00
        sta window_flag
        jmp task_b_body

task_b_body:

        inc ZP_STEP

        ; Uses the restored D flag: B must run binary even after A ran decimal.
        lda #$15
        clc
        adc #$27
        sta ZP_DEC_RESULT
        cld

        lda ZP_STEP
        and #$03
        tax
        beq no_pad_b
pad_loop_b:
        lda #B_PAD
        pha
        pha
        dex
        bne pad_loop_b
no_pad_b:
        lda ZP_STEP
        pha
        lda #B_MARK_HIGH
        pha

        lda ZP_STEP
        and #$01
        bne :+
        lda #<task_b_resume0
        sta b_ctx_pc
        lda #>task_b_resume0
        sta b_ctx_pc+1
        jmp :++
:
        lda #<task_b_resume1
        sta b_ctx_pc
        lda #>task_b_resume1
        sta b_ctx_pc+1
:
        lda #$01
        sta window_flag
        lda ZP_STEP
        clc
        adc #B_ATAG
        ldx #B_SENTINEL
        ldy #B_YTAG
        sec
        cld
        jmp yield_core

; Preserve the interrupted task's A, X, Y, and P completely. Interrupts taken
; while window_flag is set are counted as switch-boundary arrivals.
irq_handler:
        pha
        txa
        pha
        tya
        pha
        lda window_flag
        beq irq_body
        inc boundary_lo
        bne :+
        inc boundary_hi
:
        jmp irq_acknowledge
irq_body:
        inc body_lo
        bne :+
        inc body_hi
:
irq_acknowledge:
        lda CIA1_ICR
        pla
        tay
        pla
        tax
        pla
        rti

; Print the 32-byte result as hex on the 40-column VIC screen and the
; 80-column VDC screen, then halt. The VIC uses screen codes (A-F are $01-$06)
; while the VDC uses ASCII codes (A-F are $41-$46).
readout:
        sei
        lda #PROFILE_KERNEL_IO
        sta MMU_LCR_KERNEL_IO
        lda #$00
        sta MMU_PAGE0_BANK
        sta MMU_PAGE0_PAGE
        sta MMU_PAGE1_BANK
        lda #$01
        sta MMU_PAGE1_PAGE

        lda #$00
        sta readout_row
readout_row_loop:
        lda readout_row
        asl a
        asl a
        asl a
        sta readout_tmp
        asl a
        asl a
        clc
        adc readout_tmp
        sta readout_base

        lda #<$05e0
        clc
        adc readout_base
        sta readout_vic_store0+1
        sta readout_vic_store1+1
        lda #>$05e0
        adc #$00
        sta readout_vic_store0+2
        sta readout_vic_store1+2
        lda #<$d9e0
        clc
        adc readout_base
        sta readout_color_store0+1
        sta readout_color_store1+1
        lda #>$d9e0
        adc #$00
        sta readout_color_store0+2
        sta readout_color_store1+2

        lda readout_row
        asl a
        asl a
        asl a
        asl a
        sta readout_tmp
        asl a
        asl a
        clc
        adc readout_tmp
        clc
        adc #$c0
        sta readout_vdc_lo
        lda #$03
        adc #$00
        sta readout_vdc_hi

        lda #$12
        sta VDC_ADDRESS
        lda readout_vdc_hi
        sta VDC_DATA
        lda #$13
        sta VDC_ADDRESS
        lda readout_vdc_lo
        sta VDC_DATA
        lda #$1f
        sta VDC_ADDRESS

        ldx #$00
readout_byte_loop:
        ldy readout_byte
        lda RESULT,y
        sta readout_tmp
        lsr a
        lsr a
        lsr a
        lsr a
        tay
        lda readout_hex_vic,y
readout_vic_store0:
        sta $05e0,x
        lda #$01
readout_color_store0:
        sta $d9e0,x
        lda readout_tmp
        lsr a
        lsr a
        lsr a
        lsr a
        tay
        lda readout_hex_vdc,y
        sta VDC_DATA
        inx
        lda readout_tmp
        and #$0f
        tay
        lda readout_hex_vic,y
readout_vic_store1:
        sta $05e0,x
        lda #$01
readout_color_store1:
        sta $d9e0,x
        lda readout_tmp
        and #$0f
        tay
        lda readout_hex_vdc,y
        sta VDC_DATA
        inx
        inc readout_byte
        cpx #$10
        bne readout_byte_loop

        inc readout_row
        lda readout_row
        cmp #$04
        beq :+
        jmp readout_row_loop
:
readout_halt:
        jmp readout_halt

readout_hex_vic:
        .byte $30, $31, $32, $33, $34, $35, $36, $37
        .byte $38, $39, $01, $02, $03, $04, $05, $06
readout_hex_vdc:
        .byte $30, $31, $32, $33, $34, $35, $36, $37
        .byte $38, $39, $41, $42, $43, $44, $45, $46

current:        .byte $00
round_index:    .byte $00
switches_lo:    .byte $00
switches_hi:    .byte $00
boundary_lo:    .byte $00
boundary_hi:    .byte $00
body_lo:        .byte $00
body_hi:        .byte $00
checks_ok:      .byte $00
checks_bad:     .byte $00
canary_bad:     .byte $00
fail_code:      .byte $00
a_step:         .byte $00
b_step:         .byte $00
a_primed:       .byte $00
b_primed:       .byte $00
window_flag:    .byte $00
tmp_a:          .byte $00
tmp_x:          .byte $00
tmp_y:          .byte $00
tmp_p:          .byte $00
tmp_sp:         .byte $00
tmp_cmp:        .byte $00
tmp_pad:        .byte $00
a_last_p:       .byte $00
b_last_p:       .byte $00
readout_row:    .byte $00
readout_byte:   .byte $00
readout_base:   .byte $00
readout_tmp:    .byte $00
readout_vdc_lo: .byte $00
readout_vdc_hi: .byte $00

a_ctx_a:        .byte $00
a_ctx_x:        .byte $00
a_ctx_y:        .byte $00
a_ctx_p:        .byte $00
a_ctx_sp:       .byte $00
a_ctx_pc:       .word $0000

b_ctx_a:        .byte $00
b_ctx_x:        .byte $00
b_ctx_y:        .byte $00
b_ctx_p:        .byte $00
b_ctx_sp:       .byte $00
b_ctx_pc:       .word $0000

gateway_end:
        .assert gateway_end - gateway_start <= $0b00, error, "switch core exceeds common reservation"
        .assert gateway_start = $f400, error, "switch core moved"
