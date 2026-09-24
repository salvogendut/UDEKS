; SPDX-License-Identifier: GPL-3.0-or-later
;
; Instrumented CIA1 Timer-A interrupt-service benchmark for Z80 IM1.

        .module irq_service_z80
        .globl  _start

RESULT              = 0xf180
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

CUR_VARIANT         = 0xf178
CUR_SAMPLE          = 0xf179
TIMER_LOW           = 0xf17a
TIMER_HIGH          = 0xf17b

VARIANT_COUNT       = 3
SAMPLES_PER_VARIANT = 16
TARGET_COUNT        = 48
TIMER_PERIOD        = 4000

        .area   _CODE
_start::
        di
        ld      sp, #0xeff0
        ld      a, #0xc3
        ld      (0x0038), a
        ld      hl, #irq_handler
        ld      (0x0039), hl

        ; Clear the 320-byte result block.
        xor     a
        ld      hl, #RESULT
        ld      (hl), a
        ld      de, #(RESULT + 1)
        ld      bc, #319
        ldir

        ld      a, #'I'
        ld      (RESULT + 0), a
        ld      a, #'R'
        ld      (RESULT + 1), a
        ld      a, #'Q'
        ld      (RESULT + 2), a
        ld      a, #'S'
        ld      (RESULT + 3), a
        ld      a, #0x01
        ld      (RESULT + 4), a
        ld      a, #0x02
        ld      (RESULT + 5), a       ; CPU: Z80
        ld      (RESULT + 6), a       ; mode: IM1
        ld      a, #0x01
        ld      (RESULT_STATE), a
        ld      a, #VARIANT_COUNT
        ld      (RESULT_VARIANTS), a
        ld      a, #SAMPLES_PER_VARIANT
        ld      (RESULT_SAMPLES), a
        ld      a, #TARGET_COUNT
        ld      (RESULT_TARGET), a
        xor     a
        ld      (RESULT_TARGET + 1), a
        ld      a, #0xa0
        ld      (RESULT_PERIOD), a
        ld      a, #0x0f
        ld      (RESULT_PERIOD + 1), a
        ld      hl, #dispatch_target
        ld      (RESULT_VECTOR), hl
        xor     a
        ld      (CUR_VARIANT), a
        ld      (CUR_SAMPLE), a

        ; Disable and acknowledge other sources, then enable CIA1 Timer A.
        ld      bc, #0xd01a
        out     (c), a
        ld      a, #0x0f
        dec     c
        out     (c), a
        ld      a, #0x7f
        ld      bc, #0xdc0d
        out     (c), a
        in      a, (c)
        ld      a, #0x7f
        ld      bc, #0xdd0d
        out     (c), a
        in      a, (c)
        ld      a, #0x81
        ld      bc, #0xdc0d
        out     (c), a

prepare_sample:
        di
        xor     a
        ld      bc, #0xdc0e
        out     (c), a
        dec     c
        in      a, (c)
        ld      hl, #wait_irq
        ld      (wait_irq + 1), hl
        ld      a, #0xa0
        ld      bc, #0xdc04
        out     (c), a
        ld      a, #0x0f
        inc     c
        out     (c), a
        ld      a, #0x11
        ld      bc, #0xdc0e
        out     (c), a
        ei
        nop

wait_irq:
        jp      wait_irq

resume_irq:
        ; First timestamp after RETI and the patched wait jump.
        ld      bc, #0xdc04
        in      a, (c)
        ld      (TIMER_LOW), a
        inc     c
        in      a, (c)
        ld      (TIMER_HIGH), a
        di
        xor     a
        ld      bc, #0xdc0e
        out     (c), a
        ld      de, (TIMER_LOW)
        ld      hl, #TIMER_PERIOD
        or      a
        sbc     hl, de
        push    hl
        call    sample_offset
        ld      hl, #RESUME_BASE
        add     hl, de
        pop     de
        ld      (hl), e
        inc     hl
        ld      (hl), d

        ld      hl, #CUR_SAMPLE
        inc     (hl)
        ld      a, (hl)
        cp      #SAMPLES_PER_VARIANT
        jp      c, prepare_sample
        ld      (hl), #0x00
        ld      hl, #CUR_VARIANT
        inc     (hl)
        ld      a, (hl)
        cp      #VARIANT_COUNT
        jp      c, prepare_sample

        ld      a, #0x7f
        ld      bc, #0xdc0d
        out     (c), a
        in      a, (c)
        ld      a, #0x02
        ld      (RESULT_STATE), a
halt:
        jr      halt

irq_handler:
        push    af
        push    bc
        push    de
        push    hl
        push    ix
        push    iy

        ld      bc, #0xdc04
        in      a, (c)
        ld      (TIMER_LOW), a
        inc     c
        in      a, (c)
        ld      (TIMER_HIGH), a
        ld      bc, #0xdc0d
        in      a, (c)
        ld      (RESULT_LAST), a
        ld      hl, (RESULT_OBSERVED)
        ld      e, a
        ld      a, h
        or      l
        jr      nz, not_first
        ld      a, e
        ld      (RESULT_FIRST), a
not_first:
        ld      a, e
        and     #0x81
        cp      #0x81
        jr      z, source_ok
        ld      hl, #RESULT_BAD
        inc     (hl)
        jr      nz, source_ok
        inc     hl
        inc     (hl)
source_ok:
        ld      de, (TIMER_LOW)
        ld      hl, #TIMER_PERIOD
        or      a
        sbc     hl, de
        push    hl
        call    sample_offset
        ld      hl, #ENTRY_BASE
        add     hl, de
        pop     de
        ld      (hl), e
        inc     hl
        ld      (hl), d

        ld      a, (CUR_VARIANT)
        or      a
        jr      z, variant_done
        cp      #0x01
        jr      nz, dispatch_variant

        ; Kernel-tick variant: 32-bit monotonic increment plus event signal.
        ld      hl, (RESULT_TICK)
        inc     hl
        ld      (RESULT_TICK), hl
        ld      a, h
        or      l
        jr      nz, tick_event
        ld      hl, (RESULT_TICK + 2)
        inc     hl
        ld      (RESULT_TICK + 2), hl
tick_event:
        ld      a, #0x01
        ld      (RESULT_EVENT), a
        jr      variant_done

dispatch_variant:
        call    dispatch_thunk

variant_done:
        ld      bc, #0xdc04
        in      a, (c)
        ld      (TIMER_LOW), a
        inc     c
        in      a, (c)
        ld      (TIMER_HIGH), a
        ld      de, (TIMER_LOW)
        ld      hl, #TIMER_PERIOD
        or      a
        sbc     hl, de
        push    hl
        call    sample_offset
        ld      hl, #PREEXIT_BASE
        add     hl, de
        pop     de
        ld      (hl), e
        inc     hl
        ld      (hl), d

        ld      hl, #RESULT_OBSERVED
        inc     (hl)
        jr      nz, count_done
        inc     hl
        inc     (hl)
count_done:
        ld      hl, #resume_irq
        ld      (wait_irq + 1), hl

        pop     iy
        pop     ix
        pop     hl
        pop     de
        pop     bc
        pop     af
        ei
        reti

; Return DE = ((variant * 16) + sample) * 2.
sample_offset:
        ld      a, (CUR_VARIANT)
        rlca
        rlca
        rlca
        rlca
        rlca
        ld      e, a
        ld      a, (CUR_SAMPLE)
        add     a, a
        add     a, e
        ld      e, a
        ld      d, #0x00
        ret

dispatch_thunk:
        ld      hl, (RESULT_VECTOR)
        jp      (hl)

dispatch_target:
        ld      hl, #RESULT_DISPATCH
        inc     (hl)
        ret

        .area   _DATA
