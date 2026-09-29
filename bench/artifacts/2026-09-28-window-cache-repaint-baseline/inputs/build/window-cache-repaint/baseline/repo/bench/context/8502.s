; SPDX-License-Identifier: GPL-3.0-or-later
;
; Task-context save/restore benchmark for the 8502 and cc65 runtime.

        .setcpu "6502"
        .segment "CODE"

RESULT              = $f180
RESULT_STATE        = RESULT + 6
RESULT_VARIANTS     = RESULT + 7
RESULT_SAMPLES      = RESULT + 8
RESULT_ITERATIONS   = RESULT + 10
RESULT_CORE_BYTES   = RESULT + 12
RESULT_COMP_BYTES   = RESULT + 13
RESULT_FULL_BYTES   = RESULT + 14
RESULT_BAD          = RESULT + 15

EMPTY_BASE          = RESULT + 32
CORE_BASE           = EMPTY_BASE + 16
COMPILER_BASE       = CORE_BASE + 16
FULL_BASE           = COMPILER_BASE + 16

RUNTIME_ZP          = $02
RUNTIME_ZP_BYTES    = 26
CONTEXT_ZP          = $f140
CONTEXT_SP          = $f15a
ITER_COUNT          = $f15b
CUR_SAMPLE          = $f15c
TICK_LOW            = $f15d
TICK_HIGH           = $f15e

CIA1_TB_LO          = $dc06
CIA1_TB_HI          = $dc07
CIA1_ICR            = $dc0d
CIA1_CRB            = $dc0f

VARIANT_COUNT       = 4
SAMPLES_PER_VARIANT = 8
ITERATIONS          = 64
CORE_BYTES          = 7     ; return PC, P/A/X/Y frame, saved SP
COMPILER_BYTES      = 33    ; core plus 26-byte cc65 zero-page runtime
FULL_BYTES          = 33    ; no additional 8502 register bank

start:
        sei
        cld
        ldx #$ff
        txs
        lda #$3e
        sta $ff00

        lda #$00
        ldx #$00
clear_result:
        sta RESULT,x
        inx
        cpx #$80
        bne clear_result

        lda #'C'
        sta RESULT+0
        lda #'T'
        sta RESULT+1
        lda #'X'
        sta RESULT+2
        lda #'B'
        sta RESULT+3
        lda #$01
        sta RESULT+4
        sta RESULT+5             ; CPU: 8502
        sta RESULT_STATE
        lda #VARIANT_COUNT
        sta RESULT_VARIANTS
        lda #SAMPLES_PER_VARIANT
        sta RESULT_SAMPLES
        lda #<ITERATIONS
        sta RESULT_ITERATIONS
        lda #>ITERATIONS
        sta RESULT_ITERATIONS+1
        lda #CORE_BYTES
        sta RESULT_CORE_BYTES
        lda #COMPILER_BYTES
        sta RESULT_COMP_BYTES
        lda #FULL_BYTES
        sta RESULT_FULL_BYTES

        ; Seed every byte that cc65 declares as task-local runtime state.
        lda #$a5
        ldx #RUNTIME_ZP_BYTES-1
seed_zp:
        sta RUNTIME_ZP,x
        dex
        bpl seed_zp

        jsr qualify_core
        jsr qualify_compiler
        lda RESULT_BAD
        bne failed

        lda #<empty_context
        sta benchmark_call+1
        lda #>empty_context
        sta benchmark_call+2
        lda #<EMPTY_BASE
        sta store_tick+1
        sta store_tick_high+1
        lda #>EMPTY_BASE
        sta store_tick+2
        sta store_tick_high+2
        jsr run_variant

        lda #<context_core
        sta benchmark_call+1
        lda #>context_core
        sta benchmark_call+2
        lda #<CORE_BASE
        sta store_tick+1
        sta store_tick_high+1
        lda #>CORE_BASE
        sta store_tick+2
        sta store_tick_high+2
        jsr run_variant

        lda #<context_compiler
        sta benchmark_call+1
        lda #>context_compiler
        sta benchmark_call+2
        lda #<COMPILER_BASE
        sta store_tick+1
        sta store_tick_high+1
        lda #>COMPILER_BASE
        sta store_tick+2
        sta store_tick_high+2
        jsr run_variant

        ; Full architectural state is identical to compiler-complete state on
        ; the 8502, so this intentionally selects the same primitive.
        lda #<context_full
        sta benchmark_call+1
        lda #>context_full
        sta benchmark_call+2
        lda #<FULL_BASE
        sta store_tick+1
        sta store_tick_high+1
        lda #>FULL_BASE
        sta store_tick+2
        sta store_tick_high+2
        jsr run_variant

        lda #$02
        sta RESULT_STATE
halt:
        jmp halt

failed:
        lda #$ff
        sta RESULT_STATE
        jmp halt

run_variant:
        lda #$00
        sta CUR_SAMPLE
next_sample:
        jsr timer_start
        lda #ITERATIONS
        sta ITER_COUNT
timed_loop:
benchmark_call:
        jsr empty_context
        dec ITER_COUNT
        bne timed_loop
        jsr timer_elapsed
        sta TICK_LOW
        stx TICK_HIGH
        lda TICK_LOW
        cmp #$ff
        bne tick_valid
        lda TICK_HIGH
        cmp #$ff
        bne tick_valid
        inc RESULT_BAD
tick_valid:
        lda CUR_SAMPLE
        asl
        tax
        lda TICK_LOW
store_tick:
        sta EMPTY_BASE,x
        inx
        lda TICK_HIGH
store_tick_high:
        sta EMPTY_BASE,x
        inc CUR_SAMPLE
        lda CUR_SAMPLE
        cmp #SAMPLES_PER_VARIANT
        bcc next_sample
        rts

empty_context:
        rts

; Core 8502 state: call-stacked PC, P, A, X, Y, and hardware SP.
context_core:
        php
        pha
        txa
        pha
        tya
        pha
        tsx
        stx CONTEXT_SP
        ldx CONTEXT_SP
        txs
        pla
        tay
        pla
        tax
        pla
        plp
        rts

; Arbitrary preemption must additionally preserve cc65's entire 26-byte
; zero-page runtime block, including its six-byte register bank.
context_compiler:
context_full:
        php
        pha
        txa
        pha
        tya
        pha
        tsx
        stx CONTEXT_SP
        ; This is intentionally unrolled: context transfer is a kernel hot
        ; path, and the compact indexed loop more than doubles its cost.
        .repeat RUNTIME_ZP_BYTES, I
        lda RUNTIME_ZP+I
        sta CONTEXT_ZP+I
        .endrepeat
        .repeat RUNTIME_ZP_BYTES, I
        lda CONTEXT_ZP+I
        sta RUNTIME_ZP+I
        .endrepeat
        ldx CONTEXT_SP
        txs
        pla
        tay
        pla
        tax
        pla
        plp
        rts

qualify_core:
        lda #$a5
        ldx #$3c
        ldy #$c3
        sec
        jsr context_core
        bcc qualification_failed
        cmp #$a5
        bne qualification_failed
        cpx #$3c
        bne qualification_failed
        cpy #$c3
        bne qualification_failed
        rts

qualify_compiler:
        lda #$5a
        ldx #$c3
        ldy #$3c
        sec
        jsr context_compiler
        bcc qualification_failed
        cmp #$5a
        bne qualification_failed
        cpx #$c3
        bne qualification_failed
        cpy #$3c
        bne qualification_failed
        lda #$a5
        ldx #RUNTIME_ZP_BYTES-1
check_zp:
        cmp RUNTIME_ZP,x
        bne qualification_failed
        dex
        bpl check_zp
        rts

qualification_failed:
        inc RESULT_BAD
        rts

timer_start:
        lda CIA1_ICR
        lda #$00
        sta CIA1_CRB
        lda #$ff
        sta CIA1_TB_LO
        sta CIA1_TB_HI
        lda #$11
        sta CIA1_CRB
        rts

timer_elapsed:
        lda #$00
        sta CIA1_CRB
        lda CIA1_TB_LO
        eor #$ff
        pha
        lda CIA1_TB_HI
        eor #$ff
        tax
        lda CIA1_ICR
        and #$02
        bne timer_overflow
        pla
        rts
timer_overflow:
        pla
        lda #$ff
        tax
        rts
