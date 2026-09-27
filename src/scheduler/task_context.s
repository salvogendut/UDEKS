; SPDX-License-Identifier: GPL-3.0-or-later
;
; Bank-0 context records and callbacks for the common-RAM switch tail. The
; initial record describes persistent /bin/ush; later SPAWN work allocates the
; remaining records through the same private table.

        .setcpu "6502"
        .include "task_switch_context.inc"

        .export _udeks_task_context_reset
        .export _udeks_task_context_select
        .export _udeks_task_context_save_current
        .export _udeks_task_contexts_private
        .export _udeks_task_context_current_private
        .import _udeks_lifecycle_apply
        .import _udeks_scheduler_select_next
        .import _udeks_task_wait_publish_current
        .import _udeks_task_wait_reset
        .import decsp2
        .importzp ptr1, sp

MMU_PAGE0_PAGE          = $d507
MMU_PAGE0_BANK          = $d508
MMU_PAGE1_PAGE          = $d509
MMU_PAGE1_BANK          = $d50a

TASK_COUNT              = $08
TASK_CONTEXT_SIZE       = TASK_SWITCH_CONTEXT_SIZE
TASK_ENTRY              = $9000
TASK_SOFT_STACK         = $eff0
; $80-$89 back the transient APP1 save area. Task 1 instead owns the first two
; pages above bootfs ($A000-$D0FF), which are dead after native boot.
TASK_PAGE0              = $d1
TASK_PAGE1              = $d2
TASK_PAGE_BANK          = $01
TASK_STACK_CANARY       = $a5

LIFECYCLE_DISPATCH      = $03

        .segment "CODE"

; Initialize task 1 and its relocated page zero/page one. Interrupts are
; already masked by the common tail; restore the kernel mapping before RTS.
_udeks_task_context_reset:
        jsr _udeks_task_wait_reset
        lda #$00
        ldx #(TASK_COUNT * TASK_CONTEXT_SIZE)-1
clear_contexts:
        sta task_contexts,x
        dex
        bpl clear_contexts
        lda #$81
        sta current_task

        lda #$24
        sta task_contexts+TASK_CTX_P
        lda #$ff
        sta task_contexts+TASK_CTX_SP
        lda #<TASK_ENTRY
        sta task_contexts+TASK_CTX_PC_LO
        lda #>TASK_ENTRY
        sta task_contexts+TASK_CTX_PC_HI
        lda #TASK_PAGE0
        sta task_contexts+TASK_CTX_PAGE0_PAGE
        lda #TASK_PAGE_BANK
        sta task_contexts+TASK_CTX_PAGE0_BANK
        sta task_contexts+TASK_CTX_PAGE1_BANK
        lda #TASK_PAGE1
        sta task_contexts+TASK_CTX_PAGE1_PAGE

        lda #TASK_PAGE_BANK
        sta MMU_PAGE0_BANK
        sta MMU_PAGE1_BANK
        lda #TASK_PAGE0
        sta MMU_PAGE0_PAGE
        lda #TASK_PAGE1
        sta MMU_PAGE1_PAGE
        ldy #$00
        tya
clear_task_pages:
        sta $0000,y
        sta $0100,y
        iny
        bne clear_task_pages
        lda #<TASK_SOFT_STACK
        sta $02
        lda #>TASK_SOFT_STACK
        sta $03
        lda #TASK_STACK_CANARY
        sta $0100

        lda #$00
        sta MMU_PAGE0_BANK
        sta MMU_PAGE1_BANK
        sta MMU_PAGE0_PAGE
        lda #$01
        sta MMU_PAGE1_PAGE
        lda #$00
        rts

; Return a selected task id in A and copy its record into common RAM. The
; lifecycle bootstrap has already dispatched the first shell entry; later
; selections perform the normal RUNNABLE -> RUNNING transition here.
_udeks_task_context_select:
        lda current_task
        bpl select_runnable
        and #$7f
        sta current_task
        bne load_selected
select_runnable:
        lda current_task
        jsr _udeks_scheduler_select_next
        beq no_selected_task
        sta current_task
        jsr decsp2
        lda current_task
        ldy #$01
        sta (sp),y
        lda #LIFECYCLE_DISPATCH
        dey
        sta (sp),y
        tya
        jsr _udeks_lifecycle_apply
        bne no_selected_task
load_selected:
        jsr _udeks_task_wait_publish_current
        lda current_task
        jsr context_pointer
        ldy #TASK_CONTEXT_SIZE-1
copy_context_in:
        lda (ptr1),y
        sta TASK_SWITCH_CONTEXT,y
        dey
        bpl copy_context_in
        lda current_task
        rts
no_selected_task:
        lda #$00
        rts

; Called by the lifecycle request handler before it changes RUNNING state.
; The common tail has already captured the outgoing CPU/MMU context.
_udeks_task_context_save_current:
        lda current_task
        beq context_saved
        jsr context_pointer
        ldy #TASK_CONTEXT_SIZE-1
copy_context_out:
        lda TASK_SWITCH_CONTEXT,y
        sta (ptr1),y
        dey
        bpl copy_context_out
context_saved:
        rts

; A is a one-based task id. Return its record address in ptr1.
context_pointer:
        sec
        sbc #$01
        tax
        lda context_offsets,x
        clc
        adc #<task_contexts
        sta ptr1
        lda #>task_contexts
        adc #$00
        sta ptr1+1
        rts

        .segment "RODATA"
context_offsets:
        .byte $00, $0b, $16, $21, $2c, $37, $42, $4d

        .segment "BSS"
_udeks_task_contexts_private:
task_contexts:          .res TASK_COUNT * TASK_CONTEXT_SIZE
_udeks_task_context_current_private:
current_task:           .res 1
