; SPDX-License-Identifier: GPL-3.0-or-later

        .module timer
        .globl  _bench_timer_start
        .globl  _bench_timer_elapsed

        .area   _CODE

_bench_timer_start::
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

_bench_timer_elapsed::
        xor     a
        ld      bc, #0xdc0f
        out     (c), a
        ld      bc, #0xdc06
        in      a, (c)
        cpl
        ld      e, a
        inc     c
        in      a, (c)
        cpl
        ld      d, a
        ld      bc, #0xdc0d
        in      a, (c)
        and     #0x02
        ret     z
        ld      de, #0xffff
        ret
