; SPDX-License-Identifier: GPL-3.0-or-later
        .importzp sp
        .export _rectangle_sp
        .segment "CODE"
_rectangle_sp:
        lda sp
        ldx sp+1
        rts
