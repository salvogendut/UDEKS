; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .import _udeks_graphical_main
        .export _udeks_program_entry
        .segment "STARTUP"
_udeks_program_entry:
        jmp _udeks_graphical_main
