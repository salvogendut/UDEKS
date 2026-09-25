; SPDX-License-Identifier: GPL-3.0-or-later
;
; Executes from top common RAM while copying the Z80 staging image from bank 0
; $D000-$EFFF to its resident bank-1 location at $2000-$3FFF.

        .setcpu "6502"
        .segment "CODE"

BOOT_CHAIN              = $f050
BOOT_CHAIN_STATE        = BOOT_CHAIN + 12
BOOT_CHAIN_FAILURE      = BOOT_CHAIN + 13
BOOT_CHAIN_SOURCE_SUM   = BOOT_CHAIN + 14
BOOT_CHAIN_DEST_SUM     = BOOT_CHAIN + 16

MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_KERNEL_FLAT     = $ff02
MMU_LCR_WORKER_FLAT     = $ff04

gateway_start:
        ; Confirm that the two nominal banks are physically distinct.
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        lda #$a0
        sta $8000
        sta MMU_LCR_WORKER_FLAT
        lda #$a1
        sta $8000
        cmp $8000
        beq bank1_ready
        jmp bank1_failure
bank1_ready:
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        lda $8000
        cmp #$a0
        beq bank0_ready
        jmp bank0_failure
bank0_ready:

        lda #$00
        sta source_sum_low
        sta source_sum_high
        lda #$20
        sta page_count
        lda #$d0
        sta source_load+2
        lda #$20
        sta destination_store+2

copy_page:
        ldy #$00
copy_byte:
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
source_load:
        lda $d000,y
        sta transfer_byte
        clc
        adc source_sum_low
        sta source_sum_low
        bcc source_sum_ready
        inc source_sum_high
source_sum_ready:
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        lda transfer_byte
destination_store:
        sta $2000,y
        iny
        bne copy_byte
        inc source_load+2
        inc destination_store+2
        dec page_count
        bne copy_page

        ; Compare every installed byte and independently checksum bank 1.
        lda #$00
        sta destination_sum_low
        sta destination_sum_high
        lda #$20
        sta page_count
        lda #$d0
        sta source_verify+2
        lda #$20
        sta destination_verify+2

verify_page:
        ldy #$00
verify_byte:
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
source_verify:
        lda $d000,y
        sta transfer_byte
        lda #$00
        sta MMU_LCR_WORKER_FLAT
destination_verify:
        lda $2000,y
        cmp transfer_byte
        beq verify_matches
        jmp copy_failure
verify_matches:
        clc
        adc destination_sum_low
        sta destination_sum_low
        bcc destination_sum_ready
        inc destination_sum_high
destination_sum_ready:
        iny
        bne verify_byte
        inc source_verify+2
        inc destination_verify+2
        dec page_count
        bne verify_page

        lda source_sum_low
        cmp destination_sum_low
        beq checksum_low_matches
        jmp checksum_failure
checksum_low_matches:
        sta BOOT_CHAIN_SOURCE_SUM
        lda source_sum_high
        cmp destination_sum_high
        beq checksum_high_matches
        jmp checksum_failure
checksum_high_matches:
        sta BOOT_CHAIN_SOURCE_SUM+1
        lda destination_sum_low
        sta BOOT_CHAIN_DEST_SUM
        lda destination_sum_high
        sta BOOT_CHAIN_DEST_SUM+1

        ; Relocate the immutable 4 KiB bootfs from the deliberately empty Z80
        ; staging window to bank-1 low RAM, then restore that worker window to
        ; zero before the Z80 is allowed to run.
        lda #$2c
        sta bootfs_source+2
        sta bootfs_clear+2
        lda #$0c
        sta bootfs_destination+2
        ldx #$10
relocate_bootfs_page:
        ldy #$00
relocate_bootfs_byte:
bootfs_source:
        lda $2c00,y
bootfs_destination:
        sta $0c00,y
        lda #$00
bootfs_clear:
        sta $2c00,y
        iny
        bne relocate_bootfs_byte
        inc bootfs_source+2
        inc bootfs_destination+2
        inc bootfs_clear+2
        dex
        bne relocate_bootfs_page

        ; Install the two boot-preloaded application slots after the verified
        ; Z80 image has reached bank 1. Their staging ranges are in the
        ; reclaimable bank-0 VIC shadow and are copied into low RAM that the
        ; boot chain has vacated.
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        lda #$af
        sta low_copy_source+2
        lda #$02
        sta low_copy_destination+2
        ldx #$0a
        jsr copy_low_pages
        lda #$b9
        sta low_copy_source+2
        lda #$12
        sta low_copy_destination+2
        ldx #$0a
        jsr copy_low_pages

        ; Install the persistent shell payload and its zeroed BSS from the
        ; final boot-only bank-0 slot into its private bank-1 task address.
        lda #$c3
        sta ush_source+2
        lda #$90
        sta ush_destination+2
        ldx #$06
copy_ush_page:
        ldy #$00
copy_ush_byte:
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
ush_source:
        lda $c300,y
        sta transfer_byte
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        lda transfer_byte
ush_destination:
        sta $9000,y
        iny
        bne copy_ush_byte
        inc ush_source+2
        inc ush_destination+2
        dex
        bne copy_ush_page

        ; Install the permanent task loader from its reclaimable bank-0 boot
        ; staging area into common RAM. VIC graphics clears this shadow area
        ; before first use, after the loader is safely resident at $FA00.
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        lda #$c9
        sta task_loader_source+2
        lda #$fa
        sta task_loader_destination+2
        ldx #$05
copy_task_loader_page:
        ldy #$00
copy_task_loader_byte:
task_loader_source:
        lda $c900,y
task_loader_destination:
        sta $fa00,y
        iny
        bne copy_task_loader_byte
        inc task_loader_source+2
        inc task_loader_destination+2
        dex
        bne copy_task_loader_page

        ; Install the bank-1 8502 cooperative-task gate above the MMU register
        ; hole. Its 203-byte reservation ends immediately before the existing
        ; CPU-handoff gateway at $FFD0.
        ldy #$00
copy_task_bank_gate:
        lda $ce00,y
        sta $ff05,y
        iny
        cpy #$cb
        bne copy_task_bank_gate

        lda #'Z'
        sta BOOT_CHAIN+8
        lda #'8'
        sta BOOT_CHAIN+9
        lda #'0'
        sta BOOT_CHAIN+10
        lda #'!'
        sta BOOT_CHAIN+11
        lda #$00
        sta BOOT_CHAIN_FAILURE
        lda #$02
        sta BOOT_CHAIN_STATE
        lda #$00
        sta MMU_LCR_KERNEL_IO
        jmp $2000

copy_low_pages:
        ldy #$00
copy_low_byte:
low_copy_source:
        lda $d400,y
low_copy_destination:
        sta $0200,y
        iny
        bne copy_low_byte
        inc low_copy_source+2
        inc low_copy_destination+2
        dex
        bne copy_low_pages
        rts

bank1_failure:
        lda #$02
        bne failure
bank0_failure:
        lda #$03
        bne failure
copy_failure:
        lda #$04
        bne failure
checksum_failure:
        lda #$05
failure:
        sta BOOT_CHAIN_FAILURE
        ora #$80
        sta BOOT_CHAIN_STATE
        lda #$00
        sta MMU_LCR_KERNEL_IO
failure_halt:
        jmp failure_halt

page_count:             .byte $00
transfer_byte:          .byte $00
source_sum_low:         .byte $00
source_sum_high:        .byte $00
destination_sum_low:    .byte $00
destination_sum_high:   .byte $00

gateway_end:
        .assert gateway_end - gateway_start <= $0200, error, "stage-1 gateway exceeds boot reservation"

        ; The early gateway above is dead after it transfers to the kernel.
        ; Align the permanent foreground-task loader at a published common-RAM
        ; address so the user-level shell need not link a private kernel symbol.
        .segment "TASKLOADER"

TASK_STATUS             = $f280
TASK_STATE              = TASK_STATUS + 5
TASK_ERROR              = TASK_STATUS + 6
TASK_EXIT               = TASK_STATUS + 7
TASK_IMAGE_LO           = TASK_STATUS + 8
TASK_IMAGE_HI           = TASK_STATUS + 9
TASK_BSS_LO             = TASK_STATUS + 10
TASK_BSS_HI             = TASK_STATUS + 11
TASK_ARGC               = TASK_STATUS + 12
TASK_ARGV_LO            = TASK_STATUS + 13
TASK_ARGV_HI            = TASK_STATUS + 14
TASK_HEADER             = TASK_STATUS + 16

XCLOCK_STATE            = $f225
XCLOCK_RUNNING          = $03
SYSCALL_TABLE           = $cf00
BOOTFS_BASE             = $0c00
BOOTFS_LIMIT_HI         = $1c
TASK_SLOT               = $0200
TASK_BACKUP             = $8000
CC65_SP                 = $06
TASK_STACK_TOP          = $f7f0

TASK_OK                 = $00
TASK_BAD_SYSCALL_ABI    = $02
TASK_BUSY               = $03
TASK_BAD_MAGIC          = $04
TASK_BAD_VERSION        = $05
TASK_BAD_CPU            = $06
TASK_BAD_FLAGS          = $07
TASK_BAD_LOAD           = $08
TASK_BAD_SIZE           = $09
TASK_BAD_ENTRY          = $0a
TASK_NOT_FOUND          = $0b
TASK_BAD_BOOTFS         = $0c

task_loader_entry:
        .assert task_loader_entry = $fa00, error, "task loader entry moved"

        ; Adapt the cc65 call made by the shell. argv arrives in AX and argc is
        ; the one-byte stack argument. Consume argc exactly as a C callee does.
        sta TASK_ARGV_LO
        stx TASK_ARGV_HI
        ldy #$00
        lda (CC65_SP),y
        sta TASK_ARGC
        inc CC65_SP
        bne task_arg_popped
        inc CC65_SP+1
task_arg_popped:
        lda #'T'
        sta TASK_STATUS+0
        lda #'A'
        sta TASK_STATUS+1
        lda #'S'
        sta TASK_STATUS+2
        lda #'K'
        sta TASK_STATUS+3
        lda #$01
        sta TASK_STATUS+4
        sta TASK_STATE
        lda #$00
        sta TASK_ERROR

        ; APP1 contains xclock. It may be replaced only while xclock is idle.
        lda XCLOCK_STATE
        cmp #XCLOCK_RUNNING
        bne task_check_syscalls
        lda #TASK_BUSY
        jmp task_fail_kernel

task_check_syscalls:
        lda SYSCALL_TABLE+0
        cmp #'U'
        bne task_bad_syscalls
        lda SYSCALL_TABLE+1
        cmp #'S'
        bne task_bad_syscalls
        lda SYSCALL_TABLE+2
        cmp #'Y'
        bne task_bad_syscalls
        lda SYSCALL_TABLE+3
        cmp #'S'
        bne task_bad_syscalls
        lda SYSCALL_TABLE+4
        bne task_bad_syscalls
        lda SYSCALL_TABLE+5
        cmp #$02
        bcs task_bad_syscalls
        lda SYSCALL_TABLE+6
        cmp #$02
        bcc task_bad_syscalls
        jmp task_find_file
task_bad_syscalls:
        lda #TASK_BAD_SYSCALL_ABI
        jmp task_fail_kernel

task_find_file:
        ; Resolve argv[0] in the bootfs /bin directory. The argv vector and
        ; command text remain in bank 0 while the immutable directory is in
        ; the bank-1 staging window.
        lda TASK_ARGV_LO
        sta task_argv_pointer_load+1
        lda TASK_ARGV_HI
        sta task_argv_pointer_load+2
        ldy #$00
task_argv_pointer_load:
        lda $ffff,y
        sta task_command_load+1
        sta task_command_compare_load+1
        iny
        lda $ffff,y
        sta task_command_load+2
        sta task_command_compare_load+2
        ldy #$00
task_measure_name:
task_command_load:
        lda $ffff,y
        beq task_name_measured
        iny
        cpy #$11
        bcc task_measure_name
        jmp task_not_found
task_name_measured:
        sty task_name_length
        bne task_validate_bootfs
        jmp task_not_found

task_validate_bootfs:
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        lda BOOTFS_BASE+0
        cmp #'U'
        bne task_bootfs_reject_early
        lda BOOTFS_BASE+1
        cmp #'B'
        bne task_bootfs_reject_early
        lda BOOTFS_BASE+2
        cmp #'F'
        bne task_bootfs_reject_early
        lda BOOTFS_BASE+3
        cmp #'S'
        bne task_bootfs_reject_early
        lda BOOTFS_BASE+4
        bne task_bootfs_reject_early
        lda BOOTFS_BASE+5
        cmp #$02
        bcs task_bootfs_reject_early
        lda BOOTFS_BASE+6
        beq task_bootfs_reject_early
        sta task_entries_remaining
        lda BOOTFS_BASE+7
        cmp #$18
        bne task_bootfs_reject_early
        lda BOOTFS_BASE+8
        cmp #$10
        bne task_bootfs_reject_early
        lda BOOTFS_BASE+9
        bne task_bootfs_reject_early
        lda BOOTFS_BASE+14
        ora BOOTFS_BASE+15
        bne task_bootfs_reject_early
        jmp task_bootfs_header_valid

task_bootfs_reject_early:
        jmp task_bad_bootfs

task_bootfs_header_valid:
        ; Convert bootfs-relative data/end offsets to absolute bank-1
        ; addresses and keep them inside the reserved $0C00-$1BFF window.
        lda BOOTFS_BASE+10
        sta task_data_begin_lo
        lda BOOTFS_BASE+11
        clc
        adc #>BOOTFS_BASE
        sta task_data_begin_hi
        lda BOOTFS_BASE+12
        sta task_bootfs_end_lo
        lda BOOTFS_BASE+13
        clc
        adc #>BOOTFS_BASE
        sta task_bootfs_end_hi
        bcs task_bootfs_reject_bounds
        cmp #BOOTFS_LIMIT_HI
        bcc :+
        bne task_bootfs_reject_bounds
        lda task_bootfs_end_lo
        bne task_bootfs_reject_bounds
:
        lda task_data_begin_hi
        cmp #>BOOTFS_BASE
        bcc task_bootfs_reject_bounds
        cmp task_bootfs_end_hi
        bcc task_bootfs_layout_ready
        bne task_bootfs_reject_bounds
        lda task_data_begin_lo
        cmp task_bootfs_end_lo
        bcc task_bootfs_layout_ready
task_bootfs_reject_bounds:
        jmp task_bad_bootfs

task_bootfs_layout_ready:
        lda #<(BOOTFS_BASE+$10)
        sta task_entry_load+1
        lda #>(BOOTFS_BASE+$10)
        sta task_entry_load+2
        lda #<(BOOTFS_BASE+$18)
        sta task_entry_name_load+1
        lda #>(BOOTFS_BASE+$18)
        sta task_entry_name_load+2

task_next_entry:
        lda task_entries_remaining
        bne :+
        jmp task_not_found
:
        dec task_entries_remaining
        ldy #$00
task_entry_load:
        lda BOOTFS_BASE+$10,y
        and #$01
        beq task_advance_entry
        iny
        lda BOOTFS_BASE+$10,y
        cmp task_name_length
        bne task_advance_entry
        ldy #$00
task_compare_name:
        cpy task_name_length
        beq task_file_found
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
task_command_compare_load:
        lda $ffff,y
        sta task_transfer_byte
        lda #$00
        sta MMU_LCR_WORKER_FLAT
task_entry_name_load:
        lda BOOTFS_BASE+$18,y
        cmp task_transfer_byte
        bne task_advance_entry
        iny
        bne task_compare_name

task_advance_entry:
        ; Advance both self-modifying directory pointers by one 24-byte
        ; record. The host packer and the data-bound check below prevent the
        ; walk from entering file payloads.
        clc
        lda task_entry_load+1
        adc #$18
        sta task_entry_load+1
        lda task_entry_load+2
        adc #$00
        sta task_entry_load+2
        clc
        lda task_entry_name_load+1
        adc #$18
        sta task_entry_name_load+1
        lda task_entry_name_load+2
        adc #$00
        sta task_entry_name_load+2
        lda task_entry_load+2
        cmp task_data_begin_hi
        bcc task_next_entry
        beq :+
        jmp task_bad_bootfs
:
        lda task_entry_load+1
        cmp task_data_begin_lo
        bcc task_next_entry
        jmp task_bad_bootfs

task_file_found:
        ; Read the selected file bounds from the matching directory entry.
        ; task_entry_load currently names the record's flags byte.
        lda task_entry_load+1
        sta task_entry_copy_load+1
        lda task_entry_load+2
        sta task_entry_copy_load+2
        ldx #$07
task_entry_copy:
task_entry_copy_load:
        lda $ffff,x
        sta TASK_HEADER,x
        dex
        bpl task_entry_copy
        lda TASK_HEADER+2
        sta task_file_lo
        lda TASK_HEADER+3
        clc
        adc #>BOOTFS_BASE
        sta task_file_hi
        lda TASK_HEADER+4
        sta task_file_size_lo
        lda TASK_HEADER+5
        sta task_file_size_hi
        lda task_file_size_lo
        ora task_file_size_hi
        beq task_file_reject
        lda task_file_hi
        cmp task_data_begin_hi
        bcc task_file_reject
        bne :+
        lda task_file_lo
        cmp task_data_begin_lo
        bcc task_file_reject
:
        clc
        lda task_file_lo
        adc task_file_size_lo
        sta task_allocation_lo
        lda task_file_hi
        adc task_file_size_hi
        sta task_allocation_hi
        bcs task_file_reject
        cmp task_bootfs_end_hi
        bcc task_file_bounds_ready
        bne task_file_reject
        lda task_allocation_lo
        cmp task_bootfs_end_lo
        bcc task_file_bounds_ready
        beq task_file_bounds_ready
task_file_reject:
        jmp task_bad_bootfs

task_file_bounds_ready:
        lda task_file_lo
        sta task_header_load+1
        lda task_file_hi
        sta task_header_load+2
        clc
        lda task_file_lo
        adc #$10
        sta task_copy_load+1
        lda task_file_hi
        adc #$00
        sta task_copy_load+2

task_fetch_header:
        ldx #$0f
task_header_loop:
task_header_load:
        lda $ffff,x
        sta TASK_HEADER,x
        dex
        bpl task_header_loop

        lda TASK_HEADER+0
        cmp #'U'
        beq :+
        jmp task_bad_magic
:
        lda TASK_HEADER+1
        cmp #'D'
        beq :+
        jmp task_bad_magic
:
        lda TASK_HEADER+2
        cmp #'E'
        beq :+
        jmp task_bad_magic
:
        lda TASK_HEADER+3
        cmp #'X'
        beq :+
        jmp task_bad_magic
:
        lda TASK_HEADER+4
        beq :+
        jmp task_bad_version
:
        lda TASK_HEADER+5
        cmp #$02
        bcc :+
        jmp task_bad_version
:
        lda TASK_HEADER+6
        cmp #$01
        beq :+
        jmp task_bad_cpu
:
        lda TASK_HEADER+7
        beq :+
        jmp task_bad_flags
:
        lda TASK_HEADER+8
        beq :+
        jmp task_bad_load
:
        lda TASK_HEADER+9
        cmp #$02
        beq :+
        jmp task_bad_load
:

        lda TASK_HEADER+10
        sta TASK_IMAGE_LO
        lda TASK_HEADER+11
        sta TASK_IMAGE_HI
        lda TASK_IMAGE_LO
        ora TASK_IMAGE_HI
        bne :+
        jmp task_bad_size
:
        clc
        lda TASK_IMAGE_LO
        adc #$10
        cmp task_file_size_lo
        beq :+
        jmp task_bad_size
:
        lda TASK_IMAGE_HI
        adc #$00
        cmp task_file_size_hi
        beq :+
        jmp task_bad_size
:
        lda TASK_HEADER+12
        sta TASK_BSS_LO
        lda TASK_HEADER+13
        sta TASK_BSS_HI
        clc
        lda TASK_IMAGE_LO
        adc TASK_BSS_LO
        sta task_allocation_lo
        lda TASK_IMAGE_HI
        adc TASK_BSS_HI
        sta task_allocation_hi
        bcc :+
        jmp task_bad_size
:
        cmp #$0a
        bcc task_check_entry
        beq :+
        jmp task_bad_size
:
        lda task_allocation_lo
        beq :+
        jmp task_bad_size
:

task_check_entry:
        ; entry offset = entry - $0200 and must be below image size.
        sec
        lda TASK_HEADER+14
        sbc #$00
        sta task_entry_offset_lo
        lda TASK_HEADER+15
        sbc #$02
        sta task_entry_offset_hi
        bcs :+
        jmp task_bad_entry
:
        lda task_entry_offset_hi
        cmp TASK_IMAGE_HI
        bcc task_valid
        beq :+
        jmp task_bad_entry
:
        lda task_entry_offset_lo
        cmp TASK_IMAGE_LO
        bcc task_valid
        jmp task_bad_entry

task_valid:
        ; Save all ten pages of APP1 in unused bank-1 RAM.
        lda #$02
        sta task_save_load+2
        lda #$80
        sta task_save_store+2
        ldx #$0a
task_save_page:
        ldy #$00
task_save_byte:
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
task_save_load:
        lda TASK_SLOT,y
        sta task_transfer_byte
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        lda task_transfer_byte
task_save_store:
        sta TASK_BACKUP,y
        iny
        bne task_save_byte
        inc task_save_load+2
        inc task_save_store+2
        dex
        bne task_save_page

        ; Copy exactly the validated UDEX image bytes into APP1.
        lda #<TASK_SLOT
        sta task_copy_store+1
        lda #>TASK_SLOT
        sta task_copy_store+2
        lda TASK_IMAGE_LO
        sta task_remaining_lo
        lda TASK_IMAGE_HI
        sta task_remaining_hi
task_copy_byte:
        lda task_remaining_lo
        ora task_remaining_hi
        beq task_clear_bss
        lda #$00
        sta MMU_LCR_WORKER_FLAT
task_copy_load:
        lda $ffff
        sta task_transfer_byte
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        lda task_transfer_byte
task_copy_store:
        sta TASK_SLOT
        inc task_copy_load+1
        bne task_copy_source_ready
        inc task_copy_load+2
task_copy_source_ready:
        inc task_copy_store+1
        bne task_copy_destination_ready
        inc task_copy_store+2
task_copy_destination_ready:
        lda task_remaining_lo
        bne task_copy_decrement_low
        dec task_remaining_hi
task_copy_decrement_low:
        dec task_remaining_lo
        jmp task_copy_byte

task_clear_bss:
        lda task_copy_store+1
        sta task_bss_store+1
        lda task_copy_store+2
        sta task_bss_store+2
        lda TASK_BSS_LO
        sta task_remaining_lo
        lda TASK_BSS_HI
        sta task_remaining_hi
        lda #$00
task_clear_byte:
        ldx task_remaining_lo
        bne task_clear_store
        ldx task_remaining_hi
        beq task_enter
task_clear_store:
task_bss_store:
        sta TASK_SLOT
        inc task_bss_store+1
        bne task_bss_destination_ready
        inc task_bss_store+2
task_bss_destination_ready:
        ldx task_remaining_lo
        bne task_bss_decrement_low
        dec task_remaining_hi
task_bss_decrement_low:
        dec task_remaining_lo
        jmp task_clear_byte

task_enter:
        lda #$00
        sta MMU_LCR_KERNEL_IO
        ; The task has its own cc65 zero-page workspace. Preserve the complete
        ; compiler/runtime reservation, including the resident software-stack
        ; pointer after this loader call consumed argc.
        ldx #$1d
task_save_zp:
        lda $02,x
        sta task_saved_zp,x
        dex
        bpl task_save_zp
        lda #<TASK_STACK_TOP
        sta CC65_SP
        lda #>TASK_STACK_TOP
        sta CC65_SP+1
        lda #$02
        sta TASK_STATE
        lda TASK_ARGC
        ldx TASK_ARGV_LO
        ldy TASK_ARGV_HI
        jsr TASK_SLOT
        sta TASK_EXIT
        ldx #$1d
task_restore_zp:
        lda task_saved_zp,x
        sta $02,x
        dex
        bpl task_restore_zp

        ; Restore APP1 before returning to any resident shell code.
        lda #$80
        sta task_restore_load+2
        lda #$02
        sta task_restore_store+2
        ldx #$0a
task_restore_page:
        ldy #$00
task_restore_byte:
        lda #$00
        sta MMU_LCR_WORKER_FLAT
task_restore_load:
        lda TASK_BACKUP,y
        sta task_transfer_byte
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        lda task_transfer_byte
task_restore_store:
        sta TASK_SLOT,y
        iny
        bne task_restore_byte
        inc task_restore_load+2
        inc task_restore_store+2
        dex
        bne task_restore_page
        lda #$00
        sta MMU_LCR_KERNEL_IO
        lda #$03
        sta TASK_STATE
        lda TASK_EXIT
        ldx #$00
        rts

task_bad_magic:
        lda #TASK_BAD_MAGIC
        bne task_fail_worker
task_bad_version:
        lda #TASK_BAD_VERSION
        bne task_fail_worker
task_bad_cpu:
        lda #TASK_BAD_CPU
        bne task_fail_worker
task_bad_flags:
        lda #TASK_BAD_FLAGS
        bne task_fail_worker
task_bad_load:
        lda #TASK_BAD_LOAD
        bne task_fail_worker
task_bad_size:
        lda #TASK_BAD_SIZE
        bne task_fail_worker
task_bad_entry:
        lda #TASK_BAD_ENTRY
        bne task_fail_worker
task_not_found:
        lda #TASK_NOT_FOUND
        bne task_fail_worker
task_bad_bootfs:
        lda #TASK_BAD_BOOTFS
task_fail_worker:
        pha
        lda #$00
        sta MMU_LCR_KERNEL_IO
        pla
task_fail_kernel:
        sta TASK_ERROR
        ora #$80
        sta TASK_STATE
        lda #$01
        ldx #$00
        rts

task_transfer_byte:     .byte $00
task_remaining_lo:      .byte $00
task_remaining_hi:      .byte $00
task_allocation_lo:     .byte $00
task_allocation_hi:     .byte $00
task_entry_offset_lo:   .byte $00
task_entry_offset_hi:   .byte $00
task_name_length:       .byte $00
task_entries_remaining: .byte $00
task_data_begin_lo:     .byte $00
task_data_begin_hi:     .byte $00
task_bootfs_end_lo:     .byte $00
task_bootfs_end_hi:     .byte $00
task_file_lo:           .byte $00
task_file_hi:           .byte $00
task_file_size_lo:      .byte $00
task_file_size_hi:      .byte $00
task_saved_zp:          .res $1e, $00

task_loader_end:
        .assert task_loader_end <= $ff00, error, "task loader crosses MMU register hole"
