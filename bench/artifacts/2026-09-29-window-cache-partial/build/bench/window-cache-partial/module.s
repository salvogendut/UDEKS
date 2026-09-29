; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .include "layout.inc"
        .importzp sp, sreg, regsave, regbank, ptr1, ptr2, ptr3, ptr4
        .importzp tmp1, tmp2, tmp3, tmp4
        .assert sp = $06, error, "private runtime sp moved"
        .assert sreg = $08, error, "private runtime sreg moved"
        .assert regsave = $0a, error, "private runtime regsave moved"
        .assert ptr1 = $0e, error, "private runtime ptr1 moved"
        .assert ptr2 = $10, error, "private runtime ptr2 moved"
        .assert ptr3 = $12, error, "private runtime ptr3 moved"
        .assert ptr4 = $14, error, "private runtime ptr4 moved"
        .assert tmp1 = $16, error, "private runtime tmp1 moved"
        .assert tmp2 = $17, error, "private runtime tmp2 moved"
        .assert tmp3 = $18, error, "private runtime tmp3 moved"
        .assert tmp4 = $19, error, "private runtime tmp4 moved"
        .assert regbank = $1a, error, "private runtime regbank moved"
        .import _udeks_cache_controller, core_start
        .export _udeks_cache_overlay_row, command_entry
        .segment "DISPATCH"
command_entry:
        jmp _udeks_cache_controller
        .assert command_entry = DISPATCH, error, "command entry moved"
        .segment "CODE"
_udeks_cache_overlay_row:
        jmp core_start
        .segment "PRIVATESTATE"
lease_state: .res 13
row_state: .res 9
flow_state: .res 4
        .assert lease_state = LEASE, error, "command lease moved"
        .assert row_state = ROW, error, "command row moved"
        .assert * <= STACK_BOTTOM, error, "state reaches software stack"

        .assert flow_state = FLOW, error, "flow state moved"
