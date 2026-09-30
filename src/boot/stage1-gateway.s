; SPDX-License-Identifier: GPL-3.0-or-later
;
; Executes from top common RAM while copying the Z80 staging image from bank 0
; $D000-$EFFF to its resident bank-1 location at $2000-$3FFF.

        .setcpu "6502"
        .include "capability-delivery.inc"
        .include "disk-loader-bindings.inc"

BOOT_CHAIN              = $f050
BOOT_CHAIN_STATE        = BOOT_CHAIN + 12
BOOT_CHAIN_FAILURE      = BOOT_CHAIN + 13
BOOT_CHAIN_SOURCE_SUM   = BOOT_CHAIN + 14
BOOT_CHAIN_DEST_SUM     = BOOT_CHAIN + 16

MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_KERNEL_FLAT     = $ff02
MMU_LCR_WORKER_FLAT     = $ff04
BUSY_SPRITE_SOURCE      = $0bc0
VIC_BUSY_TEMPLATE       = $4140

        ; This installer remains below $F800 while it replaces the boot-time
        ; code above it with permanent common-RAM services.
        .segment "FINAL"
gateway_entry:
        jmp gateway_start
final_install:
        ; Install the permanent task loader while executing from the protected
        ; $F700 page.  The main gateway has grown into the $F910 destination,
        ; so copying it from $F800 code would overwrite the active copy loop.
        lda #$c8
        sta final_task_loader_source+2
        lda #$f9
        sta final_task_loader_destination+2
        lda #$10
        sta final_task_loader_destination+1
        ldx #$05
final_copy_task_loader_page:
        ldy #$00
final_copy_task_loader_byte:
final_task_loader_source:
        lda $c800,y
final_task_loader_destination:
        sta $f910,y
        iny
        bne final_copy_task_loader_byte
        inc final_task_loader_source+2
        inc final_task_loader_destination+2
        dex
        bne final_copy_task_loader_page
        ; Copy the final $F0 bytes without entering the MMU-register page.
        ldy #$00
final_copy_task_loader_tail:
        lda $cd00,y
        sta $fe10,y
        iny
        cpy #$f0
        bne final_copy_task_loader_tail

        lda #$c4
        sta final_copy_bootfs_load+2
        lda #$f3
        sta final_copy_bootfs_store+2
        ldx #$02
final_copy_bootfs_page:
        ldy #$00
final_copy_bootfs_byte:
final_copy_bootfs_load:
        lda $c4ef,y
final_copy_bootfs_store:
        sta $f3ef,y
        iny
        bne final_copy_bootfs_byte
        inc final_copy_bootfs_load+2
        inc final_copy_bootfs_store+2
        dex
        bne final_copy_bootfs_page
        ldy #$00
final_copy_bootfs_tail:
        lda $c6ef,y
        sta $f5ef,y
        iny
        cpy #$9b
        bne final_copy_bootfs_tail
        lda #$00
        sta $f3e8
        sta $f3e9
        sta $f3ed
        sta $f2a6

        ldy #$00
final_copy_request_page:
        lda $c300,y
        sta $f800,y
        iny
        bne final_copy_request_page
        ldy #$00
final_copy_request_tail:
        lda $c400,y
        sta $f900,y
        iny
        cpy #$09
        bne final_copy_request_tail

        ; The stage-0 KERNAL load left the versioned scheduler payload in
        ; bank 1. The one-shot common-RAM installer validates it, copies the
        ; page to $1200 and the tail to its linked bank-0 home, and clears its
        ; BSS. The scheduler entry later replaces this temporary gate.
        jsr $ff05

        ; The staged probe moves over the dead boot-sector page; the kernel
        ; runs it from $0B00 during hardware discovery.
        lda #$ad
        sta final_copy_probe_source+2
        ldy #$00
final_copy_probe_byte:
final_copy_probe_source:
        lda $ad00,y
        sta $0b00,y
        iny
        bne final_copy_probe_byte

        ; Stage 1's $1C00 page is dead now that this installer runs from the
        ; protected $F700 page.  Move the staged crt0 over it and enter there:
        ; crt0 clears BSS and the whole VICSHADOW segment through its
        ; linker-generated bounds, then jumps to _kernel_main in the resident
        ; code.  The reclaimed tail above the shadow must survive untouched.
        lda #$ae
        sta final_copy_crt0_source+2
        ldy #$00
final_copy_crt0_byte:
final_copy_crt0_source:
        lda $ae00,y
        sta $1c00,y
        iny
        bne final_copy_crt0_byte

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
        jmp $1c00
final_install_end:
        .assert final_install_end <= $f7d8, error, "final installer exceeds protected common page"

        ; Runs after crt0 returns to the fixed $F7D8 entry: copy the gathered
        ; scheduler into its reserved page and enter the scheduler entry.
        .segment "SCHEDINSTALL"
scheduler_install:
        lda #$12
        sta scheduler_install_source+2
        lda #$1c
        sta scheduler_install_destination+2
        ldx #$04
scheduler_install_page:
        ldy #$00
scheduler_install_byte:
scheduler_install_source:
        lda $1200,y
scheduler_install_destination:
        sta $1c00,y
        iny
        bne scheduler_install_byte
        inc scheduler_install_source+2
        inc scheduler_install_destination+2
        dex
        bne scheduler_install_page
        jmp $1c00
scheduler_install_end:
        .assert scheduler_install = $f7d8, error, "scheduler installer moved"
        .assert scheduler_install_end <= $f800, error, "scheduler installer exceeds protected common page"

        .segment "CODE"

gateway_start:
        ; SETLFS for SCHEDOVR retained the actual boot unit in KERNAL $BA.
        ; Capture it before retiring KERNAL; stage 0 has no spare bytes.
        lda $ba
        sta BOOT_CHAIN+20
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

        ; SCHEDOVR already delivered bootfs to bank-1 $A000-$D0FF. Do not
        ; overwrite it from legacy Z80/shadow staging. Those old containers
        ; are no longer a limit on command packaging.
        ; The high-memory module still uses its fixed bank-0 staging slot.
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        lda #$bb
        sta module_source+1
        lda #$bf
        sta module_source+2
        lda #$00
        sta module_destination+1
        lda #$e3
        sta module_destination+2
        ldx #$03
copy_module_page:
        ldy #$00
copy_module_byte:
module_source:
        lda $bfbb,y
module_destination:
        sta $e300,y
        iny
        bne copy_module_byte
        inc module_source+2
        inc module_destination+2
        dex
        bne copy_module_page
        ldy #$00
copy_module_tail:
        lda $c2bb,y
        sta $e600,y
        iny
        cpy #$45
        bne copy_module_tail
        lda #$00
        sta MMU_LCR_KERNEL_FLAT

        ; Install the one-shot scheduler-tail loader above the MMU register
        ; hole. The scheduler entry replaces it with the permanent bank-1
        ; task gate before entering the kernel.
        ldy #$00
copy_scheduler_tail_installer:
        lda $c409,y
        sta $ff05,y
        iny
        cpy #$c0
        bne copy_scheduler_tail_installer

        ; Preserve the first installed bootfs-service page in otherwise free
        ; bank-1 RAM. VIC page commits borrow that common page as a transfer
        ; buffer and restore it from this immutable backup before returning.
        ldy #$00
backup_service_page:
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        lda $c500,y
        sta transfer_byte
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        lda transfer_byte
        sta $4000,y
        iny
        bne backup_service_page

        ; Move the generated pipe out of the disposable stage-1 image and
        ; into reserved space near the start of the VIC-visible bank. Runtime
        ; changes can then copy entirely within bank 1 without spending
        ; scarce resident-kernel bytes on the 63-byte sprite payload.
        ldy #$00
copy_busy_sprite:
        lda #$00
        sta MMU_LCR_KERNEL_FLAT
        lda BUSY_SPRITE_SOURCE,y
        sta transfer_byte
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        lda transfer_byte
        sta VIC_BUSY_TEMPLATE,y
        iny
        cpy #$3f
        bne copy_busy_sprite
        lda #$00
        sta MMU_LCR_KERNEL_FLAT

        ; The capability image and this one-shot installer occupy the newly
        ; reclaimed lower shadow. Copy and checksum the image before the
        ; protected installer enters crt0 and clears that shadow.
        jsr CAPABILITY_INSTALLER
        beq capability_installed
capability_install_failed:
        jmp capability_install_failed
capability_installed:

        ; The boot-only console composer is staged after the capability
        ; installer. Its one-shot copier occupies the dead boot-sector tail;
        ; it halts after publishing a boot-chain failure if validation fails.
        ; The scheduler installer uses $1200-$15FF, below its $1600-$1BA9
        ; runtime home.
        jsr $0b50

        ; The protected $F700 installer can now replace this executing
        ; $F800-$F9FF boot code without stack-page relocation.
        jmp final_install

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
        .assert gateway_end - gateway_start <= $0300, error, "stage-1 gateway exceeds boot reservation"

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

SYSCALL_TABLE           = $cf00
BOOTFS_BASE             = $a000
BOOTFS_LIMIT_HI         = $d1
TASK_SLOT               = $0200
PERSISTENT_SLOT         = $9000
TASK_BACKUP             = $8000
; The resident image reserves four zero-page bytes before none.lib, while a
; standalone UDEX begins its runtime reservation at $02.
RESIDENT_CC65_SP        = $06
USER_CC65_SP            = $02
TASK_STACK_TOP          = $f7f0

TASK_OK                 = $00
TASK_BAD_SYSCALL_ABI    = $02
TASK_BAD_MAGIC          = $04
TASK_BAD_VERSION        = $05
TASK_BAD_CPU            = $06
TASK_BAD_FLAGS          = $07
TASK_BAD_LOAD           = $08
TASK_BAD_SIZE           = $09
TASK_BAD_ENTRY          = $0a
TASK_NOT_FOUND          = $0b
TASK_BAD_BOOTFS         = $0c
TASK_IO_ERROR           = $0d

task_persistent_loader_entry:
        .assert task_persistent_loader_entry = $f910, error, "persistent loader entry moved"
        jmp task_load_persistent
task_loader_entry:
        .assert task_loader_entry = $f913, error, "task loader entry moved"
        jmp task_load_foreground
task_managed_loader_entry:
        .assert task_managed_loader_entry = $f916, error, "managed loader entry moved"
        jmp task_load_managed
task_spawn_loader_entry:
        .assert task_spawn_loader_entry = $f919, error, "spawn loader entry moved"
        ; The lifecycle handler passes a zero-padded name in common RAM.
        ; Copy an ordinary UDEX into bank-1 APP1 but do not enter it.
        pha
        ldy #$80
        lda #>TASK_SLOT
task_load_named_destination:
        sta task_copy_store_persistent+2
        lda #<TASK_SLOT
        sta task_copy_store_persistent+1
        pla
        jmp task_load_named

task_load_persistent:
        ; init passes a direct bank-0 pointer to the bootfs program name in AX.
        pha
        ldy #$01
        lda #>PERSISTENT_SLOT
        bne task_load_named_destination
task_load_managed:
        ; The resident application manager supplies a direct name pointer.
        ldy #$02
task_load_named:
        sta task_command_load+1
        stx task_command_load+2
        sty task_load_mode
        jmp task_initialize

task_load_foreground:
        ; A live native child owns both bank-1 APP1 and the common launcher
        ; at TASK_STATUS. Reject BEFORE touching either. X=1 distinguishes
        ; the busy return from every ordinary eight-bit program exit code.
        pha
        lda DISK_LOADER_CHILD_STATE
        beq :+
        pla
        inc RESIDENT_CC65_SP
        bne task_busy_return
        inc RESIDENT_CC65_SP+1
task_busy_return:
        lda #$03
        ldx #$01
        rts
:
        pla
        ; Adapt the cc65 call made by the shell. argv arrives in AX and argc is
        ; the one-byte stack argument. Consume argc exactly as a C callee does.
        sta TASK_ARGV_LO
        stx TASK_ARGV_HI
        ldy #$00
        lda (RESIDENT_CC65_SP),y
        sta TASK_ARGC
        inc RESIDENT_CC65_SP
        bne task_arg_popped
        inc RESIDENT_CC65_SP+1
task_arg_popped:
        lda #$00
        sta task_load_mode
task_initialize:
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
        cmp #$04
        bcs task_bad_syscalls
        lda SYSCALL_TABLE+6
        cmp #$02
        bcc task_bad_syscalls
        ; A direct/debug PRG may lack secondary delivery. Fail closed instead
        ; of jumping into an absent bank-1 service extension.
        lda #0
        sta MMU_LCR_WORKER_FLAT
        ldx #5
task_lookup_identity:
        lda task_lookup_bootfs+3,x
        cmp task_lookup_signature,x
        bne task_lookup_missing
        dex
        bpl task_lookup_identity
        sta MMU_LCR_KERNEL_IO
        jmp task_find_file
task_lookup_missing:
        jmp task_bad_bootfs
task_lookup_signature: .byte "ULKP", 0, 1
task_bad_syscalls:
        lda #TASK_BAD_SYSCALL_ABI
        jmp task_fail_kernel

task_find_file:
        ; Resolve argv[0] in the bootfs /bin directory. The argv vector and
        ; command text remain in bank 0 while the immutable directory is in
        ; the bank-1 staging window.
        lda task_load_mode
        bne task_measure_name_start
        lda TASK_ARGV_LO
        sta task_argv_pointer_load+1
        sta task_argv_pointer_high_load+1
        lda TASK_ARGV_HI
        sta task_argv_pointer_load+2
        sta task_argv_pointer_high_load+2
        ldy #$00
task_argv_pointer_load:
        lda $ffff,y
        sta task_command_load+1
        iny
task_argv_pointer_high_load:
        lda $ffff,y
        sta task_command_load+2
        jmp task_measure_name_start
task_measure_name_start:
        lda task_command_load+1
        sta task_disk_name_load+1
        lda task_command_load+2
        sta task_disk_name_load+2
        ldy #$00
task_disk_name_load:
        lda $ffff,y
        cmp #'/'
        bne task_bootfs_name
        lda task_load_mode
        beq :+
        cmp #1                      ; persistent bootstrap shell also uses disk
        bne task_bootfs_name
:
        jmp task_disk_open
task_bootfs_name:
        ldy #$00
task_measure_name:
task_command_load:
        lda $ffff,y
        beq task_name_measured
        sta TASK_HEADER,y
        iny
        cpy #$11
        bcc task_measure_name
        jmp task_not_found
task_name_measured:
        tya
        sta task_name_length
        bne task_validate_bootfs
        jmp task_not_found

task_validate_bootfs:
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        jmp task_lookup_bootfs

        ; Pure lookup/validation runs in bank 1. The same link resolves the
        ; private common continuation addresses; no new public ABI gate.
        .segment "TASKLOOKUP"
task_lookup_bootfs:
        jmp task_lookup_code
        .byte "ULKP", 0, 1
task_lookup_code:
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
        ; addresses and keep them inside the reserved $0300-$1FFF window.
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
        sta task_entry_length_load+1
        lda #>(BOOTFS_BASE+$10)
        sta task_entry_load+2
        sta task_entry_length_load+2
        lda #<(BOOTFS_BASE+$18)
        sta task_entry_name_load+1
        lda #>(BOOTFS_BASE+$18)
        sta task_entry_name_load+2

task_next_entry:
        lda task_entries_remaining
        bne :+
        jmp task_lookup_miss
:
        dec task_entries_remaining
        ldy #$00
task_entry_load:
        lda BOOTFS_BASE+$10,y
        and #$01
        beq task_advance_entry
        iny
task_entry_length_load:
        lda BOOTFS_BASE+$10,y
        cmp task_name_length
        bne task_advance_entry
        ldy #$00
task_compare_name:
        cpy task_name_length
        beq task_file_found
        lda TASK_HEADER,y
task_entry_name_load:
        cmp BOOTFS_BASE+$18,y
        bne task_advance_entry
        iny
        bne task_compare_name

task_advance_entry:
        lda task_entries_remaining
        bne :+
        jmp task_lookup_miss
:
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
        lda task_entry_length_load+1
        adc #$18
        sta task_entry_length_load+1
        lda task_entry_length_load+2
        adc #$00
        sta task_entry_length_load+2
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
        bcc task_file_bounds_jump
        bne task_file_reject
        lda task_allocation_lo
        cmp task_bootfs_end_lo
        bcc task_file_bounds_jump
        beq task_file_bounds_jump
task_file_reject:
        jmp task_bad_bootfs
task_file_bounds_jump:
        jmp task_file_bounds_ready

; Small initial PATH: immutable /bin first, then a leaf on mounted /mnt.
; Only synchronous foreground programs can use the disk loader today.
task_lookup_miss:
        lda task_load_mode
        beq :+
        jmp task_not_found
:
        ldx #4
:
        lda task_disk_mount,x
        sta task_disk_leaf,x
        dex
        bpl :-
        ldx #0
:
        lda TASK_HEADER,x
        sta task_disk_leaf+5,x
        inx
        cpx task_name_length
        bcc :-
        lda #0
        sta task_disk_leaf+5,x
        lda #<task_disk_leaf
        sta task_command_load+1
        lda #>task_disk_leaf
        sta task_command_load+2
        jmp task_disk_fallback

        .segment "TASKLOADER"
task_disk_fallback:
        sta MMU_LCR_KERNEL_IO
        jmp task_disk_open
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
        sta task_copy_load_persistent+2
        lda task_copy_load+1
        sta task_copy_load_persistent+1

task_fetch_header:
        ldx #$0f
task_header_loop:
task_header_load:
        lda $ffff,x
        sta TASK_HEADER,x
        dex
        bpl task_header_loop
        jmp task_validate_header

        .segment "TASKLOOKUP"
task_validate_header:
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
        lda task_load_mode
        and #$7f
        cmp TASK_HEADER+7
        beq :+
        jmp task_bad_flags
:
        lda TASK_HEADER+8
        beq :+
        jmp task_bad_load
:
        lda TASK_HEADER+9
        ldx task_load_mode
        beq task_check_foreground_load
        bmi task_check_foreground_load
        cpx #$01
        bne task_check_managed_load
        cmp #$90
        beq :+
        jmp task_bad_load
task_check_foreground_load:
        cmp #$02
        beq :+
        jmp task_bad_load
task_check_managed_load:
        cmp #$02
        beq :+
        cmp #$12
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
        sta task_allocation_lo
        lda TASK_IMAGE_HI
        adc #$00
        sta task_allocation_hi
        lda task_allocation_lo
        cmp task_file_size_lo
        bne task_file_size_bad
        lda task_allocation_hi
        cmp task_file_size_hi
        beq task_file_size_valid
task_file_size_bad:
        jmp task_bad_size
task_file_size_valid:
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
        ldx #$0a
        lda task_load_mode
        cmp #1
        bne :+
        ldx #$10                    ; persistent ush ends before bootfs
:
        cpx task_allocation_hi
        bcc task_size_reject
        beq :+
        bne task_check_entry
task_size_reject:
        jmp task_bad_size
:
        lda task_allocation_lo
        beq :+
        jmp task_bad_size
:

task_check_entry:
        ; Persistent context entry is currently fixed at $9000. Reject a
        ; different (even in-image) entry instead of silently ignoring it.
        lda task_load_mode
        cmp #1
        bne task_check_entry_offset
        lda TASK_HEADER+14
        bne task_persistent_entry_bad
        lda TASK_HEADER+15
        cmp #$90
        beq task_check_entry_offset
task_persistent_entry_bad:
        jmp task_bad_entry
task_check_entry_offset:
        ; entry offset = entry - load base and must be below image size.
        sec
        lda TASK_HEADER+14
        sbc #$00
        sta task_entry_offset_lo
        lda TASK_HEADER+15
        sbc TASK_HEADER+9
        sta task_entry_offset_hi
        bcs :+
        jmp task_bad_entry
:
        lda task_entry_offset_hi
        cmp TASK_IMAGE_HI
        bcc task_valid_jump
        beq :+
        jmp task_bad_entry
:
        lda task_entry_offset_lo
        cmp TASK_IMAGE_LO
        bcc task_valid_jump
        jmp task_bad_entry
task_valid_jump:
        jmp task_valid

        .segment "TASKLOADER"
task_valid:
        lda task_load_mode
        beq task_save_foreground
        bmi task_copy_persistent
        cmp #$02
        beq task_copy_managed
task_copy_persistent:
        lda TASK_IMAGE_LO
        sta task_remaining_lo
        lda TASK_IMAGE_HI
        sta task_remaining_hi
task_copy_persistent_byte:
task_copy_load_persistent:
        ; Both source and destination are in bank 1 while this map is active.
        lda $ffff
task_copy_store_persistent:
        sta PERSISTENT_SLOT
        inc task_copy_load_persistent+1
        bne :+
        inc task_copy_load_persistent+2
:
        inc task_copy_store_persistent+1
        bne :+
        inc task_copy_store_persistent+2
:
        lda task_remaining_lo
        bne :+
        dec task_remaining_hi
:
        dec task_remaining_lo
        lda task_remaining_lo
        ora task_remaining_hi
        bne task_copy_persistent_byte
        jmp task_clear_bss

task_copy_managed:
        lda #$00
        sta task_copy_store+1
        lda TASK_HEADER+9
        sta task_copy_store+2
        jmp task_prepare_copy_count

task_prepare_copy_count:
        lda TASK_IMAGE_LO
        sta task_remaining_lo
        lda TASK_IMAGE_HI
        sta task_remaining_hi
        jmp task_copy_byte

task_save_foreground:
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
        jmp task_prepare_copy_count
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
        lda task_load_mode
        beq task_clear_bss_pointer_ready
        cmp #$02
        beq task_clear_bss_pointer_ready
        lda task_copy_store_persistent+1
        sta task_bss_store+1
        lda task_copy_store_persistent+2
        sta task_bss_store+2
        bne task_clear_bss_count
task_clear_bss_pointer_ready:
        lda task_copy_store+1
        sta task_bss_store+1
        lda task_copy_store+2
        sta task_bss_store+2
task_clear_bss_count:
        lda TASK_BSS_LO
        sta task_remaining_lo
        lda TASK_BSS_HI
        sta task_remaining_hi
        lda #$00
task_clear_byte:
        ldx task_remaining_lo
        bne task_clear_store
        ldx task_remaining_hi
        beq task_copy_complete
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

task_copy_complete:
        lda task_load_mode
        beq task_enter
        lda #$00
        sta MMU_LCR_KERNEL_IO
        sta TASK_STATE
        sta TASK_ERROR
        tax
        rts

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
        sta USER_CC65_SP
        lda #>TASK_STACK_TOP
        sta USER_CC65_SP+1
        lda #$02
        sta TASK_STATE
        lda TASK_HEADER+14
        sta task_call_entry+1
        lda TASK_HEADER+15
        sta task_call_entry+2
        lda TASK_ARGC
        ldx TASK_ARGV_LO
        ldy TASK_ARGV_HI
task_call_entry:
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

; Synchronous disk preparation through the existing mount/read/close service.
; The request belongs to no running user task during compatibility EXEC;
; nevertheless restore all 38 bytes (including sequence) before returning.
; Bank-1 APP1 plus its first 16 stack bytes are private staging ONLY while
; task 2 is FREE. Live bank-0 APP1 is untouched until UDEX and EOF validate.
DISK_REQUEST = $f359
DISK_PAYLOAD = DISK_REQUEST+14
task_disk_open:
        ldx #37
task_disk_save_request:
        lda DISK_REQUEST,x
        sta task_disk_saved_request,x
        lda #0
        sta DISK_REQUEST,x
        dex
        bpl task_disk_save_request
        ldx #5
task_disk_request_header:
        lda task_disk_signature,x
        sta DISK_REQUEST,x
        dex
        bpl task_disk_request_header
        ldy #0
task_disk_path:
        ; Read argv text only while bank 0 is mapped.
        jsr task_disk_get_char
        sta DISK_PAYLOAD,y
        beq task_disk_path_end
        iny
        cpy #22
        bcc task_disk_path
task_disk_bad_path:
        lda #TASK_NOT_FOUND
        jmp task_disk_done
task_disk_path_end:
        sty DISK_REQUEST+10
        cpy #6
        bcc task_disk_bad_path
        ldx #4
task_disk_prefix:
        lda DISK_PAYLOAD,x
        cmp task_disk_mount,x
        bne task_disk_bad_path
        dex
        bpl task_disk_prefix
        lda #6                      ; OPEN
        jsr task_disk_request
        lda DISK_REQUEST+12
        beq task_disk_opened
        cmp #2                      ; ENOENT
        bne task_disk_io_unopened
        lda #TASK_NOT_FOUND
        jmp task_disk_done
task_disk_io_unopened:
        lda #TASK_IO_ERROR
        jmp task_disk_done
task_disk_opened:
        lda #4
        sta DISK_REQUEST+9
        lda #0
        sta task_file_size_lo
        sta task_file_size_hi
        sta task_disk_store+1
        lda #2
        sta task_disk_store+2
task_disk_read:
        lda #24
        sta DISK_REQUEST+10
        lda #1                      ; READ
        jsr task_disk_request
        lda DISK_REQUEST+12
        bne task_disk_io
        ldx DISK_REQUEST+11
        beq task_disk_eof
        lda #0
        sta MMU_LCR_WORKER_FLAT
        ldy #0
task_disk_byte:
        lda task_load_mode
        cmp #1
        beq task_disk_persistent_room
        lda task_disk_store+2
        cmp #$0c
        bne task_disk_room
        lda task_disk_store+1
        cmp #$10
        beq task_disk_overflow
        bne task_disk_room
task_disk_persistent_room:
        lda task_disk_store+2
        cmp #$12                    ; APP1 plus unused child stack, not service
        beq task_disk_overflow
task_disk_room:
        lda DISK_PAYLOAD,y
task_disk_store:
        sta $0200
        inc task_disk_store+1
        bne :+
        inc task_disk_store+2
:
        inc task_file_size_lo
        bne :+
        inc task_file_size_hi
:
        iny
        dex
        bne task_disk_byte
        lda #0
        sta MMU_LCR_KERNEL_IO
        jmp task_disk_read
task_disk_overflow:
        lda #TASK_BAD_SIZE
        bne task_disk_close
task_disk_io:
        lda #TASK_IO_ERROR
        bne task_disk_close
task_disk_eof:
        lda #0
task_disk_close:
        pha
        lda #0
        sta MMU_LCR_KERNEL_IO
        sta DISK_REQUEST+10
        lda #9                      ; CLOSE, even on overflow/read failure
        jsr task_disk_request
        pla
        bne task_disk_done
        lda DISK_REQUEST+12
        beq task_disk_done
        lda #TASK_IO_ERROR
task_disk_done:
        pha
        ldx #37
task_disk_restore_request:
        lda task_disk_saved_request,x
        sta DISK_REQUEST,x
        dex
        bpl task_disk_restore_request
        pla
        beq task_disk_downloaded
        jmp task_fail_kernel
task_disk_downloaded:
        lda task_file_size_hi
        bne :+
        lda task_file_size_lo
        cmp #16
        bcs :+
        jmp task_bad_size
:
        lda #0
        sta task_file_lo
        sta MMU_LCR_WORKER_FLAT
        lda #2
        sta task_file_hi
        jmp task_file_bounds_ready
task_disk_get_char:
        lda task_command_load+1
        sta task_disk_char+1
        lda task_command_load+2
        sta task_disk_char+2
task_disk_char:
        lda $ffff,y
        rts
task_disk_request:
        sta DISK_REQUEST+7
        lda #1
        sta DISK_REQUEST+6
        jmp $c880
task_disk_signature: .byte "UTRQ", 0, 5
task_disk_mount: .byte "/mnt/"
task_disk_leaf: .res 22, 0
task_disk_saved_request: .res 38, 0

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
task_load_mode:         .byte $00
task_saved_zp:          .res $1e, $00
; Storage requests reuse $F68A, where boot presentation left the one-shot
; scheduler activator. Preserve that still-live image until init installs it.
BOOT_ACTIVATION_SIZE = 42
boot_saved_activation:  .res BOOT_ACTIVATION_SIZE, 0

task_loader_end:
        .assert task_loader_end <= $fe80, error, "task loader reaches boot init gate"

; Private bootstrap gate. The C mount/file policy remains in the storage
; service; this mechanism only selects the initial persistent shell source.
; F910/F913/F916/F919 and every public request gate remain unchanged.
        .segment "BOOTINIT"
boot_shell_entry:
        .assert boot_shell_entry = $fe80, error, "boot shell gate moved"
        php
        sei
        ldx #BOOT_ACTIVATION_SIZE-1
boot_shell_save_activation:
        lda $f68a,x
        sta boot_saved_activation,x
        dex
        bpl boot_shell_save_activation
        lda #0
        sta MMU_LCR_WORKER_FLAT
        ldx #5
boot_shell_identity:
        lda task_lookup_bootfs+3,x
        cmp task_lookup_signature,x
        bne boot_shell_missing
        dex
        bpl boot_shell_identity
        jsr boot_shell_policy
boot_shell_return:
        sta MMU_LCR_KERNEL_IO
        tay
        ldx #BOOT_ACTIVATION_SIZE-1
boot_shell_restore_activation:
        lda boot_saved_activation,x
        sta $f68a,x
        dex
        bpl boot_shell_restore_activation
        tya
        plp
        cmp #0                      ; init tests Z after the call
        rts
boot_shell_missing:
        lda #3
        sta BOOT_SHELL_SOURCE
        lda #TASK_BAD_BOOTFS
        sta BOOT_SHELL_ERROR
        lda #1
        bne boot_shell_return
boot_shell_request:
        sta MMU_LCR_KERNEL_IO
        jsr task_disk_request
        lda DISK_REQUEST+12
        sta MMU_LCR_WORKER_FLAT
        rts
boot_shell_load:
        sta MMU_LCR_KERNEL_IO
        jsr task_load_persistent
        sta MMU_LCR_WORKER_FLAT
        rts
boot_shell_disk_name: .byte "/mnt/USH", 0
boot_shell_fallback_name: .byte "ush", 0
        .assert * <= $ff00, error, "boot shell gate crosses MMU register hole"

        .segment "TASKLOOKUP"
BOOT_SHELL_SOURCE = $f3dd
BOOT_SHELL_ERROR = $f3de
BOOT_SHELL_DEVICE = $f3df
boot_shell_policy:
        lda #0
        sta BOOT_SHELL_SOURCE
        sta BOOT_SHELL_ERROR
        ldx #37
boot_shell_clear_request:
        sta DISK_REQUEST,x
        dex
        bpl boot_shell_clear_request
        ldx #5
boot_shell_signature:
        lda task_disk_signature,x
        sta DISK_REQUEST,x
        dex
        bpl boot_shell_signature
        lda BOOT_CHAIN+20
        cmp #8
        bcc boot_shell_default_device
        cmp #12
        bcc boot_shell_device_ready
boot_shell_default_device:
        lda #8
boot_shell_device_ready:
        sta BOOT_SHELL_DEVICE
        sta DISK_PAYLOAD
        ldx #3
boot_shell_mount_path:
        lda task_disk_mount,x
        sta DISK_PAYLOAD+1,x
        dex
        bpl boot_shell_mount_path
        lda #5
        sta DISK_REQUEST+10
        lda #17                     ; temporary mount, before any task runs
        jsr boot_shell_request
        beq boot_shell_mounted
        lda #TASK_IO_ERROR
        sta BOOT_SHELL_ERROR
        bne boot_shell_fallback
boot_shell_mounted:
        lda #<boot_shell_disk_name
        ldx #>boot_shell_disk_name
        jsr boot_shell_load
        lda TASK_ERROR
        sta BOOT_SHELL_ERROR
        ; The loader closes its file and restores our request. Drop the
        ; temporary mount so later startup/user policy owns normal mounts.
        ldx #3
boot_shell_unmount_path:
        lda task_disk_mount,x
        sta DISK_PAYLOAD,x
        dex
        bpl boot_shell_unmount_path
        lda #4
        sta DISK_REQUEST+10
        lda #18
        jsr boot_shell_request
        beq :+
        lda #TASK_IO_ERROR
        sta BOOT_SHELL_ERROR
:
        lda BOOT_SHELL_ERROR
        bne boot_shell_fallback
        lda #1
        sta BOOT_SHELL_SOURCE
        lda #0
        tax
        rts
boot_shell_fallback:
        lda #2
        sta BOOT_SHELL_SOURCE
        lda #<boot_shell_fallback_name
        ldx #>boot_shell_fallback_name
        jsr boot_shell_load
        cmp #0
        beq boot_shell_complete
        ldx #3
        stx BOOT_SHELL_SOURCE
boot_shell_complete:
        rts
