; SPDX-License-Identifier: GPL-3.0-or-later
;
; Runs from top common RAM while it alternates two synthetic 8502 tasks with
; relocated page-zero and page-one allocations and different MMU profiles.
;
; Each task owns a separate context record and a distinct register pattern,
; stack pointer, stack marker, and resume address. The interrupt handler saves
; and restores A, X, and Y and classifies interrupts that arrive inside the
; marked switch-boundary window.

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
RESULT_BOUNDARY_IRQ     = RESULT + 22
RESULT_BODY_IRQ         = RESULT + 23

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

A_SENTINEL              = $a5
B_SENTINEL              = $5a
A_YTAG                  = $a1
B_YTAG                  = $b2
A_ATAG                  = $40
B_ATAG                  = $80
A_SEED_A                = $41
A_SEED_X                = A_SENTINEL
A_SEED_Y                = A_YTAG
B_SEED_A                = $82
B_SEED_X                = B_SENTINEL
B_SEED_Y                = B_YTAG
A_MARK_LOW              = $5a
A_MARK_HIGH             = $a5
B_MARK_LOW              = $a5
B_MARK_HIGH             = $5a
A_CANARY                = $3c
B_CANARY                = $c3
BANK_A                  = $a0
BANK_B                  = $b0
A_STACK_INIT            = $ff
B_STACK_INIT            = $f5
ROUNDS                  = 64
SWITCH_BUDGET_HI        = $04
TIMER_PERIOD            = $40

ZP_SENTINEL             = $02
ZP_STEP                 = $03
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
        lda #A_SENTINEL
        sta ZP_SENTINEL
        lda #$00
        sta ZP_STEP
        sta ZP_STATE
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

; Dispatch the current task: select its ownership and profile, copy its own
; record into the restore registers, and resume at its saved program counter.
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
        lda #A_SEED_A
        sta a_ctx_a
        lda #A_SEED_X
        sta a_ctx_x
        lda #A_SEED_Y
        sta a_ctx_y
        lda #$05
        sta a_ctx_p
        lda #A_STACK_INIT
        sta a_ctx_sp
        lda #<task_a_entry
        sta a_ctx_pc
        lda #>task_a_entry
        sta a_ctx_pc+1
        lda #$01
        sta a_primed
dispatch_task_a_ready:
        lda a_ctx_a
        sta a_disp_a
        lda a_ctx_x
        sta a_disp_x
        lda a_ctx_y
        sta a_disp_y

        lda #PROFILE_KERNEL_IO
        sta MMU_LCR_KERNEL_IO

        ldx a_ctx_sp
        txs
        lda a_ctx_p
        pha
        plp
        lda #$01
        sta window_flag
        lda a_ctx_a
        ldx a_ctx_x
        ldy a_ctx_y
        cli
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
        lda #B_SEED_A
        sta b_ctx_a
        lda #B_SEED_X
        sta b_ctx_x
        lda #B_SEED_Y
        sta b_ctx_y
        lda #$05
        sta b_ctx_p
        lda #B_STACK_INIT
        sta b_ctx_sp
        lda #<task_b_entry
        sta b_ctx_pc
        lda #>task_b_entry
        sta b_ctx_pc+1
        lda #$01
        sta b_primed
dispatch_task_b_ready:
        lda b_ctx_a
        sta b_disp_a
        lda b_ctx_x
        sta b_disp_x
        lda b_ctx_y
        sta b_disp_y

        lda #PROFILE_WORKER_IO
        sta MMU_LCR_WORKER_IO

        ldx b_ctx_sp
        txs
        lda b_ctx_p
        pha
        plp
        lda #$01
        sta window_flag
        lda b_ctx_a
        ldx b_ctx_x
        ldy b_ctx_y
        cli
        jmp (b_ctx_pc)

; A task reaches here with jmp after pushing its stack marker and storing its
; resume address. Interrupts enabled up to the jmp make the boundary window
; observable to the handler.
yield_core:
        sei
        sta tmp_a
        lda #$00
        sta window_flag
        stx tmp_x
        sty tmp_y
        php
        pla
        sta tmp_p
        tsx
        stx tmp_sp

        lda current
        cmp #1
        beq :+
        jmp yield_validate_b
:
yield_validate_a:
        lda ZP_SEEN_A
        require_mem a_disp_a, 5
        lda ZP_SEEN_X
        require_mem a_disp_x, 5
        lda ZP_SEEN_Y
        require_mem a_disp_y, 5
        lda ZP_STATE
        require_imm $00, 8
        lda tmp_y
        require_imm A_YTAG, 5
        lda tmp_x
        require_imm A_SENTINEL, 5
        lda ZP_STEP
        clc
        adc #A_ATAG
        cmp tmp_a
        beq :+
        lda #5
        jmp fail_common
:
        lda tmp_p
        and #$01
        bne :+
        lda #6
        jmp fail_common
:
        lda ZP_SENTINEL
        cmp #A_SENTINEL
        beq :+
        lda #2
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
        cmp #A_MARK_LOW
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
        clc
        adc #$02
        sta a_ctx_sp
        jmp yield_accept

yield_validate_b:
        lda ZP_SEEN_A
        require_mem b_disp_a, 5
        lda ZP_SEEN_X
        require_mem b_disp_x, 5
        lda ZP_SEEN_Y
        require_mem b_disp_y, 5
        lda ZP_STATE
        require_imm $00, 8
        lda tmp_y
        require_imm B_YTAG, 5
        lda tmp_x
        require_imm B_SENTINEL, 5
        lda ZP_STEP
        clc
        adc #B_ATAG
        cmp tmp_a
        beq :+
        lda #5
        jmp fail_common
:
        lda tmp_p
        and #$01
        bne :+
        lda #6
        jmp fail_common
:
        lda ZP_SENTINEL
        cmp #B_SENTINEL
        beq :+
        lda #2
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
        cmp #B_MARK_LOW
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
        clc
        adc #$02
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
        lda boundary_irqs
        sta RESULT_BOUNDARY_IRQ
        lda body_irqs
        sta RESULT_BODY_IRQ
        lda boundary_irqs
        clc
        adc body_irqs
        sta RESULT_IRQ
        bne :+
        lda #9
        jmp fail_common
:
        lda boundary_irqs
        bne :+
        lda #12
        jmp fail_common
:
        lda body_irqs
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

; Task A. Entry registers came from record A; the stack marker is pushed into
; the actively used part of A's relocated page one.
task_a_entry:
        dec window_flag
        sta ZP_SEEN_A
        stx ZP_SEEN_X
        sty ZP_SEEN_Y
        inc ZP_STEP

        lda #A_MARK_LOW
        pha
        lda #A_MARK_HIGH
        pha

        lda #<task_a_resume
        sta a_ctx_pc
        lda #>task_a_resume
        sta a_ctx_pc+1

        lda #$01
        sta window_flag

        lda ZP_STEP
        clc
        adc #A_ATAG
        ldx #A_SENTINEL
        ldy #A_YTAG
        sec
        jmp yield_core

task_a_resume:
        jmp task_a_entry

; Task B. Same contract with distinct seed, tag, marker, stack pointer, and
; resume address.
task_b_entry:
        dec window_flag
        sta ZP_SEEN_A
        stx ZP_SEEN_X
        sty ZP_SEEN_Y
        inc ZP_STEP

        lda #B_MARK_LOW
        pha
        lda #B_MARK_HIGH
        pha

        lda #<task_b_resume
        sta b_ctx_pc
        lda #>task_b_resume
        sta b_ctx_pc+1

        lda #$01
        sta window_flag

        lda ZP_STEP
        clc
        adc #B_ATAG
        ldx #B_SENTINEL
        ldy #B_YTAG
        sec
        jmp yield_core

task_b_resume:
        jmp task_b_entry

; Preserve the interrupted task's A, X, and Y completely. Interrupts taken
; while window_flag is set are counted as switch-boundary arrivals.
irq_handler:
        pha
        txa
        pha
        tya
        pha
        lda window_flag
        beq irq_body
        inc boundary_irqs
        jmp irq_acknowledge
irq_body:
        inc body_irqs
irq_acknowledge:
        lda CIA1_ICR
        pla
        tay
        pla
        tax
        pla
        rti

current:        .byte $00
round_index:    .byte $00
switches_lo:    .byte $00
switches_hi:    .byte $00
boundary_irqs:  .byte $00
body_irqs:      .byte $00
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

a_ctx_a:        .byte $00
a_ctx_x:        .byte $00
a_ctx_y:        .byte $00
a_ctx_p:        .byte $00
a_ctx_sp:       .byte $00
a_ctx_pc:       .word $0000
a_disp_a:       .byte $00
a_disp_x:       .byte $00
a_disp_y:       .byte $00

b_ctx_a:        .byte $00
b_ctx_x:        .byte $00
b_ctx_y:        .byte $00
b_ctx_p:        .byte $00
b_ctx_sp:       .byte $00
b_ctx_pc:       .word $0000
b_disp_a:       .byte $00
b_disp_x:       .byte $00
b_disp_y:       .byte $00

gateway_end:
        .assert gateway_end - gateway_start <= $0700, error, "switch core exceeds common reservation"
        .assert gateway_start = $f800, error, "switch core moved"
