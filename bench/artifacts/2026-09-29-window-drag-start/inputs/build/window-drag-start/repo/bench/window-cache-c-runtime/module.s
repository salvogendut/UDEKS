; SPDX-License-Identifier: GPL-3.0-or-later
; Six bounded C calls, no polling/callback/yield while bank 1 is mapped.
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
        .import _udeks_cache_init, _udeks_cache_invalidate
        .import _udeks_cache_capture_begin, _udeks_cache_paste_begin
        .import _udeks_cache_prepare_row, _udeks_cache_commit_row
        .export policy_dispatch, policy_dispatch_end
        .segment "DISPATCH"
policy_dispatch:
        lda OP
        cmp #$06
        bcs bad_operation
        tax
        lda counts,x
        sta argument_count+1
        txa
        asl a
        tax
        lda functions,x
        sta invoke+1
        lda functions+1,x
        sta invoke+2
        ldx #$05
copy_geometry:
        lda INPUT_GEOMETRY,x
        sta GEOMETRY,x
        dex
        bpl copy_geometry
        ; Copy the exact ordinary cc65 stacked arguments into private RAM.
        ; Last/rightmost argument is passed in A/X by the calling convention.
        sec
        lda #<STACK_TOP
argument_count:
        sbc #$ff
        sta sp
        ldy argument_count+1
        dey
copy_arguments:
        lda ARGS,y
        sta (sp),y
        dey
        bpl copy_arguments
        lda LAST_A
        ldx LAST_X
invoke:
        jsr $ffff
        sta RESULT
        ldx #$0c
copy_lease:
        lda LEASE,x
        sta OUTPUT_LEASE,x
        dex
        bpl copy_lease
        ldx #$08
copy_row:
        lda ROW,x
        sta OUTPUT_ROW,x
        dex
        bpl copy_row
        rts
bad_operation:
        lda #$01
        sta RESULT
        rts
counts: .byte 2,2,7,5,5,5
functions:
        .word _udeks_cache_init, _udeks_cache_invalidate
        .word _udeks_cache_capture_begin, _udeks_cache_paste_begin
        .word _udeks_cache_prepare_row, _udeks_cache_commit_row
policy_dispatch_end:
        .assert policy_dispatch = DISPATCH, error, "private dispatcher moved"
        .assert sp = ZP_FIRST, error, "private C stack symbol moved"
        .segment "PRIVATESTATE"
lease_state: .res 13
geometry_state: .res 6
row_state: .res 9
        .assert lease_state = LEASE, error, "private lease moved"
        .assert geometry_state = GEOMETRY, error, "private geometry moved"
        .assert row_state = ROW, error, "private row moved"
        .assert * <= STACK_BOTTOM, error, "private state reaches C stack"
