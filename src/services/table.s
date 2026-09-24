; SPDX-License-Identifier: GPL-3.0-or-later
;
; Static bring-up registry. Later loadable modules feed the same descriptor ABI
; into the registry without changing its validation or lifecycle semantics.

        .setcpu "6502"
        .import _udeks_capability_service_descriptor
        .import _udeks_time_service_descriptor
        .import _udeks_z80_worker_service_descriptor
        .import _udeks_console_service_descriptor
        .import _udeks_pointer_service_descriptor
        .import _udeks_vic_graphics_service_descriptor
        .import _udeks_window_service_descriptor
        .import _udeks_xclock_service_descriptor
        .import _udeks_xwave_service_descriptor
        .import _udeks_keyboard_service_descriptor
        .import _udeks_root_terminal_service_descriptor
        .import _udeks_shell_service_descriptor
        .export _udeks_service_table
        .export _udeks_service_count

        .segment "RODATA"
_udeks_service_table:
        .addr _udeks_capability_service_descriptor
        .addr _udeks_time_service_descriptor
        .addr _udeks_z80_worker_service_descriptor
        .addr _udeks_console_service_descriptor
        .addr _udeks_pointer_service_descriptor
        .addr _udeks_vic_graphics_service_descriptor
        .addr _udeks_window_service_descriptor
        .addr _udeks_keyboard_service_descriptor
        .addr _udeks_root_terminal_service_descriptor
        .addr _udeks_shell_service_descriptor
        .addr _udeks_xclock_service_descriptor
        .addr _udeks_xwave_service_descriptor
_udeks_service_count:
        .byte $0c
