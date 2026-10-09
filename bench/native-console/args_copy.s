; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .include "native_args.inc"
        .import _udeks_shell_native_argc, _udeks_shell_command_line, _udeks_shell_offsets
        .export _test_copy_args
        .segment "CODE"
_test_copy_args:
        .include "native_args_copy.inc"
        rts
