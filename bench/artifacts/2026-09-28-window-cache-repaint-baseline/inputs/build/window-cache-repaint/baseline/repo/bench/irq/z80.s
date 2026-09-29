; SPDX-License-Identifier: GPL-3.0-or-later
;
; CIA1 Timer-A repeated-interrupt qualification for the Z80 in IM1.

        .module irq_z80
        .globl  _start

RESULT          = 0xf180
RESULT_STATE    = RESULT + 7
RESULT_TARGET   = RESULT + 8
RESULT_COUNT    = RESULT + 10
RESULT_BAD      = RESULT + 12
RESULT_FIRST    = RESULT + 14
RESULT_LAST     = RESULT + 15
RESULT_PERIOD   = RESULT + 16
RESULT_SAMPLES  = RESULT + 18
SAMPLE_BASE     = RESULT + 32
TIMER_LOW       = 0xf17e
TIMER_HIGH      = 0xf17f

TARGET_COUNT    = 32
TIMER_PERIOD    = 1000

        .area   _CODE
_start::
        di
        ld      sp, #0xeff0

        ; IM1 enters $0038. Bottom common RAM makes this bank-zero jump
        ; visible even though CR bit 6 selected normal Z80 RAM.
        ld      a, #0xc3
        ld      (0x0038), a
        ld      hl, #irq_handler
        ld      (0x0039), hl

        ; Start from a deterministic result block, including all samples.
        xor     a
        ld      hl, #RESULT
        ld      b, #128
clear_result:
        ld      (hl), a
        inc     hl
        djnz    clear_result

        ld      hl, #RESULT
        ld      (hl), #'I'
        inc     hl
        ld      (hl), #'R'
        inc     hl
        ld      (hl), #'Q'
        inc     hl
        ld      (hl), #'P'
        inc     hl
        ld      (hl), #0x01
        inc     hl
        ld      (hl), #0x02       ; CPU: Z80
        inc     hl
        ld      (hl), #0x02       ; mode: IM1
        inc     hl
        ld      (hl), #0x01       ; running
        inc     hl
        ld      (hl), #TARGET_COUNT
        inc     hl
        xor     a
        ld      (RESULT_TARGET + 1), a
        ld      (RESULT_COUNT), a
        ld      (RESULT_COUNT + 1), a
        ld      (RESULT_BAD), a
        ld      (RESULT_BAD + 1), a
        ld      (RESULT_FIRST), a
        ld      (RESULT_LAST), a
        ld      a, #0xe8           ; 1000, little endian
        ld      (RESULT_PERIOD), a
        ld      a, #0x03
        ld      (RESULT_PERIOD + 1), a
        ld      a, #TARGET_COUNT
        ld      (RESULT_SAMPLES), a
        xor     a
        ld      (RESULT_SAMPLES + 1), a

        ; Disable and acknowledge VIC/CIA interrupt sources.
        ld      bc, #0xd01a
        out     (c), a
        ld      a, #0x0f
        ld      bc, #0xd019
        out     (c), a
        ld      a, #0x7f
        ld      bc, #0xdc0d
        out     (c), a
        in      a, (c)
        ld      a, #0x7f
        ld      bc, #0xdd0d
        out     (c), a
        in      a, (c)

        ; Timer A: continuous 1000-system-cycle period.
        xor     a
        ld      bc, #0xdc0e
        out     (c), a
        ld      a, #0xe8
        ld      bc, #0xdc04
        out     (c), a
        ld      a, #0x03
        inc     c
        out     (c), a
        ld      a, #0x81
        ld      bc, #0xdc0d
        out     (c), a
        ld      a, #0x11
        inc     c
        out     (c), a

        im      1
        ei
        nop
wait:
        halt
        ld      a, (RESULT_COUNT)
        cp      #TARGET_COUNT
        jr      c, wait

        di
        xor     a
        ld      bc, #0xdc0e
        out     (c), a
        ld      a, #0x7f
        dec     c
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

        ; The CIA counter is not latched on read. Sample high/low/high until
        ; the high byte is stable around the low-byte read.
        call    read_timer_a
        ld      bc, #0xdc0d
        in      a, (c)
        ld      hl, #RESULT_COUNT
        ld      e, (hl)
        ld      d, a
        ld      a, e
        or      a
        jr      nz, not_first
        ld      a, d
        ld      (RESULT_FIRST), a
not_first:
        ld      a, d
        ld      (RESULT_LAST), a
        and     #0x81
        cp      #0x81
        jr      z, source_ok
        ld      hl, #RESULT_BAD
        inc     (hl)
source_ok:
        ld      de, (TIMER_LOW)
        ld      hl, #TIMER_PERIOD
        or      a
        sbc     hl, de
        push    hl
        ld      a, (RESULT_COUNT)
        add     a, a
        ld      e, a
        ld      d, #0x00
        ld      hl, #SAMPLE_BASE
        add     hl, de
        pop     de
        ld      (hl), e
        inc     hl
        ld      (hl), d
        ld      hl, #RESULT_COUNT
        inc     (hl)
        jr      nz, count_done
        inc     hl
        inc     (hl)
count_done:
        pop     iy
        pop     ix
        pop     hl
        pop     de
        pop     bc
        pop     af
        ei
        reti

read_timer_a:
read_timer_retry:
        ld      bc, #0xdc05
        in      a, (c)
        ld      d, a
        dec     c
        in      a, (c)
        ld      e, a
        inc     c
        in      a, (c)
        cp      d
        jr      nz, read_timer_retry
        ld      a, e
        ld      (TIMER_LOW), a
        ld      a, d
        ld      (TIMER_HIGH), a
        ret

        ; SDCC's linker expects the standard data area even when this probe
        ; deliberately contains no C data.
        .area   _DATA
