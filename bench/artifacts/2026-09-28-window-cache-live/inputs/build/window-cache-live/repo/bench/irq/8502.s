; SPDX-License-Identifier: GPL-3.0-or-later
;
; CIA1 Timer-A repeated-interrupt qualification for the 8502.

        .setcpu "6502"
        .segment "CODE"

RESULT          = $f180
RESULT_STATE    = RESULT + 7
RESULT_TARGET   = RESULT + 8
RESULT_COUNT    = RESULT + 10
RESULT_BAD      = RESULT + 12
RESULT_FIRST    = RESULT + 14
RESULT_LAST     = RESULT + 15
RESULT_PERIOD   = RESULT + 16
RESULT_SAMPLES  = RESULT + 18
SAMPLE_BASE     = RESULT + 32
TIMER_LOW       = $f17e
TIMER_HIGH      = $f17f

VIC_IRQ_STATUS  = $d019
VIC_IRQ_MASK    = $d01a
CIA1_TA_LO      = $dc04
CIA1_TA_HI      = $dc05
CIA1_ICR        = $dc0d
CIA1_CRA        = $dc0e
CIA2_ICR        = $dd0d

TARGET_COUNT    = 32
TIMER_PERIOD    = 1000

start:
        sei
        cld
        ldx #$ff
        txs

        ; Bank-zero RAM with the I/O window visible.
        lda #$3e
        sta $ff00

        lda #<irq_handler
        sta $fffe
        lda #>irq_handler
        sta $ffff

        lda #'I'
        sta RESULT+0
        lda #'R'
        sta RESULT+1
        lda #'Q'
        sta RESULT+2
        lda #'P'
        sta RESULT+3
        lda #$01
        sta RESULT+4
        sta RESULT+5             ; CPU: 8502
        sta RESULT+6             ; mode: native IRQ vector
        sta RESULT_STATE         ; running
        lda #TARGET_COUNT
        sta RESULT_TARGET
        lda #$00
        sta RESULT_TARGET+1
        sta RESULT_COUNT
        sta RESULT_COUNT+1
        sta RESULT_BAD
        sta RESULT_BAD+1
        sta RESULT_FIRST
        sta RESULT_LAST
        lda #<TIMER_PERIOD
        sta RESULT_PERIOD
        lda #>TIMER_PERIOD
        sta RESULT_PERIOD+1
        lda #TARGET_COUNT
        sta RESULT_SAMPLES
        lda #$00
        sta RESULT_SAMPLES+1

        ; Remove pre-existing maskable and non-maskable device requests.
        sta VIC_IRQ_MASK
        lda #$0f
        sta VIC_IRQ_STATUS
        lda #$7f
        sta CIA1_ICR
        sta CIA2_ICR
        lda CIA1_ICR
        lda CIA2_ICR

        ; Timer A: continuous 1000-system-cycle period.
        lda #$00
        sta CIA1_CRA
        lda #<TIMER_PERIOD
        sta CIA1_TA_LO
        lda #>TIMER_PERIOD
        sta CIA1_TA_HI
        lda #$81
        sta CIA1_ICR
        lda #$11
        sta CIA1_CRA

        cli
wait:
        lda RESULT_COUNT
        cmp #TARGET_COUNT
        bcc wait

        sei
        lda #$00
        sta CIA1_CRA
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

        ; First ABI-safe timestamp after preserving the admitted registers.
        ; The two-byte CIA counter is not latched on read, so sample it until
        ; the high byte is stable around the low-byte read.
        jsr read_timer_a
        lda CIA1_ICR
        ldx RESULT_COUNT
        bne not_first
        sta RESULT_FIRST
not_first:
        sta RESULT_LAST
        and #$81
        cmp #$81
        beq source_ok
        inc RESULT_BAD
source_ok:
        ldx RESULT_COUNT
        txa
        asl
        tax
        sec
        lda #<TIMER_PERIOD
        sbc TIMER_LOW
        sta SAMPLE_BASE,x
        inx
        lda #>TIMER_PERIOD
        sbc TIMER_HIGH
        sta SAMPLE_BASE,x
        inc RESULT_COUNT
        bne count_done
        inc RESULT_COUNT+1
count_done:
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
