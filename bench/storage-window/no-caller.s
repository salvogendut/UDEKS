; SPDX-License-Identifier: GPL-3.0-or-later
; Deliberately denies OPEN. Size/link experiment, NOT a trusted task provider.
        .setcpu "6502"
        .export _udeks_storage_caller
        .segment "STORAGECODE"
_udeks_storage_caller:
        lda #0
        tax
        rts
