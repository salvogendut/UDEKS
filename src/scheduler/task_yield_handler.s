; SPDX-License-Identifier: GPL-3.0-or-later
;
; Post-startup lifecycle request handler in the permanent scheduler tail. The
; common switch tail has already captured the task CPU/MMU context before
; entering here. Carry set suspends the caller; carry clear resumes a rejected
; request synchronously.

        .setcpu "6502"

        .export _udeks_task_yield_handler
        .import _udeks_task_sleep_poll
        .import _udeks_task_tick_advance
        .import _udeks_task_cancel_request
        .import _udeks_task_poll_request
        .import _udeks_task_console_get_line
        .import _udeks_task_context_save_current
        .import _udeks_task_contexts_private
        .import _udeks_lifecycle_slots_private
        .import _udeks_lifecycle_current_private
        .import _udeks_lifecycle_last_event_private
        .import _udeks_lifecycle_rejected_private
        .import _udeks_task_wait_state_private
        .import _udeks_task_wait_operation_private
        .import _udeks_task_wait_sequence_private
        .import _udeks_task_wait_descriptor_private
        .import _udeks_task_wait_count_private
        .import _udeks_task_wait_flags_private
        .import _udeks_task_wait_selector_private
        .import _udeks_task_wait_selector_high_private
        .import _udeks_task_wait_child_private
        .import _udeks_task_wait_status_private
        .import _udeks_monotonic_ticks_low
        .import _udeks_monotonic_ticks_high
        .import _udeks_bootfs_finish_error
        .import _udeks_bootfs_finish_ok

TREQ_BASE               = $f359
TREQ_STATE              = TREQ_BASE+$06
TREQ_OPERATION          = TREQ_BASE+$07
TREQ_SEQUENCE           = TREQ_BASE+$08
TREQ_DESCRIPTOR         = TREQ_BASE+$09
TREQ_COUNT              = TREQ_BASE+$0a
TREQ_RESULT             = TREQ_BASE+$0b
TREQ_ERROR              = TREQ_BASE+$0c
TREQ_FLAGS              = TREQ_BASE+$0d
TREQ_PAYLOAD             = TREQ_BASE+$0e
TASK_STATUS             = $f280
TASK_ERROR              = TASK_STATUS+$06
TASK_HEADER             = TASK_STATUS+$10
SPAWN_LOADER            = $f919
TASK_REQUEST_GATE       = $ff16

MMU_PAGE0_PAGE          = $d507
MMU_PAGE0_BANK          = $d508
MMU_PAGE1_PAGE          = $d509
MMU_PAGE1_BANK          = $d50a

TREQ_IDLE               = $00
TREQ_COMPLETE           = $02
ERR_EINVAL              = $16
ERR_ENOSYS              = $26
ERR_ENOENT              = $02
ERR_EIO                 = $05
ERR_ENOEXEC             = $08
ERR_ENOMEM              = $0c

OP_YIELD                = $0a
OP_EXIT                 = $0b
OP_WAITPID              = $0c
OP_SLEEP                = $0d
OP_CANCEL               = $0e
OP_SPAWN                = $0f
WAITPID_NOHANG          = $01
TASK_SLOT_STRIDE        = $08
TASK_SLOT_PARENT        = $00
TASK_SLOT_STATE         = $01
TASK_SLOT_WAIT          = $02
TASK_SLOT_FLAGS         = $03
TASK_SLOT_EXIT          = $04
TASK_SLOT_RESUME        = $06
TASK_SLOT_TABLE_SIZE    = $40
TASK_STATE_FREE         = $00
TASK_STATE_RUNNABLE     = $02
TASK_STATE_RUNNING      = $03
TASK_STATE_WAITING      = $04
TASK_STATE_ZOMBIE       = $06
LIFECYCLE_YIELD         = $04
LIFECYCLE_BLOCK         = $05
LIFECYCLE_EXIT          = $09
LIFECYCLE_REAP          = $0a
LIFECYCLE_ADMIT         = $02
WAIT_CHILD              = $01
WAIT_TIMER              = $03
WAIT_BLOCKED            = $01
WAIT_READY              = $02
ERR_ECHILD              = $0a

TASK_CONTEXT_SIZE       = $0b
TASK2_CONTEXT           = _udeks_task_contexts_private+TASK_CONTEXT_SIZE
TASK_CTX_P              = $03
TASK_CTX_SP             = $04
TASK_CTX_PC_LO          = $05
TASK_CTX_PC_HI          = $06
TASK_CTX_PAGE0_PAGE     = $07
TASK_CTX_PAGE0_BANK     = $08
TASK_CTX_PAGE1_PAGE     = $09
TASK_CTX_PAGE1_BANK     = $0a
TASK2_PAGE0             = $d3
TASK2_PAGE1             = $d4
TASK2_PAGE_BANK         = $01
TASK2_STACK_BOTTOM      = $0c00
TASK2_STACK_TOP         = $1200
TASK2_LAUNCHER          = TASK_STATUS
TASK2_STACK_CANARY      = $a5
TASK2_INITIAL_SP        = $ff
TASK_FLAG_USER          = $01
TASK_LOADER_NOT_FOUND   = $0b
TASK_LOADER_BAD_BOOTFS  = $0c
TASK_LOADER_BAD_SIZE    = $09

        .segment "YIELDHANDLER"

_udeks_task_yield_handler:
        jmp lifecycle_request
task_sleep_poll_gate:
        jmp _udeks_task_sleep_poll
task_tick_advance_gate:
        jmp _udeks_task_tick_advance
task_wait_snapshot_gate:
        jmp wait_snapshot
task_block_caller_gate:
        jmp block_caller
task_console_get_line_gate:
        jmp _udeks_task_console_get_line

lifecycle_request:
        lda TREQ_OPERATION
        cmp #$10
        bne :+
        jmp _udeks_task_poll_request
:
        lda TREQ_DESCRIPTOR
        beq :+
        jmp yield_invalid
:

        lda TREQ_OPERATION
        cmp #OP_YIELD
        bne :+
        jmp request_yield
:
        cmp #OP_EXIT
        bne :+
        jmp request_exit
:
        cmp #OP_WAITPID
        bne :+
        jmp request_waitpid
:
        cmp #OP_SLEEP
        bne :+
        jmp request_sleep
:
        cmp #OP_CANCEL
        bne :+
        jmp _udeks_task_cancel_request
:
        cmp #OP_SPAWN
        bne :+
        jmp request_spawn
:
        lda #ERR_ENOSYS
        jmp _udeks_bootfs_finish_error

request_spawn:
        lda TREQ_FLAGS
        beq :+
        jmp yield_invalid
:
        lda TREQ_COUNT
        cmp #$11
        beq :+
        jmp yield_invalid
:
        jsr current_slot
        beq :+
        jmp yield_invalid
:
        lda TREQ_PAYLOAD
        beq spawn_invalid
        cmp #$11
        bcc :+
spawn_invalid:
        jmp yield_invalid
:
        tax
        ldy #$01
spawn_validate_name:
        lda TREQ_PAYLOAD,y
        cmp #'.'
        beq spawn_name_valid
        cmp #'_'
        beq spawn_name_valid
        cmp #'+'
        beq spawn_name_valid
        cmp #'-'
        beq spawn_name_valid
        cmp #'0'
        bcc spawn_invalid
        cmp #'9'+1
        bcc spawn_name_valid
        cmp #'A'
        bcc spawn_invalid
        cmp #'Z'+1
        bcc spawn_name_valid
        cmp #'a'
        bcc spawn_invalid
        cmp #'z'+1
        bcs spawn_invalid
spawn_name_valid:
        iny
        dex
        bne spawn_validate_name
spawn_validate_padding:
        cpy #$11
        beq spawn_request_valid
        lda TREQ_PAYLOAD,y
        bne spawn_invalid
        iny
        bne spawn_validate_padding

spawn_request_valid:
        ; APP1 is the only ordinary-task allocation in Tasking 0.1, so task 2
        ; owns it exclusively until EXIT/WAITPID reaps the slot.
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STRIDE+TASK_SLOT_STATE
        beq :+
        lda #ERR_ENOMEM
        jmp _udeks_bootfs_finish_error
:
        ; Length 16 has no in-count pad byte. Supply the private loader's
        ; required terminator only after the entire request has validated.
        lda #$00
        sta TREQ_PAYLOAD+$11
        lda #<(TREQ_PAYLOAD+$01)
        ldx #>(TREQ_PAYLOAD+$01)
        jsr SPAWN_LOADER
        beq spawn_loaded
        lda TASK_ERROR
        cmp #TASK_LOADER_NOT_FOUND
        beq spawn_not_found
        cmp #TASK_LOADER_BAD_BOOTFS
        beq spawn_io_error
        cmp #TASK_LOADER_BAD_SIZE
        bne spawn_bad_executable
        ; Distinguish a valid image that cannot fit APP1 from malformed size
        ; metadata. The common loader has already checked header/file parity.
        lda TASK_HEADER+$0a
        ora TASK_HEADER+$0b
        beq spawn_bad_executable
        clc
        lda TASK_HEADER+$0a
        adc TASK_HEADER+$0c
        lda TASK_HEADER+$0b
        adc TASK_HEADER+$0d
        cmp #$0a
        bcc spawn_bad_executable
        bne spawn_no_memory
        lda TASK_HEADER+$0a
        clc
        adc TASK_HEADER+$0c
        beq spawn_bad_executable
spawn_no_memory:
        lda #ERR_ENOMEM
        jmp _udeks_bootfs_finish_error
spawn_not_found:
        lda #ERR_ENOENT
        jmp _udeks_bootfs_finish_error
spawn_io_error:
        lda #ERR_EIO
        jmp _udeks_bootfs_finish_error
spawn_bad_executable:
        lda #ERR_ENOEXEC
        jmp _udeks_bootfs_finish_error

spawn_loaded:
        ; Prepare the private task record before its lifecycle slot becomes
        ; visible. The common launcher receives the validated UDEX entry.
        lda #$00
        ldx #TASK_CONTEXT_SIZE-1
spawn_clear_context:
        sta TASK2_CONTEXT,x
        dex
        bpl spawn_clear_context
        lda #$24
        sta TASK2_CONTEXT+TASK_CTX_P
        lda #TASK2_INITIAL_SP
        sta TASK2_CONTEXT+TASK_CTX_SP
        lda TASK_HEADER+$0e
        sta TASK2_CONTEXT+TASK_CTX_PC_LO
        lda TASK_HEADER+$0f
        sta TASK2_CONTEXT+TASK_CTX_PC_HI
        lda #TASK2_PAGE0
        sta TASK2_CONTEXT+TASK_CTX_PAGE0_PAGE
        lda #TASK2_PAGE_BANK
        sta TASK2_CONTEXT+TASK_CTX_PAGE0_BANK
        sta TASK2_CONTEXT+TASK_CTX_PAGE1_BANK
        lda #TASK2_PAGE1
        sta TASK2_CONTEXT+TASK_CTX_PAGE1_PAGE

        ; No JSR, push, pull, or zero-page access is permitted until the
        ; kernel page mappings are restored below.
        lda #TASK2_PAGE_BANK
        sta MMU_PAGE0_BANK
        sta MMU_PAGE1_BANK
        lda #TASK2_PAGE0
        sta MMU_PAGE0_PAGE
        lda #TASK2_PAGE1
        sta MMU_PAGE1_PAGE
        ldy #$00
        tya
spawn_clear_pages:
        sta $0000,y
        sta $0100,y
        iny
        bne spawn_clear_pages
        lda #<TASK2_STACK_TOP
        sta $02
        lda #>TASK2_STACK_TOP
        sta $03
        lda #TASK2_STACK_CANARY
        sta $0100
        ; The validated header is no longer needed after its entry is copied
        ; into the launcher. Reuse the common loader-status record so this
        ; short JSR/EXIT path is visible in every MMU profile.
        ldy #spawn_return_trampoline_end-spawn_return_trampoline-1
spawn_copy_return_trampoline:
        lda spawn_return_trampoline,y
        sta TASK2_LAUNCHER,y
        dey
        bne spawn_copy_return_trampoline
        lda spawn_return_trampoline
        sta TASK2_LAUNCHER
        lda TASK2_CONTEXT+TASK_CTX_PC_LO
        sta TASK2_LAUNCHER+$01
        lda TASK2_CONTEXT+TASK_CTX_PC_HI
        sta TASK2_LAUNCHER+$02
        lda #<TASK2_LAUNCHER
        sta TASK2_CONTEXT+TASK_CTX_PC_LO
        lda #>TASK2_LAUNCHER
        sta TASK2_CONTEXT+TASK_CTX_PC_HI

        lda #$00
        sta MMU_PAGE0_BANK
        sta MMU_PAGE0_PAGE
        sta MMU_PAGE1_BANK
        lda #$01
        sta MMU_PAGE1_PAGE

        ; Slot reuse must not inherit an older blocking-request snapshot.
        lda #$00
        sta _udeks_task_wait_state_private+1
        sta _udeks_task_wait_operation_private+1
        sta _udeks_task_wait_sequence_private+1
        sta _udeks_task_wait_descriptor_private+1
        sta _udeks_task_wait_count_private+1
        sta _udeks_task_wait_flags_private+1
        sta _udeks_task_wait_selector_private+1
        sta _udeks_task_wait_selector_high_private+1
        sta _udeks_task_wait_child_private+1
        sta _udeks_task_wait_status_private+1

        ldx #TASK_SLOT_STRIDE-1
spawn_clear_slot:
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STRIDE,x
        dex
        bpl spawn_clear_slot
        lda _udeks_lifecycle_current_private
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STRIDE+TASK_SLOT_PARENT
        lda #TASK_FLAG_USER
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STRIDE+TASK_SLOT_FLAGS
        lda #LIFECYCLE_ADMIT
        sta _udeks_lifecycle_last_event_private
        ; State is the publication commit byte.
        lda #TASK_STATE_RUNNABLE
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STRIDE+TASK_SLOT_STATE
        lda #$02
        sta TREQ_PAYLOAD
        lda #$00
        sta TREQ_PAYLOAD+1
        lda #$01
        jmp _udeks_bootfs_finish_ok

; Copied over the post-load status bytes at common $F280. The entry receives
; zeroed A/X/Y; after its RTS, A contains the program's return status.
spawn_return_trampoline:
        jsr $ffff
        sta TREQ_PAYLOAD
        lda #$00
        sta TREQ_DESCRIPTOR
        sta TREQ_FLAGS
        lda #OP_EXIT
        sta TREQ_OPERATION
        lda #$01
        sta TREQ_COUNT
        sta TREQ_STATE
        jsr TASK_REQUEST_GATE
spawn_return_failed:
        jmp spawn_return_failed
spawn_return_trampoline_end:

request_sleep:
        lda TREQ_FLAGS
        beq :+
        jmp yield_invalid
:
        lda TREQ_COUNT
        cmp #$02
        beq :+
        jmp yield_invalid
:
        lda TREQ_PAYLOAD
        ora TREQ_PAYLOAD+1
        bne :+
        jmp yield_invalid
:
        lda TREQ_PAYLOAD+1
        cmp #$02
        bcc sleep_range_valid
        bne sleep_invalid
        lda TREQ_PAYLOAD
        cmp #$59
        bcc sleep_range_valid
sleep_invalid:
        jmp yield_invalid
sleep_range_valid:
        jsr current_slot
        beq :+
        jmp yield_invalid
:
        jsr wait_snapshot
        clc
        lda _udeks_monotonic_ticks_low
        adc TREQ_PAYLOAD
        sta _udeks_task_wait_selector_private,y
        lda _udeks_monotonic_ticks_high
        adc TREQ_PAYLOAD+1
        sta _udeks_task_wait_selector_high_private,y
        lda #WAIT_TIMER
        jmp block_caller

request_yield:
        lda TREQ_COUNT
        ora TREQ_FLAGS
        beq :+
        jmp yield_invalid
:
        jsr current_slot
        beq :+
        jmp yield_invalid
:
        txa
        pha
        jsr _udeks_task_context_save_current
        pla
        tax
        lda #TASK_STATE_RUNNABLE
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        lda #LIFECYCLE_YIELD
        sta _udeks_lifecycle_last_event_private
        lda #TREQ_COMPLETE
        sta TREQ_STATE
        lda #$00
        sta _udeks_lifecycle_current_private
        sta TREQ_RESULT
        sta TREQ_ERROR
        sec
        rts

request_waitpid:
        lda TREQ_COUNT
        cmp #$02
        beq :+
        jmp yield_invalid
:
        lda TREQ_FLAGS
        and #$fe
        beq :+
        jmp yield_invalid
:
        jsr current_slot
        beq :+
        jmp yield_invalid
:
        lda TREQ_PAYLOAD+1
        beq :+
        jmp wait_no_child
:
        lda TREQ_PAYLOAD
        beq wait_any_child
        cmp #$09
        bcc :+
        jmp wait_no_child
:
        cmp _udeks_lifecycle_current_private
        bne :+
        jmp wait_no_child
:
        sec
        sbc #$01
        asl a
        asl a
        asl a
        tax
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        bne :+
        jmp wait_no_child
:
        lda _udeks_lifecycle_slots_private+TASK_SLOT_PARENT,x
        cmp _udeks_lifecycle_current_private
        beq :+
        jmp wait_no_child
:
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_ZOMBIE
        bne wait_live_child
        jmp wait_reap

wait_any_child:
        ldx #$00
        ldy #$00
wait_scan:
        lda _udeks_lifecycle_slots_private+TASK_SLOT_PARENT,x
        cmp _udeks_lifecycle_current_private
        bne wait_next
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        beq wait_next
        cmp #TASK_STATE_ZOMBIE
        bne :+
        jmp wait_reap
:
        ldy #$01
wait_next:
        txa
        clc
        adc #TASK_SLOT_STRIDE
        tax
        cmp #TASK_SLOT_TABLE_SIZE
        bne wait_scan
        tya
        bne wait_live_child
        jmp wait_no_child

wait_live_child:
        lda TREQ_FLAGS
        and #WAITPID_NOHANG
        beq wait_blocking
        lda #$00
        jmp _udeks_bootfs_finish_ok

wait_blocking:
        ; Snapshot the fields required to publish this task's eventual
        ; response, then release the shared request record before sleeping.
        jsr wait_snapshot
        lda TREQ_PAYLOAD
        sta _udeks_task_wait_selector_private,y
        lda TREQ_PAYLOAD+1
        sta _udeks_task_wait_selector_high_private,y
        lda #WAIT_CHILD
        jmp block_caller

wait_reap:
        lda _udeks_lifecycle_slots_private+TASK_SLOT_EXIT,x
        sta TREQ_PAYLOAD+2
        txa
        lsr a
        lsr a
        lsr a
        clc
        adc #$01
        sta TREQ_PAYLOAD
        lda #$00
        sta TREQ_PAYLOAD+1
        sta TREQ_PAYLOAD+3
        ldy #TASK_SLOT_STRIDE
wait_clear_slot:
        sta _udeks_lifecycle_slots_private,x
        inx
        dey
        bne wait_clear_slot
        lda #LIFECYCLE_REAP
        sta _udeks_lifecycle_last_event_private
        lda #$01
        jmp _udeks_bootfs_finish_ok

wait_no_child:
        lda #ERR_ECHILD
        jmp _udeks_bootfs_finish_error

request_exit:
        lda TREQ_FLAGS
        beq :+
        jmp yield_invalid
:
        lda TREQ_COUNT
        cmp #$01
        beq :+
        jmp yield_invalid
:
        jsr current_slot
        beq :+
        jmp yield_invalid
:
        lda _udeks_lifecycle_current_private
        jsr $c883                   ; close before ZOMBIE/reap/slot reuse
        lda TREQ_PAYLOAD
        sta _udeks_lifecycle_slots_private+TASK_SLOT_EXIT,x
        lda #TASK_STATE_ZOMBIE
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        lda #LIFECYCLE_EXIT
        sta _udeks_lifecycle_last_event_private
        ; A blocked parent owns a private WAITPID snapshot. If this child
        ; matches it, move the response there, reap the child, and make the
        ; parent runnable. The shared request still belongs to this EXIT call.
        lda _udeks_lifecycle_slots_private+TASK_SLOT_PARENT,x
        beq exit_release
        sec
        sbc #$01
        tay
        lda _udeks_task_wait_state_private,y
        cmp #WAIT_BLOCKED
        bne exit_release
        lda _udeks_task_wait_selector_private,y
        beq exit_parent_slot
        cmp _udeks_lifecycle_current_private
        bne exit_release
exit_parent_slot:
        tya
        asl a
        asl a
        asl a
        tax
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_WAITING
        bne exit_release
        lda _udeks_lifecycle_slots_private+TASK_SLOT_WAIT,x
        cmp #WAIT_CHILD
        bne exit_release

        lda _udeks_lifecycle_current_private
        sta _udeks_task_wait_child_private,y
        lda TREQ_PAYLOAD
        sta _udeks_task_wait_status_private,y
        lda #WAIT_READY
        sta _udeks_task_wait_state_private,y
        lda #$00
        sta _udeks_lifecycle_slots_private+TASK_SLOT_WAIT,x
        sta _udeks_lifecycle_slots_private+TASK_SLOT_RESUME,x
        lda #TASK_STATE_RUNNABLE
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x

        lda _udeks_lifecycle_current_private
        sec
        sbc #$01
        asl a
        asl a
        asl a
        tax
        lda #$00
        ldy #TASK_SLOT_STRIDE
exit_clear_child:
        sta _udeks_lifecycle_slots_private,x
        inx
        dey
        bne exit_clear_child
        lda #LIFECYCLE_REAP
        sta _udeks_lifecycle_last_event_private
exit_release:
        ; EXIT never publishes a response to the dead caller. Release the
        ; shared record before returning to the kernel poll frame.
        lda #$00
        sta _udeks_lifecycle_current_private
        sta TREQ_STATE
        sta TREQ_RESULT
        sta TREQ_ERROR
        sec
        rts

; Return Z set and X=(current-1)*8 only for a current RUNNING task.
current_slot:
        lda _udeks_lifecycle_current_private
        beq no_current_slot
        sec
        sbc #$01
        asl a
        asl a
        asl a
        tax
        lda _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        cmp #TASK_STATE_RUNNING
        rts
no_current_slot:
        lda #$01
        rts

yield_invalid:
        inc _udeks_lifecycle_rejected_private
        lda #ERR_EINVAL
        jmp _udeks_bootfs_finish_error

; Private overlay helpers behind fixed $C909/$C90C veneers. The caller has
; completed validation. Snapshot returns Y=current-1; block receives the wait
; reason in A and never returns to the task until it is selected again.
wait_snapshot:
        lda _udeks_lifecycle_current_private
        sec
        sbc #$01
        tay
        lda TREQ_OPERATION
        sta _udeks_task_wait_operation_private,y
        lda TREQ_SEQUENCE
        sta _udeks_task_wait_sequence_private,y
        lda TREQ_DESCRIPTOR
        sta _udeks_task_wait_descriptor_private,y
        lda TREQ_COUNT
        sta _udeks_task_wait_count_private,y
        lda TREQ_FLAGS
        sta _udeks_task_wait_flags_private,y
        rts

block_caller:
        pha
        lda #WAIT_BLOCKED
        sta _udeks_task_wait_state_private,y
        jsr _udeks_task_context_save_current
        lda _udeks_lifecycle_current_private
        sec
        sbc #$01
        asl a
        asl a
        asl a
        tax
        pla
        sta _udeks_lifecycle_slots_private+TASK_SLOT_WAIT,x
        lda #TASK_STATE_WAITING
        sta _udeks_lifecycle_slots_private+TASK_SLOT_STATE,x
        lda #LIFECYCLE_BLOCK
        sta _udeks_lifecycle_last_event_private
        lda #$00
        sta _udeks_lifecycle_current_private
        sta TREQ_STATE
        sta TREQ_RESULT
        sta TREQ_ERROR
        sec
        rts

yield_handler_end:
        .assert _udeks_task_yield_handler = $c900, error, "lifecycle handler moved"
        .assert task_sleep_poll_gate = $c903, error, "SLEEP poll gate moved"
        .assert task_tick_advance_gate = $c906, error, "scheduler tick gate moved"
        .assert task_wait_snapshot_gate = $c909, error, "private wait snapshot gate moved"
        .assert task_block_caller_gate = $c90c, error, "private block gate moved"
        .assert task_console_get_line_gate = $c90f, error, "private console ownership gate moved"
        .assert yield_handler_end <= $cdbd, error, "lifecycle handler reaches context binding"
