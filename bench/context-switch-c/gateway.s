; SPDX-License-Identifier: GPL-3.0-or-later
;
; Always-mapped context core for two real cc65 tasks. Each task owns relocated
; page zero/page one and a distinct C software stack. Yield resumes through
; the live hardware-stack return address left by the C call.

        .setcpu "6502"
        .segment "CODE"

RESULT                  = $f1a0
RESULT_STATE            = RESULT + 6
RESULT_FAILURE          = RESULT + 7
RESULT_SWITCH_LO        = RESULT + 8
RESULT_SWITCH_HI        = RESULT + 9
RESULT_STEP_A           = RESULT + 10
RESULT_STEP_B           = RESULT + 11
RESULT_SUM_A_LO         = RESULT + 12
RESULT_SUM_A_HI         = RESULT + 13
RESULT_SUM_B_LO         = RESULT + 14
RESULT_SUM_B_HI         = RESULT + 15
RESULT_STRATEGY         = RESULT + 16
RESULT_DONE             = RESULT + 17
RESULT_SP_A_LO          = RESULT + 18
RESULT_SP_A_HI          = RESULT + 19
RESULT_SP_B_LO          = RESULT + 20
RESULT_SP_B_HI          = RESULT + 21

MMU_PAGE0_PAGE          = $d507
MMU_PAGE0_BANK          = $d508
MMU_PAGE1_PAGE          = $d509
MMU_PAGE1_BANK          = $d50a

TASK_A_VECTOR           = $2800
TASK_B_VECTOR           = $2803
TASK_A_SOFT_TOP         = $70f0
TASK_B_SOFT_TOP         = $71f0
TASK_A_SOFT_CANARY      = $7000
TASK_B_SOFT_CANARY      = $7100
TASK_A_PAGE0            = $80
TASK_A_PAGE1            = $81
TASK_B_PAGE0            = $82
TASK_B_PAGE1            = $83
TASK_A_CANARY           = $a5
TASK_B_CANARY           = $5a

gateway_start:
        jmp initialize
yield_vector:
        jmp yield_core
done_vector:
        jmp done_core

initialize:
        sei
        cld
        lda #$00
        ldx #$00
clear_result:
        sta RESULT,x
        inx
        cpx #$20
        bne clear_result
        lda #'U'
        sta RESULT
        lda #'C'
        sta RESULT+1
        lda #'C'
        sta RESULT+2
        lda #'S'
        sta RESULT+3
        lda #$01
        sta RESULT+4
        sta RESULT+5
        sta RESULT_STATE
        lda #$02
        sta RESULT_STRATEGY
        lda #TASK_A_CANARY
        sta TASK_A_SOFT_CANARY
        lda #TASK_B_CANARY
        sta TASK_B_SOFT_CANARY

        lda #$01
        sta MMU_PAGE0_BANK
        sta MMU_PAGE1_BANK
        lda #TASK_A_PAGE0
        sta MMU_PAGE0_PAGE
        lda #TASK_A_PAGE1
        sta MMU_PAGE1_PAGE
        ldy #$00
        lda #$00
clear_a_pages:
        sta $0000,y
        sta $0100,y
        iny
        bne clear_a_pages
        lda #<TASK_A_SOFT_TOP
        sta $02
        lda #>TASK_A_SOFT_TOP
        sta $03
        lda #TASK_A_CANARY
        sta $0100

        lda #TASK_B_PAGE0
        sta MMU_PAGE0_PAGE
        lda #TASK_B_PAGE1
        sta MMU_PAGE1_PAGE
        ldy #$00
        lda #$00
clear_b_pages:
        sta $0000,y
        sta $0100,y
        iny
        bne clear_b_pages
        lda #<TASK_B_SOFT_TOP
        sta $02
        lda #>TASK_B_SOFT_TOP
        sta $03
        lda #TASK_B_CANARY
        sta $0100

        lda #$00
        sta done_bits
        sta switch_lo
        sta switch_hi
        lda #$01
        sta current

        lda #$00
        sta a_ctx_a
        sta a_ctx_x
        sta a_ctx_y
        lda #$24
        sta a_ctx_p
        lda #$ff
        sta a_ctx_sp
        lda #<TASK_A_VECTOR
        sta a_ctx_pc
        lda #>TASK_A_VECTOR
        sta a_ctx_pc+1

        lda #$00
        sta b_ctx_a
        sta b_ctx_x
        sta b_ctx_y
        lda #$24
        sta b_ctx_p
        lda #$ff
        sta b_ctx_sp
        lda #<TASK_B_VECTOR
        sta b_ctx_pc
        lda #>TASK_B_VECTOR
        sta b_ctx_pc+1
        jmp dispatch

yield_core:
        sta saved_a
        stx saved_x
        sty saved_y
        php
        sei
        pla
        sta saved_p
        cld
        tsx
        stx saved_sp

        lda current
        cmp #$01
        bne save_b
        lda $0100
        cmp #TASK_A_CANARY
        beq :+
        jmp fail_stack_a
:
        lda saved_a
        sta a_ctx_a
        lda saved_x
        sta a_ctx_x
        lda saved_y
        sta a_ctx_y
        lda saved_p
        sta a_ctx_p
        lda saved_sp
        sta a_ctx_sp
        lda #<resume_from_yield
        sta a_ctx_pc
        lda #>resume_from_yield
        sta a_ctx_pc+1
        jmp yield_saved
save_b:
        lda $0100
        cmp #TASK_B_CANARY
        beq :+
        jmp fail_stack_b
:
        lda saved_a
        sta b_ctx_a
        lda saved_x
        sta b_ctx_x
        lda saved_y
        sta b_ctx_y
        lda saved_p
        sta b_ctx_p
        lda saved_sp
        sta b_ctx_sp
        lda #<resume_from_yield
        sta b_ctx_pc
        lda #>resume_from_yield
        sta b_ctx_pc+1

yield_saved:
        inc switch_lo
        bne :+
        inc switch_hi
:
        lda current
        cmp #$01
        bne select_a
        lda done_bits
        and #$02
        bne select_a
        lda #$02
        bne selected
select_a:
        lda #$01
selected:
        sta current
        jmp dispatch

resume_from_yield:
        rts

done_core:
        sei
        cmp #$01
        bne done_b
        lda done_bits
        ora #$01
        sta done_bits
        lda #$02
        sta current
        bne done_selected
done_b:
        lda done_bits
        ora #$02
        sta done_bits
        lda #$01
        sta current
done_selected:
        lda done_bits
        cmp #$03
        beq finish
        jmp dispatch

dispatch:
        lda #$01
        sta MMU_PAGE0_BANK
        sta MMU_PAGE1_BANK
        lda current
        cmp #$01
        bne dispatch_b
        lda #TASK_A_PAGE0
        sta MMU_PAGE0_PAGE
        lda #TASK_A_PAGE1
        sta MMU_PAGE1_PAGE
        ldx a_ctx_sp
        txs
        lda a_ctx_p
        pha
        lda a_ctx_a
        ldx a_ctx_x
        ldy a_ctx_y
        plp
        jmp (a_ctx_pc)
dispatch_b:
        lda #TASK_B_PAGE0
        sta MMU_PAGE0_PAGE
        lda #TASK_B_PAGE1
        sta MMU_PAGE1_PAGE
        ldx b_ctx_sp
        txs
        lda b_ctx_p
        pha
        lda b_ctx_a
        ldx b_ctx_x
        ldy b_ctx_y
        plp
        jmp (b_ctx_pc)

finish:
        lda switch_lo
        sta RESULT_SWITCH_LO
        lda switch_hi
        sta RESULT_SWITCH_HI
        lda done_bits
        sta RESULT_DONE
        lda RESULT_FAILURE
        beq :+
        jmp finish_failed
:
        lda RESULT_STEP_A
        cmp #$20
        beq :+
        jmp fail_progress_a
:
        lda RESULT_STEP_B
        cmp #$20
        beq :+
        jmp fail_progress_b
:
        lda RESULT_SUM_A_LO
        cmp #<$1444
        beq :+
        jmp fail_sum_a
:
        lda RESULT_SUM_A_HI
        cmp #>$1444
        bne fail_sum_a
        lda RESULT_SUM_B_LO
        cmp #<$4741
        bne fail_sum_b
        lda RESULT_SUM_B_HI
        cmp #>$4741
        bne fail_sum_b
        lda TASK_A_SOFT_CANARY
        cmp #TASK_A_CANARY
        bne fail_soft_a
        lda TASK_B_SOFT_CANARY
        cmp #TASK_B_CANARY
        bne fail_soft_b

        lda #TASK_A_PAGE0
        sta MMU_PAGE0_PAGE
        lda #TASK_A_PAGE1
        sta MMU_PAGE1_PAGE
        lda $02
        sta RESULT_SP_A_LO
        cmp #<TASK_A_SOFT_TOP
        bne fail_sp_a
        lda $03
        sta RESULT_SP_A_HI
        cmp #>TASK_A_SOFT_TOP
        bne fail_sp_a
        lda $0100
        cmp #TASK_A_CANARY
        bne fail_stack_a

        lda #TASK_B_PAGE0
        sta MMU_PAGE0_PAGE
        lda #TASK_B_PAGE1
        sta MMU_PAGE1_PAGE
        lda $02
        sta RESULT_SP_B_LO
        cmp #<TASK_B_SOFT_TOP
        bne fail_sp_b
        lda $03
        sta RESULT_SP_B_HI
        cmp #>TASK_B_SOFT_TOP
        bne fail_sp_b
        lda $0100
        cmp #TASK_B_CANARY
        bne fail_stack_b
        lda #$02
        sta RESULT_STATE
halt:
        jmp halt

fail_stack_a:
        lda #$03
        bne fail
fail_stack_b:
        lda #$04
        bne fail
fail_progress_a:
        lda #$05
        bne fail
fail_progress_b:
        lda #$06
        bne fail
fail_sum_a:
        lda #$07
        bne fail
fail_sum_b:
        lda #$08
        bne fail
fail_soft_a:
        lda #$09
        bne fail
fail_soft_b:
        lda #$0a
        bne fail
fail_sp_a:
        lda #$0b
        bne fail
fail_sp_b:
        lda #$0c
fail:
        sta RESULT_FAILURE
finish_failed:
        lda #$82
        sta RESULT_STATE
        jmp halt

current:        .byte $00
done_bits:      .byte $00
switch_lo:      .byte $00
switch_hi:      .byte $00
saved_a:        .byte $00
saved_x:        .byte $00
saved_y:        .byte $00
saved_p:        .byte $00
saved_sp:       .byte $00
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
        .assert yield_vector = $f403, error, "compiled yield vector moved"
        .assert done_vector = $f406, error, "compiled done vector moved"
        .assert gateway_end - gateway_start <= $0300, error, "compiled switch core exceeds budget"
