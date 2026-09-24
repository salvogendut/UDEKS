; SPDX-License-Identifier: GPL-3.0-or-later
;
; 8502 controller and worker for the end-to-end offload crossover sweep.

        .setcpu "6502"
        .segment "CODE"

MMU_MCR             = $d505
CPU_SPEED           = $d030
CIA1_TB_LO          = $dc06
CIA1_TB_HI          = $dc07
CIA1_ICR            = $dc0d
CIA1_CRB            = $dc0f
VIC_BORDER          = $d020

SOURCE              = $c000
DESTINATION         = $c800
MAX_SIZE            = 2048

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

OP_COPY             = 1
OP_CHECKSUM16       = 2
OP_TRANSFORM        = 3

CONTROL             = $f080
PHASE               = CONTROL + 0
CUR_OP              = CONTROL + 1
CUR_SIZE_INDEX      = CONTROL + 2
RECORD_INDEX        = CONTROL + 3
ERROR_CODE          = CONTROL + 4
WORK_RESULT_LO      = CONTROL + 5
WORK_RESULT_HI      = CONTROL + 6

PHASE_READY         = 1
PHASE_8502_SWEEP    = 2
PHASE_Z80_SWEEP     = 3
PHASE_Z80_ACTIVE    = 4
PHASE_COMPLETE      = 5
PHASE_ERROR         = $80

RESULT              = $f400
RESULT_STATE        = RESULT + 5
RESULT_SPEED        = RESULT + 10
RESULT_ERROR        = RESULT + 11
RECORD_BASE         = RESULT + 32
RECORD_COUNT        = 24
RECORD_SIZE         = 16

SRC_PTR             = $f0
DST_PTR             = $f2
LENGTH              = $f4
SUM                 = $f6
REC_PTR             = $f8

SIZE_COUNT          = 8

ERR_PHASE           = 1
ERR_MAILBOX         = 2
ERR_RESPONSE        = 3
ERR_TIMER           = 4
ERR_VALIDATION      = 5
ERR_LAYOUT          = 6

start:
        sei
        cld
        ldx #$ff
        txs
        lda #$00
        sta VIC_BORDER

        lda #$00
        ldx #$00
clear_mailbox:
        sta MAILBOX,x
        inx
        cpx #$40
        bne clear_mailbox
        ldx #$00
clear_result_pages:
        sta RESULT,x
        sta RESULT+$100,x
        inx
        bne clear_result_pages
        sta ERROR_CODE

        lda #'X'
        sta RESULT+0
        lda #'O'
        sta RESULT+1
        lda #'F'
        sta RESULT+2
        lda #'S'
        sta RESULT+3
        lda #$01
        sta RESULT+4
        sta RESULT_STATE
        lda #$03
        sta RESULT+6             ; operation count
        lda #SIZE_COUNT
        sta RESULT+7
        lda #RECORD_SIZE
        sta RESULT+8
        lda #$01
        sta RESULT+9             ; CIA1 Timer B
        lda CPU_SPEED
        and #$01
        clc
        adc #$01
        sta RESULT_SPEED
        lda #RECORD_COUNT
        sta RESULT+12
        lda #>SOURCE
        sta RESULT+13
        lda #>DESTINATION
        sta RESULT+14
        lda #>MAX_SIZE
        sta RESULT+15

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

        jsr initialize_source
        jsr initialize_records

        lda #PHASE_8502_SWEEP
        sta PHASE
        lda #OP_COPY
        sta CUR_OP
        lda #$00
        sta CUR_SIZE_INDEX
        sta RECORD_INDEX
        lda #<RECORD_BASE
        sta REC_PTR
        lda #>RECORD_BASE
        sta REC_PTR+1

run_8502_record:
        jsr setup_job_from_record
        jsr clear_destination
        jsr timer_start
        jsr run_local_operation
        jsr timer_elapsed
        bcc local_timer_ok
        jmp timer_failed
local_timer_ok:
        ldy #$04
        sta (REC_PTR),y
        iny
        txa
        sta (REC_PTR),y
        jsr validate_current_output
        bcc local_valid
        jmp validation_failed
local_valid:
        ldy #$01
        lda (REC_PTR),y
        ora #$01
        sta (REC_PTR),y

        jsr setup_job_from_record
        jsr clear_destination
        jsr timer_start
        jsr publish_request
        lda #$b0
        sta MMU_MCR
        jsr validate_response
        bcc offload_response_ok
        jmp response_failed
offload_response_ok:
        jsr timer_elapsed
        bcc offload_timer_ok
        jmp timer_failed
offload_timer_ok:
        ldy #$06
        sta (REC_PTR),y
        iny
        txa
        sta (REC_PTR),y
        jsr validate_current_output
        bcc offload_valid
        jmp validation_failed
offload_valid:
        ldy #$0c
        lda WORK_RESULT_LO
        sta (REC_PTR),y
        iny
        lda WORK_RESULT_HI
        sta (REC_PTR),y
        ldy #$01
        lda (REC_PTR),y
        ora #$02
        sta (REC_PTR),y

        inc RECORD_INDEX
        inc CUR_SIZE_INDEX
        lda CUR_SIZE_INDEX
        cmp #SIZE_COUNT
        bcc advance_8502_record
        lda #$00
        sta CUR_SIZE_INDEX
        inc CUR_OP
advance_8502_record:
        clc
        lda REC_PTR
        adc #RECORD_SIZE
        sta REC_PTR
        bcc record_pointer_ok
        inc REC_PTR+1
record_pointer_ok:
        lda RECORD_INDEX
        cmp #RECORD_COUNT
        bcs sweep_8502_done
        jmp run_8502_record

sweep_8502_done:
        lda #PHASE_Z80_SWEEP
        sta PHASE
        lda #$b0
        sta MMU_MCR

z80_request_dispatch:
        lda PHASE
        cmp #PHASE_Z80_ACTIVE
        beq service_z80_request
        cmp #PHASE_COMPLETE
        beq benchmark_complete
        cmp #PHASE_ERROR
        bne unexpected_phase
        jmp peer_failed
unexpected_phase:
        lda #ERR_PHASE
        jmp fail

service_z80_request:
        jsr validate_mailbox
        bcc z80_mailbox_ok
        jmp mailbox_failed
z80_mailbox_ok:
        lda #MB_RUNNING
        sta MB_STATE
        lda MB_OPCODE
        sta CUR_OP
        lda MB_LENGTH_LO
        sta LENGTH
        lda MB_LENGTH_HI
        sta LENGTH+1
        lda #<SOURCE
        sta SRC_PTR
        lda #>SOURCE
        sta SRC_PTR+1
        lda #<DESTINATION
        sta DST_PTR
        lda #>DESTINATION
        sta DST_PTR+1
        jsr run_local_operation
        lda WORK_RESULT_LO
        sta MB_RESULT_LO
        lda WORK_RESULT_HI
        sta MB_RESULT_HI
        lda #$00
        sta MB_STATUS
        lda #MB_COMPLETE
        sta MB_STATE
        lda #$b0
        sta MMU_MCR
        jmp z80_request_dispatch

benchmark_complete:
        lda #<RECORD_BASE
        sta REC_PTR
        lda #>RECORD_BASE
        sta REC_PTR+1
        ldx #RECORD_COUNT
verify_records:
        ldy #$01
        lda (REC_PTR),y
        cmp #$0f
        bne layout_failed
        clc
        lda REC_PTR
        adc #RECORD_SIZE
        sta REC_PTR
        bcc verify_pointer_ok
        inc REC_PTR+1
verify_pointer_ok:
        dex
        bne verify_records
        lda #$02
        sta RESULT_STATE
        lda #$05                ; green: complete and validated
        sta VIC_BORDER
halt:
        jmp halt

peer_failed:
        lda ERROR_CODE
        bne fail
        lda #ERR_RESPONSE
        bne fail
mailbox_failed:
        lda #ERR_MAILBOX
        bne fail
response_failed:
        lda #ERR_RESPONSE
        bne fail
timer_failed:
        lda #ERR_TIMER
        bne fail
validation_failed:
        lda #ERR_VALIDATION
        bne fail
layout_failed:
        lda #ERR_LAYOUT
fail:
        sta ERROR_CODE
        sta RESULT_ERROR
        lda #PHASE_ERROR
        sta PHASE
        sta RESULT_STATE
        lda #$02                ; red: self-check or protocol failure
        sta VIC_BORDER
        jmp halt

initialize_source:
        lda #<SOURCE
        sta SRC_PTR
        lda #>SOURCE
        sta SRC_PTR+1
        lda #$0b
        ldx #>MAX_SIZE
        ldy #$00
source_byte:
        sta (SRC_PTR),y
        clc
        adc #$25
        iny
        bne source_byte
        inc SRC_PTR+1
        dex
        bne source_byte
        rts

initialize_records:
        lda #<RECORD_BASE
        sta REC_PTR
        lda #>RECORD_BASE
        sta REC_PTR+1
        lda #OP_COPY
        sta CUR_OP
        lda #$00
        sta CUR_SIZE_INDEX
        sta RECORD_INDEX
record_init_loop:
        ldy #$00
        lda CUR_OP
        sta (REC_PTR),y
        iny
        lda #$00
        sta (REC_PTR),y
        ldx CUR_SIZE_INDEX
        ldy #$02
        lda size_low,x
        sta (REC_PTR),y
        iny
        lda size_high,x
        sta (REC_PTR),y
        lda CUR_OP
        cmp #OP_TRANSFORM
        beq transform_expected
        lda expected_source_low,x
        pha
        lda expected_source_high,x
        jmp store_expected
transform_expected:
        lda expected_transform_low,x
        pha
        lda expected_transform_high,x
store_expected:
        ldy #$0f
        sta (REC_PTR),y
        dey
        pla
        sta (REC_PTR),y

        inc RECORD_INDEX
        inc CUR_SIZE_INDEX
        lda CUR_SIZE_INDEX
        cmp #SIZE_COUNT
        bcc init_advance
        lda #$00
        sta CUR_SIZE_INDEX
        inc CUR_OP
init_advance:
        clc
        lda REC_PTR
        adc #RECORD_SIZE
        sta REC_PTR
        bcc init_pointer_ok
        inc REC_PTR+1
init_pointer_ok:
        lda RECORD_INDEX
        cmp #RECORD_COUNT
        bcc record_init_loop
        rts

setup_job_from_record:
        lda #<SOURCE
        sta SRC_PTR
        lda #>SOURCE
        sta SRC_PTR+1
        lda #<DESTINATION
        sta DST_PTR
        lda #>DESTINATION
        sta DST_PTR+1
        ldy #$02
        lda (REC_PTR),y
        sta LENGTH
        iny
        lda (REC_PTR),y
        sta LENGTH+1
        rts

clear_destination:
        lda #<DESTINATION
        sta DST_PTR
        lda #>DESTINATION
        sta DST_PTR+1
        lda #$00
        ldx #>MAX_SIZE
        ldy #$00
clear_destination_byte:
        sta (DST_PTR),y
        iny
        bne clear_destination_byte
        inc DST_PTR+1
        dex
        bne clear_destination_byte
        lda #<DESTINATION
        sta DST_PTR
        lda #>DESTINATION
        sta DST_PTR+1
        rts

run_local_operation:
        lda CUR_OP
        cmp #OP_COPY
        beq copy_operation
        cmp #OP_CHECKSUM16
        beq checksum_operation
        cmp #OP_TRANSFORM
        beq transform_operation
        lda #ERR_MAILBOX
        jmp fail

copy_operation:
        jsr copy_buffer
        lda LENGTH
        sta WORK_RESULT_LO
        lda LENGTH+1
        sta WORK_RESULT_HI
        rts

transform_operation:
        jsr transform_buffer
        lda LENGTH
        sta WORK_RESULT_LO
        lda LENGTH+1
        sta WORK_RESULT_HI
        rts

checksum_operation:
        jsr checksum_buffer
        rts

copy_buffer:
        lda LENGTH+1
        beq copy_tail
        tax
        ldy #$00
copy_page_byte:
        lda (SRC_PTR),y
        sta (DST_PTR),y
        iny
        bne copy_page_byte
        inc SRC_PTR+1
        inc DST_PTR+1
        dex
        bne copy_page_byte
        rts
copy_tail:
        ldy #$00
copy_tail_byte:
        lda (SRC_PTR),y
        sta (DST_PTR),y
        iny
        cpy LENGTH
        bne copy_tail_byte
        rts

transform_buffer:
        lda LENGTH+1
        beq transform_tail
        tax
        ldy #$00
transform_page_byte:
        lda (SRC_PTR),y
        eor #$a5
        asl a
        adc #$00
        sta (DST_PTR),y
        iny
        bne transform_page_byte
        inc SRC_PTR+1
        inc DST_PTR+1
        dex
        bne transform_page_byte
        rts
transform_tail:
        ldy #$00
transform_tail_byte:
        lda (SRC_PTR),y
        eor #$a5
        asl a
        adc #$00
        sta (DST_PTR),y
        iny
        cpy LENGTH
        bne transform_tail_byte
        rts

checksum_buffer:
        lda #$00
        sta SUM
        sta SUM+1
        lda LENGTH+1
        beq checksum_tail
        tax
        ldy #$00
checksum_page_byte:
        clc
        lda SUM
        adc (SRC_PTR),y
        sta SUM
        bcc checksum_page_no_carry
        inc SUM+1
checksum_page_no_carry:
        iny
        bne checksum_page_byte
        inc SRC_PTR+1
        dex
        bne checksum_page_byte
        jmp checksum_done
checksum_tail:
        ldy #$00
checksum_tail_byte:
        clc
        lda SUM
        adc (SRC_PTR),y
        sta SUM
        bcc checksum_tail_no_carry
        inc SUM+1
checksum_tail_no_carry:
        iny
        cpy LENGTH
        bne checksum_tail_byte
checksum_done:
        lda SUM
        sta WORK_RESULT_LO
        lda SUM+1
        sta WORK_RESULT_HI
        rts

validate_current_output:
        lda CUR_OP
        cmp #OP_CHECKSUM16
        beq compare_expected
        lda #<DESTINATION
        sta SRC_PTR
        lda #>DESTINATION
        sta SRC_PTR+1
        jsr checksum_buffer
compare_expected:
        ldy #$0e
        lda WORK_RESULT_LO
        cmp (REC_PTR),y
        bne validation_bad
        iny
        lda WORK_RESULT_HI
        cmp (REC_PTR),y
        bne validation_bad
        clc
        rts
validation_bad:
        sec
        rts

publish_request:
        lda #$00
        sta MB_STATUS
        sta MB_FLAGS
        sta MB_RESULT_LO
        sta MB_RESULT_HI
        sta MB_SEQUENCE_HI
        lda RECORD_INDEX
        clc
        adc #$01
        sta MB_SEQUENCE_LO
        lda CUR_OP
        sta MB_OPCODE
        lda #<SOURCE
        sta MB_ARG0_LO
        lda #>SOURCE
        sta MB_ARG0_HI
        lda #<DESTINATION
        sta MB_ARG1_LO
        lda #>DESTINATION
        sta MB_ARG1_HI
        lda LENGTH
        sta MB_LENGTH_LO
        lda LENGTH+1
        sta MB_LENGTH_HI
        lda #MB_SUBMITTED
        sta MB_STATE
        rts

validate_response:
        lda MB_STATE
        cmp #MB_COMPLETE
        bne response_bad
        lda MB_STATUS
        bne response_bad
        lda MB_SEQUENCE_HI
        bne response_bad
        lda RECORD_INDEX
        clc
        adc #$01
        cmp MB_SEQUENCE_LO
        bne response_bad
        lda CUR_OP
        cmp #OP_CHECKSUM16
        beq response_checksum
        lda LENGTH
        cmp MB_RESULT_LO
        bne response_bad
        lda LENGTH+1
        cmp MB_RESULT_HI
        bne response_bad
        clc
        rts
response_checksum:
        ldy #$0e
        lda MB_RESULT_LO
        cmp (REC_PTR),y
        bne response_bad
        iny
        lda MB_RESULT_HI
        cmp (REC_PTR),y
        bne response_bad
        clc
        rts
response_bad:
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
        cmp #OP_COPY
        bcc mailbox_bad
        cmp #(OP_TRANSFORM + 1)
        bcs mailbox_bad
        lda MB_ARG0_LO
        cmp #<SOURCE
        bne mailbox_bad
        lda MB_ARG0_HI
        cmp #>SOURCE
        bne mailbox_bad
        lda MB_ARG1_LO
        cmp #<DESTINATION
        bne mailbox_bad
        lda MB_ARG1_HI
        cmp #>DESTINATION
        bne mailbox_bad
        lda MB_LENGTH_HI
        cmp #$09
        bcs mailbox_bad
        ora MB_LENGTH_LO
        beq mailbox_bad
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

timer_elapsed:
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

size_low:
        .byte $10, $20, $40, $80, $00, $00, $00, $00
size_high:
        .byte $00, $00, $00, $00, $01, $02, $04, $08
expected_source_low:
        .byte $08, $10, $20, $40, $80, $00, $00, $00
expected_source_high:
        .byte $07, $0f, $20, $3f, $7f, $ff, $fe, $fc
expected_transform_low:
        .byte $1a, $b1, $5f, $c1, $80, $00, $00, $00
expected_transform_high:
        .byte $08, $0f, $1f, $3f, $7f, $ff, $fe, $fc
