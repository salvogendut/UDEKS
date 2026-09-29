; SPDX-License-Identifier: GPL-3.0-or-later

        .module kernel_crt0_z80
        .globl  _z80_main

        .area   _CODE
_start::
        di
        ld      sp, #0xeff0
        call    _z80_main
halt:
        di
        jp      halt
