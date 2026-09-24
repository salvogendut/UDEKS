; SPDX-License-Identifier: GPL-3.0-or-later

        .export _bench_timer_start, _bench_timer_elapsed

CIA1_TB_LO = $dc06
CIA1_TB_HI = $dc07
CIA1_ICR   = $dc0d
CIA1_CRB   = $dc0f

        .segment "CODE"

_bench_timer_start:
        lda CIA1_ICR
        lda #$00
        sta CIA1_CRB
        lda #$ff
        sta CIA1_TB_LO
        sta CIA1_TB_HI
        lda #$11
        sta CIA1_CRB
        rts

_bench_timer_elapsed:
        lda CIA1_TB_LO
        eor #$ff
        pha
        lda CIA1_TB_HI
        eor #$ff
        tax
        lda CIA1_ICR
        and #$02
        bne overflow
        pla
        rts

overflow:
        pla
        lda #$ff
        tax
        rts
