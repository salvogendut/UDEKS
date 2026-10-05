; SPDX-License-Identifier: GPL-3.0-or-later
; Shared by the bank-0 page initializer and bank-1 loader.
NATIVE_CLIENTS = 4
.macro native_bases
        .byte $23,$35,$80,$c6
.endmacro
.macro native_limits
        .byte $35,$40,$90,$d0
.endmacro
.macro native_stacks
        .byte $34,$3f,$8f,$cf
.endmacro
.macro native_zero_pages
        .byte $d5,$d7,$d0,$00
.endmacro
.macro native_hardware_pages
        .byte $d6,$d8,$e2,$01
.endmacro
