; SPDX-License-Identifier: GPL-3.0-or-later
;
; Task-context save/restore benchmark for the Z80 and SDCC runtime.

        .module context_z80
        .globl  _start

RESULT              = 0xf180
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

CONTEXT_SP          = 0xf158
ITER_COUNT          = 0xf15a
CUR_SAMPLE          = 0xf15b
TICK_LOW            = 0xf15c
TICK_HIGH           = 0xf15d

VARIANT_COUNT       = 4
SAMPLES_PER_VARIANT = 8
ITERATIONS          = 64
CORE_BYTES          = 16    ; return PC, AF/BC/DE/HL/IX/IY frame, saved SP
COMPILER_BYTES      = 16    ; SDCC has no task-local pseudo-register block
FULL_BYTES          = 24    ; compiler state plus AF'/BC'/DE'/HL'

        .area   _CODE
_start::
        di
        ld      sp, #0xeff0

        xor     a
        ld      hl, #RESULT
        ld      (hl), a
        ld      de, #(RESULT + 1)
        ld      bc, #127
        ldir

        ld      a, #'C'
        ld      (RESULT + 0), a
        ld      a, #'T'
        ld      (RESULT + 1), a
        ld      a, #'X'
        ld      (RESULT + 2), a
        ld      a, #'B'
        ld      (RESULT + 3), a
        ld      a, #0x01
        ld      (RESULT + 4), a
        ld      a, #0x02
        ld      (RESULT + 5), a
        ld      a, #0x01
        ld      (RESULT_STATE), a
        ld      a, #VARIANT_COUNT
        ld      (RESULT_VARIANTS), a
        ld      a, #SAMPLES_PER_VARIANT
        ld      (RESULT_SAMPLES), a
        ld      a, #ITERATIONS
        ld      (RESULT_ITERATIONS), a
        xor     a
        ld      (RESULT_ITERATIONS + 1), a
        ld      a, #CORE_BYTES
        ld      (RESULT_CORE_BYTES), a
        ld      a, #COMPILER_BYTES
        ld      (RESULT_COMP_BYTES), a
        ld      a, #FULL_BYTES
        ld      (RESULT_FULL_BYTES), a

        call    qualify_core
        call    qualify_full
        ld      a, (RESULT_BAD)
        or      a
        jp      nz, failed

        ld      hl, #empty_context
        ld      (benchmark_call + 1), hl
        ld      hl, #EMPTY_BASE
        ld      (store_tick + 1), hl
        call    run_variant

        ld      hl, #context_core
        ld      (benchmark_call + 1), hl
        ld      hl, #CORE_BASE
        ld      (store_tick + 1), hl
        call    run_variant

        ; SDCC's compiler-complete state is the primary register set and stack.
        ld      hl, #context_compiler
        ld      (benchmark_call + 1), hl
        ld      hl, #COMPILER_BASE
        ld      (store_tick + 1), hl
        call    run_variant

        ld      hl, #context_full
        ld      (benchmark_call + 1), hl
        ld      hl, #FULL_BASE
        ld      (store_tick + 1), hl
        call    run_variant

        ld      a, #0x02
        ld      (RESULT_STATE), a
halt:
        jr      halt

failed:
        ld      a, #0xff
        ld      (RESULT_STATE), a
        jr      halt

run_variant:
        xor     a
        ld      (CUR_SAMPLE), a
next_sample:
        call    timer_start
        ld      a, #ITERATIONS
        ld      (ITER_COUNT), a
timed_loop:
benchmark_call:
        call    empty_context
        ld      hl, #ITER_COUNT
        dec     (hl)
        jr      nz, timed_loop
        call    timer_elapsed
        ld      a, e
        ld      (TICK_LOW), a
        ld      a, d
        ld      (TICK_HIGH), a
        ld      a, e
        and     d
        inc     a
        jr      nz, tick_valid
        ld      hl, #RESULT_BAD
        inc     (hl)
tick_valid:
        ld      a, (CUR_SAMPLE)
        add     a, a
        ld      e, a
        ld      d, #0x00
store_tick:
        ld      hl, #EMPTY_BASE
        add     hl, de
        ld      a, (TICK_LOW)
        ld      (hl), a
        inc     hl
        ld      a, (TICK_HIGH)
        ld      (hl), a
        ld      hl, #CUR_SAMPLE
        inc     (hl)
        ld      a, (hl)
        cp      #SAMPLES_PER_VARIANT
        jr      c, next_sample
        ret

empty_context:
        ret

; SDCC compiler-visible state: primary AF/BC/DE/HL, IX, IY, call-stacked PC,
; and the saved hardware SP. I, R, IFF, and IM are kernel-global policy.
context_core:
context_compiler:
        push    af
        push    bc
        push    de
        push    hl
        push    ix
        push    iy
        ld      (CONTEXT_SP), sp
        ld      sp, (CONTEXT_SP)
        pop     iy
        pop     ix
        pop     hl
        pop     de
        pop     bc
        pop     af
        ret

; Full UDEKS application context additionally admits the alternate register
; bank. Refresh state and interrupt mode remain kernel-owned.
context_full:
        push    af
        push    bc
        push    de
        push    hl
        push    ix
        push    iy
        exx
        push    bc
        push    de
        push    hl
        ex      af, af'
        push    af
        ld      (CONTEXT_SP), sp
        ld      sp, (CONTEXT_SP)
        pop     af
        ex      af, af'
        pop     hl
        pop     de
        pop     bc
        exx
        pop     iy
        pop     ix
        pop     hl
        pop     de
        pop     bc
        pop     af
        ret

qualify_core:
        ld      a, #0xa5
        ld      bc, #0x1234
        ld      de, #0x5678
        ld      hl, #0x9abc
        ld      ix, #0x1357
        ld      iy, #0x2468
        scf
        call    context_core
        jp      nc, qualification_failed
        cp      #0xa5
        jp      nz, qualification_failed
        ld      a, b
        cp      #0x12
        jp      nz, qualification_failed
        ld      a, c
        cp      #0x34
        jp      nz, qualification_failed
        ld      a, d
        cp      #0x56
        jp      nz, qualification_failed
        ld      a, e
        cp      #0x78
        jp      nz, qualification_failed
        ld      a, h
        cp      #0x9a
        jp      nz, qualification_failed
        ld      a, l
        cp      #0xbc
        jp      nz, qualification_failed
        push    ix
        pop     hl
        ld      a, h
        cp      #0x13
        jp      nz, qualification_failed
        ld      a, l
        cp      #0x57
        jp      nz, qualification_failed
        push    iy
        pop     hl
        ld      a, h
        cp      #0x24
        jp      nz, qualification_failed
        ld      a, l
        cp      #0x68
        jp      nz, qualification_failed
        ret

qualify_full:
        ld      bc, #0x1234
        ld      de, #0x5678
        ld      hl, #0x9abc
        ld      ix, #0x1357
        ld      iy, #0x2468
        exx
        ld      bc, #0xa1b2
        ld      de, #0xc3d4
        ld      hl, #0xe5f6
        exx
        ld      a, #0x5a
        ex      af, af'
        ld      a, #0xa5
        ex      af, af'
        scf
        call    context_full
        jr      nc, qualification_failed
        ex      af, af'
        cp      #0xa5
        jr      nz, qualification_failed
        ex      af, af'
        cp      #0x5a
        jr      nz, qualification_failed
        exx
        ld      a, b
        cp      #0xa1
        jr      nz, qualification_failed_alt
        ld      a, c
        cp      #0xb2
        jr      nz, qualification_failed_alt
        ld      a, d
        cp      #0xc3
        jr      nz, qualification_failed_alt
        ld      a, e
        cp      #0xd4
        jr      nz, qualification_failed_alt
        ld      a, h
        cp      #0xe5
        jr      nz, qualification_failed_alt
        ld      a, l
        cp      #0xf6
        jr      nz, qualification_failed_alt
        exx
        ret
qualification_failed_alt:
        exx
qualification_failed:
        ld      hl, #RESULT_BAD
        inc     (hl)
        ret

timer_start:
        ld      bc, #0xdc0d
        in      a, (c)
        xor     a
        ld      bc, #0xdc0f
        out     (c), a
        ld      a, #0xff
        ld      bc, #0xdc06
        out     (c), a
        inc     c
        out     (c), a
        ld      a, #0x11
        ld      bc, #0xdc0f
        out     (c), a
        ret

timer_elapsed:
        ld      bc, #0xdc06
        in      a, (c)
        cpl
        ld      e, a
        inc     c
        in      a, (c)
        cpl
        ld      d, a
        xor     a
        ld      bc, #0xdc0f
        out     (c), a
        ld      bc, #0xdc0d
        in      a, (c)
        and     #0x02
        ret     z
        ld      de, #0xffff
        ret

        .area   _DATA
