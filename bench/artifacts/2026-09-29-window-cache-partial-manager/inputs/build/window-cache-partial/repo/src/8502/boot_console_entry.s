; SPDX-License-Identifier: GPL-3.0-or-later
;
; Public resident binding for the boot-only console composer. The actual C
; image is installed at $1600 before crt0 and remains live only through the
; initial service-start pass.

        .setcpu "6502"
        .export _udeks_boot_console_build

_udeks_boot_console_build = $1600
