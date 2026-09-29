; SPDX-License-Identifier: GPL-3.0-or-later
;
; Instrumented CIA1 Timer-A interrupt-service benchmark for the 8502.

        .setcpu "6502"
        .segment "CODE"

RESULT              = $f180
RESULT_STATE        = RESULT + 7
RESULT_VARIANTS     = RESULT + 8
RESULT_SAMPLES      = RESULT + 9
RESULT_TARGET       = RESULT + 10
RESULT_OBSERVED     = RESULT + 12
RESULT_BAD          = RESULT + 14
RESULT_FIRST        = RESULT + 16
RESULT_LAST         = RESULT + 17
RESULT_PERIOD       = RESULT + 18
RESULT_TICK         = RESULT + 24
RESULT_EVENT        = RESULT + 28
RESULT_DISPATCH     = RESULT + 29
RESULT_VECTOR       = RESULT + 30

ENTRY_BASE          = RESULT + 32
PREEXIT_BASE        = ENTRY_BASE + 96
RESUME_BASE         = PREEXIT_BASE + 96

CUR_VARIANT         = $f178
CUR_SAMPLE          = $f179
TIMER_LOW           = $f17a
TIMER_HIGH          = $f17b
SAMPLE_OFFSET       = $f17c

VIC_IRQ_STATUS      = $d019
VIC_IRQ_MASK        = $d01a
CIA1_TA_LO          = $dc04
CIA1_TA_HI          = $dc05
CIA1_ICR            = $dc0d
CIA1_CRA            = $dc0e
CIA2_ICR            = $dd0d

VARIANT_COUNT       = 3
SAMPLES_PER_VARIANT = 16
TARGET_COUNT        = VARIANT_COUNT * SAMPLES_PER_VARIANT
TIMER_PERIOD        = 4000

start:
        sei
        cld
        ldx #$ff
        txs

        lda #$3e
        sta $ff00
        lda #<irq_handler
        sta $fffe
        lda #>irq_handler
        sta $ffff

        ; Clear the 320-byte result block.
        lda #$00
        ldx #$00
clear_page:
        sta RESULT,x
        inx
        bne clear_page
        ldx #$00
clear_tail:
        sta RESULT+$100,x
        inx
        cpx #$40
        bne clear_tail

        lda #'I'
        sta RESULT+0
        lda #'R'
        sta RESULT+1
        lda #'Q'
        sta RESULT+2
        lda #'S'
        sta RESULT+3
        lda #$01
        sta RESULT+4
        sta RESULT+5             ; CPU: 8502
        sta RESULT+6             ; mode: native IRQ vector
        sta RESULT_STATE         ; running
        lda #VARIANT_COUNT
        sta RESULT_VARIANTS
        lda #SAMPLES_PER_VARIANT
        sta RESULT_SAMPLES
        lda #<TARGET_COUNT
        sta RESULT_TARGET
        lda #>TARGET_COUNT
        sta RESULT_TARGET+1
        lda #<TIMER_PERIOD
        sta RESULT_PERIOD
        lda #>TIMER_PERIOD
        sta RESULT_PERIOD+1
        lda #<dispatch_target
        sta RESULT_VECTOR
        lda #>dispatch_target
        sta RESULT_VECTOR+1

        lda #$00
        sta CUR_VARIANT
        sta CUR_SAMPLE
        sta VIC_IRQ_MASK
        lda #$0f
        sta VIC_IRQ_STATUS
        lda #$7f
        sta CIA1_ICR
        sta CIA2_ICR
        lda CIA1_ICR
        lda CIA2_ICR
        lda #$81
        sta CIA1_ICR

prepare_sample:
        sei
        lda #$00
        sta CIA1_CRA
        lda CIA1_ICR
        lda #<wait_irq
        sta wait_irq+1
        lda #>wait_irq
        sta wait_irq+2
        lda #<TIMER_PERIOD
        sta CIA1_TA_LO
        lda #>TIMER_PERIOD
        sta CIA1_TA_HI
        lda #$11
        sta CIA1_CRA
        cli

wait_irq:
        jmp wait_irq

resume_irq:
        ; First timestamp after RTI and the patched wait jump.
        jsr read_timer_a
        sei
        lda #$00
        sta CIA1_CRA

        jsr sample_offset
        sec
        lda #<TIMER_PERIOD
        sbc TIMER_LOW
        sta RESUME_BASE,x
        inx
        lda #>TIMER_PERIOD
        sbc TIMER_HIGH
        sta RESUME_BASE,x

        inc CUR_SAMPLE
        lda CUR_SAMPLE
        cmp #SAMPLES_PER_VARIANT
        bcc prepare_sample
        lda #$00
        sta CUR_SAMPLE
        inc CUR_VARIANT
        lda CUR_VARIANT
        cmp #VARIANT_COUNT
        bcc prepare_sample

        lda #$7f
        sta CIA1_ICR
        lda CIA1_ICR
        lda #$02
        sta RESULT_STATE
halt:
        jmp halt

irq_handler:
        pha
        txa
        pha
        tya
        pha

        ; Entry timestamp after the admitted ISR register set is safe.
        jsr read_timer_a
        lda CIA1_ICR
        sta RESULT_LAST
        ldx RESULT_OBSERVED
        bne not_first
        ldx RESULT_OBSERVED+1
        bne not_first
        sta RESULT_FIRST
not_first:
        and #$81
        cmp #$81
        beq source_ok
        inc RESULT_BAD
        bne source_ok
        inc RESULT_BAD+1
source_ok:
        jsr sample_offset
        sec
        lda #<TIMER_PERIOD
        sbc TIMER_LOW
        sta ENTRY_BASE,x
        inx
        lda #>TIMER_PERIOD
        sbc TIMER_HIGH
        sta ENTRY_BASE,x

        lda CUR_VARIANT
        beq variant_done
        cmp #$01
        bne dispatch_variant

        ; Kernel-tick variant: 32-bit monotonic increment plus event signal.
        inc RESULT_TICK
        bne tick_event
        inc RESULT_TICK+1
        bne tick_event
        inc RESULT_TICK+2
        bne tick_event
        inc RESULT_TICK+3
tick_event:
        lda #$01
        sta RESULT_EVENT
        bne variant_done

dispatch_variant:
        jsr dispatch_thunk

variant_done:
        ; Timestamp after acknowledgement, bookkeeping, and variant work.
        jsr read_timer_a
        jsr sample_offset
        sec
        lda #<TIMER_PERIOD
        sbc TIMER_LOW
        sta PREEXIT_BASE,x
        inx
        lda #>TIMER_PERIOD
        sbc TIMER_HIGH
        sta PREEXIT_BASE,x

        inc RESULT_OBSERVED
        bne count_done
        inc RESULT_OBSERVED+1
count_done:
        lda #<resume_irq
        sta wait_irq+1
        lda #>resume_irq
        sta wait_irq+2

        pla
        tay
        pla
        tax
        pla
        rti

read_timer_a:
read_timer_retry:
        lda CIA1_TA_HI
        tax
        lda CIA1_TA_LO
        sta TIMER_LOW
        cpx CIA1_TA_HI
        bne read_timer_retry
        stx TIMER_HIGH
        rts

; Return X = ((variant * 16) + sample) * 2.
sample_offset:
        lda CUR_VARIANT
        asl
        asl
        asl
        asl
        asl
        sta SAMPLE_OFFSET
        lda CUR_SAMPLE
        asl
        clc
        adc SAMPLE_OFFSET
        tax
        rts

dispatch_thunk:
        jmp (RESULT_VECTOR)

dispatch_target:
        inc RESULT_DISPATCH
        rts
