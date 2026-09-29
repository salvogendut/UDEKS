; SPDX-License-Identifier: GPL-3.0-or-later
        .setcpu "6502"
        .import _repaint_dispatch, _udeks_repaint_lane
        .importzp sp, sreg, regsave, ptr1, ptr2, ptr3, ptr4
        .importzp tmp1, tmp2, tmp3, tmp4, regbank
        .segment "ENTRY"
entry:  jmp _repaint_dispatch
        .assert entry = $d100, lderror, "repaint dispatch moved"
        .assert _udeks_repaint_lane = $dfe0, lderror, "bank-owned lane moved"
        .assert sp = $06, lderror, "sp moved"
        .assert sreg = $08, lderror, "sreg moved"
        .assert regsave = $0a, lderror, "regsave moved"
        .assert ptr1 = $0e, lderror, "ptr1 moved"
        .assert ptr2 = $10, lderror, "ptr2 moved"
        .assert ptr3 = $12, lderror, "ptr3 moved"
        .assert ptr4 = $14, lderror, "ptr4 moved"
        .assert tmp1 = $16, lderror, "tmp1 moved"
        .assert tmp2 = $17, lderror, "tmp2 moved"
        .assert tmp3 = $18, lderror, "tmp3 moved"
        .assert tmp4 = $19, lderror, "tmp4 moved"
        .assert regbank = $1a, lderror, "regbank moved"
