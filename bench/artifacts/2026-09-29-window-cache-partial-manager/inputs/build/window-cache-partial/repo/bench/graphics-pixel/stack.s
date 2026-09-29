; SPDX-License-Identifier: GPL-3.0-or-later
; Diagnostic only, not part of the measured production mechanism.
        .setcpu "6502"
        .importzp sp
        .export _pixel_probe_sp
        .segment "CODE"
_pixel_probe_sp:
        lda sp
        ldx sp+1
        rts
