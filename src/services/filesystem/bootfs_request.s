; SPDX-License-Identifier: GPL-3.0-or-later
;
; Bounded read-only bootfs directory service.  This code is installed in
; reclaimed common RAM so it can inspect the bank-1 bootfs without enlarging
; the resident microkernel or depending on a bank-private C runtime stack.

        .setcpu "6502"
        .macpack longbranch
        .segment "BOOTFSCODE"

        .export _udeks_bootfs_request

MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_WORKER_FLAT     = $ff04
BOOTFS_BASE             = $0800

TREQ_BASE               = $f359
TREQ_STATE              = TREQ_BASE+$06
TREQ_OPERATION          = TREQ_BASE+$07
TREQ_DESCRIPTOR         = TREQ_BASE+$09
TREQ_COUNT              = TREQ_BASE+$0a
TREQ_RESULT             = TREQ_BASE+$0b
TREQ_ERROR              = TREQ_BASE+$0c
TREQ_PAYLOAD            = TREQ_BASE+$0e

DIRECTORY_KIND          = $f3e8
DIRECTORY_OFFSET        = $f3e9
ENTRY_INDEX             = $f3ea
ENTRY_ADDRESS_LOW       = $f3eb
ENTRY_ADDRESS_HIGH      = $f3ec
CWD_KIND                = $f2a6

STATE_COMPLETE          = $02
STATE_ERROR             = $80
OP_OPEN                 = $06
OP_GETDENTS             = $07
OP_STAT                 = $08
OP_CLOSE                = $09
ERR_ENOENT              = $02
ERR_EBADF               = $09
ERR_EMFILE              = $18
ERR_ENOSYS              = $26
DT_DIR                  = $04
DT_REG                  = $08
DIRECTORY_FD            = $03

_udeks_bootfs_request:
        lda TREQ_OPERATION
        cmp #OP_OPEN
        beq request_open
        cmp #OP_GETDENTS
        beq request_getdents
        cmp #OP_STAT
        jeq request_stat
        cmp #OP_CLOSE
        jeq request_close
        lda #ERR_ENOSYS
        jmp finish_error

request_open:
        lda DIRECTORY_KIND
        beq open_path
        lda #ERR_EMFILE
        jmp finish_error
open_path:
        lda TREQ_COUNT
        cmp #$01
        bne open_check_bin
        lda TREQ_PAYLOAD
        cmp #'.'
        beq open_current
        cmp #'/'
        bne open_not_found
open_root:
        lda #$01
        bne open_ready
open_current:
        lda CWD_KIND
        beq open_root
        lda #$02
        bne open_ready
open_check_bin:
        cmp #$04
        bne open_not_found
        lda TREQ_PAYLOAD+0
        cmp #'/'
        bne open_not_found
        lda TREQ_PAYLOAD+1
        cmp #'b'
        bne open_not_found
        lda TREQ_PAYLOAD+2
        cmp #'i'
        bne open_not_found
        lda TREQ_PAYLOAD+3
        cmp #'n'
        bne open_not_found
        lda #$02
open_ready:
        sta DIRECTORY_KIND
        lda #$00
        sta DIRECTORY_OFFSET
        lda #DIRECTORY_FD
        jmp finish_ok
open_not_found:
        lda #ERR_ENOENT
        jmp finish_error

request_getdents:
        lda TREQ_DESCRIPTOR
        cmp #DIRECTORY_FD
        jne bad_descriptor
        lda DIRECTORY_KIND
        jeq bad_descriptor
        cmp #$01
        bne getdents_bin
        lda DIRECTORY_OFFSET
        jne getdents_eof
        inc DIRECTORY_OFFSET
        lda #DT_DIR
        sta TREQ_PAYLOAD+0
        lda #$03
        sta TREQ_PAYLOAD+1
        lda #'b'
        sta TREQ_PAYLOAD+2
        lda #'i'
        sta TREQ_PAYLOAD+3
        lda #'n'
        sta TREQ_PAYLOAD+4
        lda #$05
        jmp finish_ok
getdents_bin:
        lda #$00
        sta MMU_LCR_WORKER_FLAT
        lda DIRECTORY_OFFSET
        cmp BOOTFS_BASE+6
        bcs getdents_eof_worker
        jsr set_entry_address
        inc DIRECTORY_OFFSET
        clc
        lda ENTRY_ADDRESS_LOW
        adc #$01
        sta getdents_length+1
        lda ENTRY_ADDRESS_HIGH
        adc #$00
        sta getdents_length+2
        clc
        lda ENTRY_ADDRESS_LOW
        adc #$08
        sta getdents_name+1
        lda ENTRY_ADDRESS_HIGH
        adc #$00
        sta getdents_name+2
        lda #DT_REG
        sta TREQ_PAYLOAD+0
getdents_length:
        lda $ffff
        sta TREQ_PAYLOAD+1
        tax
        ldy #$00
getdents_copy_name:
getdents_name:
        lda $ffff,y
        sta TREQ_PAYLOAD+2,y
        iny
        dex
        bne getdents_copy_name
        tya
        clc
        adc #$02
        pha
        lda #$00
        sta MMU_LCR_KERNEL_IO
        pla
        jmp finish_ok
getdents_eof_worker:
        lda #$00
        sta MMU_LCR_KERNEL_IO
getdents_eof:
        lda #$00
        jmp finish_ok

request_stat:
        lda TREQ_COUNT
        cmp #$01
        bne stat_check_bin_directory
        lda TREQ_PAYLOAD
        cmp #'.'
        beq stat_directory
        cmp #'/'
        beq stat_directory
        bne stat_not_found_near
stat_check_bin_directory:
        cmp #$04
        bne stat_check_file
        lda TREQ_PAYLOAD+0
        cmp #'/'
        bne stat_not_found_near
        lda TREQ_PAYLOAD+1
        cmp #'b'
        bne stat_not_found_near
        lda TREQ_PAYLOAD+2
        cmp #'i'
        bne stat_not_found_near
        lda TREQ_PAYLOAD+3
        cmp #'n'
        bne stat_not_found_near
stat_directory:
        lda #DT_DIR
        sta TREQ_PAYLOAD+0
        lda #$00
        sta TREQ_PAYLOAD+1
        sta TREQ_PAYLOAD+2
        lda #$03
        jmp finish_ok
stat_not_found_near:
        jmp stat_not_found
stat_check_file:
        cmp #$06
        bcc stat_file_not_found_near
        lda TREQ_PAYLOAD+0
        cmp #'/'
        bne stat_file_not_found_near
        lda TREQ_PAYLOAD+1
        cmp #'b'
        bne stat_file_not_found_near
        lda TREQ_PAYLOAD+2
        cmp #'i'
        bne stat_file_not_found_near
        lda TREQ_PAYLOAD+3
        cmp #'n'
        bne stat_file_not_found_near
        lda TREQ_PAYLOAD+4
        cmp #'/'
        bne stat_file_not_found_near
        lda #$00
        sta ENTRY_INDEX
        sta MMU_LCR_WORKER_FLAT
        beq stat_next_entry
stat_file_not_found_near:
        jmp stat_not_found
stat_next_entry:
        lda ENTRY_INDEX
        cmp BOOTFS_BASE+6
        bcs stat_not_found_worker
        jsr set_entry_address
        clc
        lda ENTRY_ADDRESS_LOW
        adc #$01
        sta stat_length+1
        lda ENTRY_ADDRESS_HIGH
        adc #$00
        sta stat_length+2
stat_length:
        lda $ffff
        tax
        clc
        adc #$05
        cmp TREQ_COUNT
        bne stat_advance
        clc
        lda ENTRY_ADDRESS_LOW
        adc #$08
        sta stat_name+1
        lda ENTRY_ADDRESS_HIGH
        adc #$00
        sta stat_name+2
        ldy #$00
stat_compare_name:
        lda TREQ_PAYLOAD+5,y
stat_name:
        cmp $ffff,y
        bne stat_advance
        iny
        dex
        bne stat_compare_name
        clc
        lda ENTRY_ADDRESS_LOW
        adc #$04
        sta stat_size_low+1
        sta stat_size_high+1
        lda ENTRY_ADDRESS_HIGH
        adc #$00
        sta stat_size_low+2
        sta stat_size_high+2
        lda #DT_REG
        sta TREQ_PAYLOAD+0
stat_size_low:
        lda $ffff
        sta TREQ_PAYLOAD+1
        inc stat_size_high+1
        bne :+
        inc stat_size_high+2
:
stat_size_high:
        lda $ffff
        sta TREQ_PAYLOAD+2
        lda #$00
        sta MMU_LCR_KERNEL_IO
        lda #$03
        jmp finish_ok
stat_advance:
        inc ENTRY_INDEX
        jmp stat_next_entry
stat_not_found_worker:
        lda #$00
        sta MMU_LCR_KERNEL_IO
stat_not_found:
        lda #ERR_ENOENT
        jmp finish_error

request_close:
        lda TREQ_DESCRIPTOR
        cmp #DIRECTORY_FD
        bne bad_descriptor
        lda DIRECTORY_KIND
        beq bad_descriptor
        lda #$00
        sta DIRECTORY_KIND
        sta DIRECTORY_OFFSET
        beq finish_ok
bad_descriptor:
        lda #ERR_EBADF
        jmp finish_error

; A is a zero-based bootfs directory index.  Each record is 24 bytes and the
; first record begins at $0810.
set_entry_address:
        sta ENTRY_ADDRESS_LOW
        asl a
        clc
        adc ENTRY_ADDRESS_LOW
        asl a
        asl a
        asl a
        clc
        adc #$10
        sta ENTRY_ADDRESS_LOW
        lda #$08
        adc #$00
        sta ENTRY_ADDRESS_HIGH
        rts

finish_error:
        sta TREQ_ERROR
        lda #$00
        sta TREQ_RESULT
        lda #STATE_ERROR
        sta TREQ_STATE
        lda TREQ_ERROR
        rts
finish_ok:
        sta TREQ_RESULT
        lda #$00
        sta TREQ_ERROR
        lda #STATE_COMPLETE
        sta TREQ_STATE
        lda #$00
        rts

bootfs_request_end:
        .export _udeks_vic_buffer_restore
_udeks_vic_buffer_restore:
        ; Page commits borrow the first service page as their bank-crossing
        ; buffer, then restore it from the boot-time bank-1 backup.
        ldy #$00
restore_service_page:
        lda $4000,y
        sta $f400,y
        iny
        bne restore_service_page
        lda #$00
        sta MMU_LCR_KERNEL_IO
        rts

        .assert * <= $f68a, error, "bootfs service and restore gate exceed common reservation"
