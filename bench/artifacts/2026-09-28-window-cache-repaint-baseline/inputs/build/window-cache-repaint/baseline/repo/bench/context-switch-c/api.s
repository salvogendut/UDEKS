; SPDX-License-Identifier: GPL-3.0-or-later

        .setcpu "6502"
        .importzp sp
        .export _compiled_context_yield

        .assert sp = $02, lderror, "compiled-context cc65 sp moved"

        .segment "CODE"
_compiled_context_yield:
        jmp $f403
