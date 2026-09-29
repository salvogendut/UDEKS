; SPDX-License-Identifier: GPL-3.0-or-later
;
; 8502 half of the bidirectional C128 ownership-transfer benchmark.

        .setcpu "6502"
        .segment "CODE"

MMU_MCR             = $d505
CPU_SPEED           = $d030
CIA1_TB_LO          = $dc06
CIA1_TB_HI          = $dc07
CIA1_ICR            = $dc0d
CIA1_CRB            = $dc0f

MAILBOX             = $f000
MB_MAGIC0           = MAILBOX + 0
MB_ABI_MAJOR        = MAILBOX + 4
MB_ABI_MINOR        = MAILBOX + 5
MB_STATE            = MAILBOX + 6
MB_OPCODE           = MAILBOX + 7
MB_SEQUENCE_LO      = MAILBOX + 8
MB_SEQUENCE_HI      = MAILBOX + 9
MB_STATUS           = MAILBOX + 10
MB_FLAGS            = MAILBOX + 11
MB_ARG0_LO          = MAILBOX + 12
MB_ARG0_HI          = MAILBOX + 13
MB_ARG1_LO          = MAILBOX + 14
MB_ARG1_HI          = MAILBOX + 15
MB_LENGTH_LO        = MAILBOX + 16
MB_LENGTH_HI        = MAILBOX + 17
MB_RESULT_LO        = MAILBOX + 18
MB_RESULT_HI        = MAILBOX + 19

MB_IDLE             = 0
MB_SUBMITTED        = 1
MB_RUNNING          = 2
MB_COMPLETE         = 3

CONTROL             = $f170
PHASE               = CONTROL + 0
PEER_COUNT_LO       = CONTROL + 1
PEER_COUNT_HI       = CONTROL + 2
ERROR_CODE          = CONTROL + 3

PHASE_READY         = 1
PHASE_8502_BARE     = 2
PHASE_8502_MAIL     = 3
PHASE_Z80_BARE      = 4
PHASE_Z80_MAIL_PREP = 5
PHASE_Z80_MAIL      = 6
PHASE_COMPLETE      = 7
PHASE_ERROR         = $80

RESULT              = $f180
RESULT_STATE        = RESULT + 5
RESULT_ERROR        = RESULT + 11
RESULT_8502_SPEED   = RESULT + 12
REC_8502_BARE       = RESULT + 16
REC_8502_MAIL       = RESULT + 24
REC_Z80_BARE        = RESULT + 32
REC_Z80_MAIL        = RESULT + 40

ITERATIONS          = 64

ERR_PHASE           = 1
ERR_MAILBOX         = 2
ERR_RESPONSE        = 3
ERR_TIMER           = 4
ERR_COUNT           = 5

start:
        sei
        cld
        ldx #$ff
        txs

        lda #$00
        ldx #$00
clear_mailbox:
        sta MAILBOX,x
        inx
        cpx #$40
        bne clear_mailbox
        ldx #$00
clear_result:
        sta RESULT,x
        inx
        cpx #$40
        bne clear_result
        sta PEER_COUNT_LO
        sta PEER_COUNT_HI
        sta ERROR_CODE

        lda #'H'
        sta RESULT+0
        lda #'N'
        sta RESULT+1
        lda #'D'
        sta RESULT+2
        lda #'F'
        sta RESULT+3
        lda #$01
        sta RESULT+4             ; result format
        sta RESULT_STATE         ; running
        lda #$04
        sta RESULT+6             ; case count
        lda #$08
        sta RESULT+7             ; record size
        lda #<ITERATIONS
        sta RESULT+8
        lda #>ITERATIONS
        sta RESULT+9
        lda #$01
        sta RESULT+10            ; CIA1 Timer B
        lda CPU_SPEED
        and #$01
        clc
        adc #$01
        sta RESULT_8502_SPEED

        lda #'U'
        sta MB_MAGIC0+0
        lda #'D'
        sta MB_MAGIC0+1
        lda #'E'
        sta MB_MAGIC0+2
        lda #'K'
        sta MB_MAGIC0+3
        lda #$00
        sta MB_ABI_MAJOR
        lda #$01
        sta MB_ABI_MINOR
        lda #MB_IDLE
        sta MB_STATE

        lda #$01
        sta REC_8502_BARE+0
        lda #$02
        sta REC_8502_MAIL+0
        lda #$03
        sta REC_Z80_BARE+0
        lda #$04
        sta REC_Z80_MAIL+0
        lda #<ITERATIONS
        sta REC_8502_BARE+2
        sta REC_8502_MAIL+2
        sta REC_Z80_BARE+2
        sta REC_Z80_MAIL+2
        lda #>ITERATIONS
        sta REC_8502_BARE+3
        sta REC_8502_MAIL+3
        sta REC_Z80_BARE+3
        sta REC_Z80_MAIL+3

        ; Bare 8502 -> Z80 -> 8502 round trips.
        lda #$00
        sta PEER_COUNT_LO
        sta PEER_COUNT_HI
        lda #PHASE_8502_BARE
        sta PHASE
        jsr timer_start
        ldx #$00
bare_8502_loop:
        lda #$b0
        sta MMU_MCR
        inx
        cpx #ITERATIONS
        bne bare_8502_loop
        jsr timer_elapsed
        bcc bare_timer_ok
        jmp timer_failed
bare_timer_ok:
        sta REC_8502_BARE+4
        stx REC_8502_BARE+5
        jsr require_peer_count
        bcc bare_count_ok
        jmp count_failed
bare_count_ok:
        lda PEER_COUNT_LO
        sta REC_8502_BARE+6
        lda PEER_COUNT_HI
        sta REC_8502_BARE+7

        ; Full ABI mailbox transactions in the same direction.
        lda #$00
        sta PEER_COUNT_LO
        sta PEER_COUNT_HI
        lda #PHASE_8502_MAIL
        sta PHASE
        jsr timer_start
        ldx #$00
mail_8502_loop:
        inx
        lda #$00
        sta MB_STATUS
        sta MB_FLAGS
        sta MB_ARG0_HI
        sta MB_ARG1_HI
        sta MB_LENGTH_LO
        sta MB_LENGTH_HI
        sta MB_RESULT_LO
        sta MB_RESULT_HI
        sta MB_SEQUENCE_HI
        txa
        sta MB_SEQUENCE_LO
        sta MB_ARG0_LO
        eor #$a5
        sta MB_ARG1_LO
        lda #$00
        sta MB_OPCODE
        lda #MB_SUBMITTED        ; publish last
        sta MB_STATE
        lda #$b0
        sta MMU_MCR

        lda MB_STATE
        cmp #MB_COMPLETE
        beq response_state_ok
        jmp response_failed
response_state_ok:
        lda MB_STATUS
        beq response_status_ok
        jmp response_failed
response_status_ok:
        txa
        cmp MB_SEQUENCE_LO
        beq response_sequence_ok
        jmp response_failed
response_sequence_ok:
        eor #$5a
        cmp MB_RESULT_LO
        beq response_low_ok
        jmp response_failed
response_low_ok:
        lda MB_RESULT_HI
        cmp #$a5
        beq response_high_ok
        jmp response_failed
response_high_ok:
        cpx #ITERATIONS
        bne mail_8502_loop
        jsr timer_elapsed
        bcc mail_timer_ok
        jmp timer_failed
mail_timer_ok:
        sta REC_8502_MAIL+4
        stx REC_8502_MAIL+5
        jsr require_peer_count
        bcc mail_count_ok
        jmp count_failed
mail_count_ok:
        lda PEER_COUNT_LO
        sta REC_8502_MAIL+6
        lda PEER_COUNT_HI
        sta REC_8502_MAIL+7

        ; Let the Z80 initiate its bare round trips. The first return from this
        ; write is the first request, so the dispatcher immediately responds.
        lda #$00
        sta PEER_COUNT_LO
        sta PEER_COUNT_HI
        lda #PHASE_Z80_BARE
        sta PHASE
        lda #$b0
        sta MMU_MCR

z80_request_dispatch:
        lda PHASE
        cmp #PHASE_Z80_BARE
        beq respond_z80_bare
        cmp #PHASE_Z80_MAIL_PREP
        beq prepare_z80_mail
        cmp #PHASE_Z80_MAIL
        beq respond_z80_mail
        cmp #PHASE_COMPLETE
        beq benchmark_complete
        cmp #PHASE_ERROR
        beq peer_failed
        lda #ERR_PHASE
        jmp fail

respond_z80_bare:
        jsr increment_peer_count
        lda #$b0
        sta MMU_MCR
        jmp z80_request_dispatch

prepare_z80_mail:
        jsr require_peer_count
        bcs count_failed
        lda #$00
        sta PEER_COUNT_LO
        sta PEER_COUNT_HI
        lda #MB_IDLE
        sta MB_STATE
        lda #PHASE_Z80_MAIL
        sta PHASE
        lda #$b0
        sta MMU_MCR
        jmp z80_request_dispatch

respond_z80_mail:
        jsr validate_mailbox
        bcs mailbox_failed
        lda #MB_RUNNING
        sta MB_STATE
        lda MB_SEQUENCE_LO
        eor #$5a
        sta MB_RESULT_LO
        lda MB_SEQUENCE_HI
        eor #$a5
        sta MB_RESULT_HI
        lda #$00
        sta MB_STATUS
        jsr increment_peer_count
        lda #MB_COMPLETE         ; publish result last
        sta MB_STATE
        lda #$b0
        sta MMU_MCR
        jmp z80_request_dispatch

benchmark_complete:
        jsr require_peer_count
        bcs count_failed
        lda #$02
        sta RESULT_STATE
halt:
        jmp halt

peer_failed:
        lda ERROR_CODE
        bne fail
        lda #ERR_RESPONSE
        jmp fail
mailbox_failed:
        lda #ERR_MAILBOX
        jmp fail
response_failed:
        lda #ERR_RESPONSE
        jmp fail
timer_failed:
        lda #ERR_TIMER
        jmp fail
count_failed:
        lda #ERR_COUNT
fail:
        sta ERROR_CODE
        sta RESULT_ERROR
        lda #PHASE_ERROR
        sta PHASE
        lda #$80
        sta RESULT_STATE
        jmp halt

increment_peer_count:
        inc PEER_COUNT_LO
        bne increment_done
        inc PEER_COUNT_HI
increment_done:
        rts

require_peer_count:
        lda PEER_COUNT_LO
        cmp #<ITERATIONS
        bne count_bad
        lda PEER_COUNT_HI
        cmp #>ITERATIONS
        bne count_bad
        clc
        rts
count_bad:
        sec
        rts

validate_mailbox:
        lda MB_MAGIC0+0
        cmp #'U'
        bne mailbox_bad
        lda MB_MAGIC0+1
        cmp #'D'
        bne mailbox_bad
        lda MB_MAGIC0+2
        cmp #'E'
        bne mailbox_bad
        lda MB_MAGIC0+3
        cmp #'K'
        bne mailbox_bad
        lda MB_ABI_MAJOR
        bne mailbox_bad
        lda MB_ABI_MINOR
        cmp #$01
        bne mailbox_bad
        lda MB_STATE
        cmp #MB_SUBMITTED
        bne mailbox_bad
        lda MB_OPCODE
        bne mailbox_bad
        clc
        rts
mailbox_bad:
        sec
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

; Return elapsed ticks in X:A. Carry set means timer underflow.
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
        clc
        rts
timer_overflow:
        pla
        sec
        rts
