; SPDX-License-Identifier: GPL-3.0-or-later
;
; Z80 half of the bidirectional C128 ownership-transfer benchmark.

        .module handoff_z80
        .globl  _start

MMU_MCR             = 0xd505
CIA1_TB_LO          = 0xdc06
CIA1_TB_HI          = 0xdc07
CIA1_ICR            = 0xdc0d
CIA1_CRB            = 0xdc0f

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

MB_IDLE             = 0
MB_SUBMITTED        = 1
MB_RUNNING          = 2
MB_COMPLETE         = 3

CONTROL             = 0xf170
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
PHASE_ERROR         = 0x80

RESULT              = 0xf180
RESULT_STATE        = RESULT + 5
RESULT_ERROR        = RESULT + 11
REC_Z80_BARE        = RESULT + 32
REC_Z80_MAIL        = RESULT + 40

ITERATIONS          = 64

ERR_PHASE           = 1
ERR_MAILBOX         = 2
ERR_RESPONSE        = 3
ERR_TIMER           = 4
ERR_COUNT           = 5

        .area   _CODE
_start::
        di
        ld      sp, #0xeff0
        ld      a, #PHASE_READY
        ld      (PHASE), a
        ld      bc, #MMU_MCR
        ld      a, #0xb1
        out     (c), a            ; return bootstrap ownership to the 8502

dispatch:
        ld      a, (PHASE)
        cp      #PHASE_8502_BARE
        jr      z, respond_8502_bare
        cp      #PHASE_8502_MAIL
        jr      z, respond_8502_mail
        cp      #PHASE_Z80_BARE
        jp      z, initiate_z80_bare
        jp      fail_phase

respond_8502_bare:
        call    increment_peer_count
        ld      bc, #MMU_MCR
        ld      a, #0xb1
        out     (c), a
        jr      dispatch

respond_8502_mail:
        call    validate_mailbox
        jp      c, fail_mailbox
        ld      a, #MB_RUNNING
        ld      (MB_STATE), a
        ld      a, (MB_SEQUENCE_LO)
        xor     #0x5a
        ld      (MB_RESULT_LO), a
        ld      a, (MB_SEQUENCE_HI)
        xor     #0xa5
        ld      (MB_RESULT_HI), a
        xor     a
        ld      (MB_STATUS), a
        call    increment_peer_count
        ld      a, #MB_COMPLETE
        ld      (MB_STATE), a     ; publish result last
        ld      bc, #MMU_MCR
        ld      a, #0xb1
        out     (c), a
        jr      dispatch

initiate_z80_bare:
        call    timer_start
        ld      d, #ITERATIONS
bare_z80_loop:
        ld      bc, #MMU_MCR
        ld      a, #0xb1
        out     (c), a
        dec     d
        jr      nz, bare_z80_loop
        call    timer_elapsed
        jp      c, fail_timer
        ld      (REC_Z80_BARE + 4), de
        call    require_peer_count
        jp      c, fail_count
        ld      hl, (PEER_COUNT_LO)
        ld      (REC_Z80_BARE + 6), hl

        ; The transition yield lets the 8502 validate the bare count and reset
        ; the mailbox before it returns with PHASE_Z80_MAIL.
        ld      a, #PHASE_Z80_MAIL_PREP
        ld      (PHASE), a
        ld      bc, #MMU_MCR
        ld      a, #0xb1
        out     (c), a
        ld      a, (PHASE)
        cp      #PHASE_Z80_MAIL
        jp      nz, fail_phase

        call    timer_start
        ld      d, #ITERATIONS
        ld      e, #0
mail_z80_loop:
        inc     e
        xor     a
        ld      (MB_STATUS), a
        ld      (MB_FLAGS), a
        ld      (MB_ARG0_HI), a
        ld      (MB_ARG1_HI), a
        ld      (MB_LENGTH_LO), a
        ld      (MB_LENGTH_HI), a
        ld      (MB_RESULT_LO), a
        ld      (MB_RESULT_HI), a
        ld      (MB_SEQUENCE_HI), a
        ld      a, e
        ld      (MB_SEQUENCE_LO), a
        ld      (MB_ARG0_LO), a
        xor     #0xa5
        ld      (MB_ARG1_LO), a
        xor     a
        ld      (MB_OPCODE), a
        ld      a, #MB_SUBMITTED
        ld      (MB_STATE), a     ; publish request last
        ld      bc, #MMU_MCR
        ld      a, #0xb1
        out     (c), a

        ld      a, (MB_STATE)
        cp      #MB_COMPLETE
        jp      nz, fail_response
        ld      a, (MB_STATUS)
        or      a
        jp      nz, fail_response
        ld      a, (MB_SEQUENCE_LO)
        cp      e
        jp      nz, fail_response
        xor     #0x5a
        ld      hl, #MB_RESULT_LO
        cp      (hl)
        jp      nz, fail_response
        ld      a, (MB_RESULT_HI)
        cp      #0xa5
        jp      nz, fail_response
        dec     d
        jr      nz, mail_z80_loop

        call    timer_elapsed
        jp      c, fail_timer
        ld      (REC_Z80_MAIL + 4), de
        call    require_peer_count
        jp      c, fail_count
        ld      hl, (PEER_COUNT_LO)
        ld      (REC_Z80_MAIL + 6), hl
        ld      a, #PHASE_COMPLETE
        ld      (PHASE), a
        ld      bc, #MMU_MCR
        ld      a, #0xb1
        out     (c), a
z80_halt:
        jr      z80_halt

increment_peer_count:
        ld      hl, (PEER_COUNT_LO)
        inc     hl
        ld      (PEER_COUNT_LO), hl
        ret

require_peer_count:
        ld      hl, (PEER_COUNT_LO)
        ld      de, #ITERATIONS
        or      a
        sbc     hl, de
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
        or      a
        jr      nz, mailbox_bad
        or      a                   ; clear carry
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

; Return elapsed ticks in DE. Carry set means timer underflow.
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
fail_count:
        ld      a, #ERR_COUNT
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

        ; SDCC's linker expects the standard data area even though all shared
        ; state in this benchmark lives at fixed common-RAM addresses.
        .area   _DATA
