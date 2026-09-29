; SPDX-License-Identifier: GPL-3.0-or-later
;
; Z80 controller and worker for the end-to-end offload crossover sweep.

        .module offload_z80
        .globl  _start

MMU_MCR             = 0xd505
CIA1_TB_LO          = 0xdc06
CIA1_TB_HI          = 0xdc07
CIA1_ICR            = 0xdc0d
CIA1_CRB            = 0xdc0f

SOURCE              = 0xc000
DESTINATION         = 0xc800
MAX_SIZE            = 2048

MAILBOX             = 0xf000
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

MB_SUBMITTED        = 1
MB_RUNNING          = 2
MB_COMPLETE         = 3

OP_COPY             = 1
OP_CHECKSUM16       = 2
OP_TRANSFORM        = 3

CONTROL             = 0xf080
PHASE               = CONTROL + 0
CUR_OP              = CONTROL + 1
RECORD_INDEX        = CONTROL + 3
ERROR_CODE          = CONTROL + 4
WORK_RESULT_LO      = CONTROL + 5
WORK_RESULT_HI      = CONTROL + 6
LENGTH              = CONTROL + 8

PHASE_READY         = 1
PHASE_8502_SWEEP    = 2
PHASE_Z80_SWEEP     = 3
PHASE_Z80_ACTIVE    = 4
PHASE_COMPLETE      = 5
PHASE_ERROR         = 0x80

RESULT              = 0xf400
RESULT_STATE        = RESULT + 5
RESULT_ERROR        = RESULT + 11
RECORD_BASE         = RESULT + 32
RECORD_COUNT        = 24
RECORD_SIZE         = 16

ERR_PHASE           = 1
ERR_MAILBOX         = 2
ERR_RESPONSE        = 3
ERR_TIMER           = 4
ERR_VALIDATION      = 5

        .area   _CODE
_start::
        di
        ld      sp, #0xeff0
        ld      a, #PHASE_READY
        ld      (PHASE), a
        ld      bc, #MMU_MCR
        ld      a, #0xb1
        out     (c), a

dispatch:
        ld      a, (PHASE)
        cp      #PHASE_8502_SWEEP
        jp      z, service_8502_request
        cp      #PHASE_Z80_SWEEP
        jp      z, run_z80_sweep
        jp      fail_phase

service_8502_request:
        call    validate_mailbox
        jp      c, fail_mailbox
        ld      a, #MB_RUNNING
        ld      (MB_STATE), a
        ld      a, (MB_OPCODE)
        ld      (CUR_OP), a
        ld      hl, (MB_LENGTH_LO)
        ld      (LENGTH), hl
        call    run_local_operation
        ld      hl, (WORK_RESULT_LO)
        ld      (MB_RESULT_LO), hl
        xor     a
        ld      (MB_STATUS), a
        ld      a, #MB_COMPLETE
        ld      (MB_STATE), a
        ld      bc, #MMU_MCR
        ld      a, #0xb1
        out     (c), a
        jp      dispatch

run_z80_sweep:
        ld      ix, #RECORD_BASE
        xor     a
        ld      (RECORD_INDEX), a

z80_record_loop:
        ld      a, (ix+0)
        ld      (CUR_OP), a
        ld      l, (ix+2)
        ld      h, (ix+3)
        ld      (LENGTH), hl
        call    clear_destination
        call    timer_start
        call    run_local_operation
        call    timer_elapsed
        jp      c, fail_timer
        ld      (ix+8), e
        ld      (ix+9), d
        call    validate_current_output
        jp      c, fail_validation
        ld      a, (ix+1)
        or      #0x04
        ld      (ix+1), a

        call    clear_destination
        call    timer_start
        call    publish_request
        ld      a, #PHASE_Z80_ACTIVE
        ld      (PHASE), a
        ld      bc, #MMU_MCR
        ld      a, #0xb1
        out     (c), a
        call    validate_response
        jp      c, fail_response
        call    timer_elapsed
        jp      c, fail_timer
        ld      (ix+10), e
        ld      (ix+11), d
        call    validate_current_output
        jp      c, fail_validation
        ld      hl, (WORK_RESULT_LO)
        ld      (ix+12), l
        ld      (ix+13), h
        ld      a, (ix+1)
        or      #0x08
        ld      (ix+1), a

        ld      a, (RECORD_INDEX)
        inc     a
        ld      (RECORD_INDEX), a
        cp      #RECORD_COUNT
        jr      z, z80_sweep_done
        ld      de, #RECORD_SIZE
        add     ix, de
        jp      z80_record_loop

z80_sweep_done:
        ld      a, #PHASE_COMPLETE
        ld      (PHASE), a
        ld      bc, #MMU_MCR
        ld      a, #0xb1
        out     (c), a
z80_halt:
        jr      z80_halt

run_local_operation:
        ld      a, (CUR_OP)
        cp      #OP_COPY
        jr      z, copy_operation
        cp      #OP_CHECKSUM16
        jr      z, checksum_operation
        cp      #OP_TRANSFORM
        jr      z, transform_operation
        jp      fail_mailbox

copy_operation:
        ld      hl, #SOURCE
        ld      de, #DESTINATION
        ld      bc, (LENGTH)
        ldir
        ld      hl, (LENGTH)
        ld      (WORK_RESULT_LO), hl
        ret

checksum_operation:
        ld      hl, #SOURCE
        ld      bc, (LENGTH)
        call    checksum_at_hl
        ld      (WORK_RESULT_LO), de
        ret

transform_operation:
        ld      hl, #SOURCE
        ld      de, #DESTINATION
        ld      bc, (LENGTH)
        ld      a, b
        or      a
        jr      z, transform_tail_setup
transform_page_byte:
        ld      a, (hl)
        xor     #0xa5
        rlca
        ld      (de), a
        inc     hl
        inc     de
        dec     c
        jr      nz, transform_page_byte
        djnz    transform_page_byte
        jr      transform_done
transform_tail_setup:
        ld      b, c
transform_tail_byte:
        ld      a, (hl)
        xor     #0xa5
        rlca
        ld      (de), a
        inc     hl
        inc     de
        djnz    transform_tail_byte
transform_done:
        ld      hl, (LENGTH)
        ld      (WORK_RESULT_LO), hl
        ret

checksum_at_hl:
        ld      de, #0x0000
        ld      a, b
        or      a
        jr      z, checksum_tail_setup
checksum_page_byte:
        ld      a, (hl)
        add     a, e
        ld      e, a
        jr      nc, checksum_no_carry
        inc     d
checksum_no_carry:
        inc     hl
        dec     c
        jr      nz, checksum_page_byte
        djnz    checksum_page_byte
        ret
checksum_tail_setup:
        ld      b, c
checksum_tail_byte:
        ld      a, (hl)
        add     a, e
        ld      e, a
        jr      nc, checksum_tail_no_carry
        inc     d
checksum_tail_no_carry:
        inc     hl
        djnz    checksum_tail_byte
        ret

clear_destination:
        ld      hl, #DESTINATION
        ld      bc, #MAX_SIZE
        ld      e, #0
clear_destination_byte:
        ld      (hl), e
        inc     hl
        dec     bc
        ld      a, b
        or      c
        jr      nz, clear_destination_byte
        ret

validate_current_output:
        ld      a, (CUR_OP)
        cp      #OP_CHECKSUM16
        jr      nz, checksum_destination
        ld      de, (WORK_RESULT_LO)
        jr      compare_expected
checksum_destination:
        ld      hl, #DESTINATION
        ld      bc, (LENGTH)
        call    checksum_at_hl
        ld      (WORK_RESULT_LO), de
compare_expected:
        ld      a, (ix+14)
        cp      e
        jr      nz, validation_bad
        ld      a, (ix+15)
        cp      d
        jr      nz, validation_bad
        or      a
        ret
validation_bad:
        scf
        ret

publish_request:
        xor     a
        ld      (MB_STATUS), a
        ld      (MB_FLAGS), a
        ld      (MB_RESULT_LO), a
        ld      (MB_RESULT_HI), a
        ld      (MB_SEQUENCE_HI), a
        ld      a, (RECORD_INDEX)
        inc     a
        ld      (MB_SEQUENCE_LO), a
        ld      a, (CUR_OP)
        ld      (MB_OPCODE), a
        ld      hl, #SOURCE
        ld      (MB_ARG0_LO), hl
        ld      hl, #DESTINATION
        ld      (MB_ARG1_LO), hl
        ld      hl, (LENGTH)
        ld      (MB_LENGTH_LO), hl
        ld      a, #MB_SUBMITTED
        ld      (MB_STATE), a
        ret

validate_response:
        ld      a, (MB_STATE)
        cp      #MB_COMPLETE
        jr      nz, response_bad
        ld      a, (MB_STATUS)
        or      a
        jr      nz, response_bad
        ld      a, (MB_SEQUENCE_HI)
        or      a
        jr      nz, response_bad
        ld      a, (RECORD_INDEX)
        inc     a
        ld      hl, #MB_SEQUENCE_LO
        cp      (hl)
        jr      nz, response_bad
        ld      a, (CUR_OP)
        cp      #OP_CHECKSUM16
        jr      z, response_checksum
        ld      hl, (MB_RESULT_LO)
        ld      de, (LENGTH)
        or      a
        sbc     hl, de
        jr      nz, response_bad
        or      a
        ret
response_checksum:
        ld      a, (MB_RESULT_LO)
        cp      (ix+14)
        jr      nz, response_bad
        ld      a, (MB_RESULT_HI)
        cp      (ix+15)
        jr      nz, response_bad
        ld      hl, (MB_RESULT_LO)
        ld      (WORK_RESULT_LO), hl
        or      a
        ret
response_bad:
        scf
        ret

validate_mailbox:
        ld      a, (MB_MAGIC0 + 0)
        cp      #'U'
        jr      nz, mailbox_bad
        ld      a, (MB_MAGIC0 + 1)
        cp      #'D'
        jr      nz, mailbox_bad
        ld      a, (MB_MAGIC0 + 2)
        cp      #'E'
        jr      nz, mailbox_bad
        ld      a, (MB_MAGIC0 + 3)
        cp      #'K'
        jr      nz, mailbox_bad
        ld      a, (MB_ABI_MAJOR)
        or      a
        jr      nz, mailbox_bad
        ld      a, (MB_ABI_MINOR)
        cp      #1
        jr      nz, mailbox_bad
        ld      a, (MB_STATE)
        cp      #MB_SUBMITTED
        jr      nz, mailbox_bad
        ld      a, (MB_OPCODE)
        cp      #OP_COPY
        jr      c, mailbox_bad
        cp      #(OP_TRANSFORM + 1)
        jr      nc, mailbox_bad
        ld      hl, (MB_ARG0_LO)
        ld      de, #SOURCE
        or      a
        sbc     hl, de
        jr      nz, mailbox_bad
        ld      hl, (MB_ARG1_LO)
        ld      de, #DESTINATION
        or      a
        sbc     hl, de
        jr      nz, mailbox_bad
        ld      hl, (MB_LENGTH_LO)
        ld      a, h
        or      l
        jr      z, mailbox_bad
        ld      de, #(MAX_SIZE + 1)
        or      a
        sbc     hl, de
        jr      nc, mailbox_bad
        or      a
        ret
mailbox_bad:
        scf
        ret

timer_start:
        ld      bc, #CIA1_ICR
        in      a, (c)
        xor     a
        ld      bc, #CIA1_CRB
        out     (c), a
        ld      a, #0xff
        ld      bc, #CIA1_TB_LO
        out     (c), a
        inc     c
        out     (c), a
        ld      a, #0x11
        ld      bc, #CIA1_CRB
        out     (c), a
        ret

timer_elapsed:
        xor     a
        ld      bc, #CIA1_CRB
        out     (c), a
        ld      bc, #CIA1_TB_LO
        in      a, (c)
        cpl
        ld      e, a
        inc     c
        in      a, (c)
        cpl
        ld      d, a
        ld      bc, #CIA1_ICR
        in      a, (c)
        and     #0x02
        ret     z
        scf
        ret

fail_phase:
        ld      a, #ERR_PHASE
        jr      fail
fail_mailbox:
        ld      a, #ERR_MAILBOX
        jr      fail
fail_response:
        ld      a, #ERR_RESPONSE
        jr      fail
fail_timer:
        ld      a, #ERR_TIMER
        jr      fail
fail_validation:
        ld      a, #ERR_VALIDATION
fail:
        ld      (ERROR_CODE), a
        ld      (RESULT_ERROR), a
        ld      a, #PHASE_ERROR
        ld      (PHASE), a
        ld      (RESULT_STATE), a
        ld      bc, #MMU_MCR
        ld      a, #0xb1
        out     (c), a
        jp      z80_halt

        .area   _DATA
