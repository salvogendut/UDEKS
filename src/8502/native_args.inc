; SPDX-License-Identifier: GPL-3.0-or-later
; UARG 0.1: logical addresses in each native task's relocated page zero.
NATIVE_ARGS_BASE = $80
NATIVE_ARGS_MAJOR = $84
NATIVE_ARGS_MINOR = $85
NATIVE_ARGS_COUNT = $86
NATIVE_ARGS_VECTOR = $88
NATIVE_ARGS_TEXT = $9a
NATIVE_ARGS_MAX = 8
NATIVE_ARGS_TEXT_SIZE = 55
        .assert NATIVE_ARGS_VECTOR+2*(NATIVE_ARGS_MAX+1) = NATIVE_ARGS_TEXT, error, "UARG vector size"
        .assert NATIVE_ARGS_TEXT+NATIVE_ARGS_TEXT_SIZE <= $100, error, "UARG leaves private ZP"
