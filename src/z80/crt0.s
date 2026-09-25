; SPDX-License-Identifier: GPL-3.0-or-later
;
; SDAS syntax. This object must be linked first so _start is at code-loc.

        .module crt0
        .globl  _z80_main

        .area   _CODE
_start::
        di
        ; The worker is suspended between leases while bank-1 ush runs. Keep
        ; its live call frames in reserved common RAM so neither the task nor
        ; an MMU profile change can replace the underlying stack storage.
        ld      sp, #0xf300
        call    _z80_main

halt:
        di
        jp      halt
