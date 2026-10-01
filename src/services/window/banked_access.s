; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .export _udeks_banked_call, _udeks_banked_read, _udeks_banked_write
        .segment "CODE"
_udeks_banked_call:
        jmp $f91c
_udeks_banked_read:
        ldy #$20
        bne transfer
_udeks_banked_write:
        ldy #$21
transfer:
        sta $f367
        stx $f368
        tya
        jmp $f91c
