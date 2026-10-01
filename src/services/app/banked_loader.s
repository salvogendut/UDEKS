; SPDX-License-Identifier: GPL-3.0-or-later
; Private bank-1 allocation and native context mechanism. No UAPP callbacks.
; Enter/leave via $F91C under kernel I/O; this image runs under worker FLAT.
; A=3/4 loads a padded basename from UTRQ (count=17, length + 16 bytes).
; A=$43/$44 admits an ordinary (flags=0) image as native task 3/4.
; A=$83/$84 releases FREE, A=$C3/$C4 reaps a root-owned ZOMBIE and releases.
; Return A=errno, request preserved. Native return is EXIT through $FF16.
; Rejected files may dirty the FREE target but never publish its ownership.
        .setcpu "6502"
        .macpack longbranch
        .include "banked-bindings.inc"
        .export banked_entry, banked_owned, banked_headers, banked_end
        .segment "CODE"
REQUEST = $f359
PAYLOAD = REQUEST+14
IO_GATE = $f91f
MEMORY_GATE = $f922
        jmp banked_entry
        .byte "BLOD",0,1
current_task:
        lda #<BANK0_CURRENT
        ldy #>BANK0_CURRENT
        jsr read_address
        ldx #0
        jmp MEMORY_GATE
banked_entry:
        cld
        cmp #$10
        jeq graphics_install
        cmp #$20
        jeq transfer8
        cmp #$21
        jeq transfer8
        cmp #$30
        beq current_task
        sta selector
        and #$1f
        sec
        sbc #3
        cmp #2
        jcs invalid
        sta slot
        ; Both launcher child and selected native task must be FREE. Reap is
        ; the sole exception, and only accepts a root-owned zombie.
        lda #<(BANK0_SLOTS+1)
        ldy #>(BANK0_SLOTS+1)
        jsr read_address
        lda selector
        cmp #$63
        jeq query_state
        cmp #$64
        jeq query_state
        ldx #8                      ; task 2 (state-base + slot stride)
        jsr MEMORY_GATE
        jne busy
        lda slot
        asl
        asl
        asl
        clc
        adc #16                     ; task 3/4
        sta slot_offset
        tax
        jsr MEMORY_GATE
        sta live_state
        lda selector
        cmp #$c0
        jcs reap
        lda live_state
        jne busy
        lda selector
        jmi release
        and #$40
        jne activate
        ldx slot
        lda banked_owned,x
        jne busy
        lda REQUEST+10
        cmp #17
        jne invalid
        lda PAYLOAD
        jeq invalid
        cmp #17
        jcs invalid
        sta name_length
        ldx #0
check_name:
        lda PAYLOAD+1,x
        cpx name_length
        bcs check_padding
        cmp #'a'
        bcc not_lower
        cmp #'z'+1
        bcc name_ok
not_lower:
        cmp #'A'
        bcc not_upper
        cmp #'Z'+1
        bcc name_ok
not_upper:
        cmp #'0'
        bcc not_digit
        cmp #'9'+1
        bcc name_ok
not_digit:
        cmp #'_'
        beq name_ok
        cmp #'-'
        beq name_ok
        cmp #'.'
        bne invalid
        beq name_ok
check_padding:
        cmp #0
        bne invalid
name_ok:
        inx
        cpx #16
        bne check_name
        jmp load_image
query_state:
        lda slot
        asl
        asl
        asl
        clc
        adc #16
        tax
        jmp MEMORY_GATE
transfer8:
        ldx #$b9                    ; LDA abs,Y
        cmp #$20
        beq :+
        ldx #$99                    ; STA abs,Y
:       stx transfer_byte
        lda PAYLOAD
        sta transfer_byte+1
        lda PAYLOAD+1
        sta transfer_byte+2
        ldy #7
transfer_loop:
        lda PAYLOAD+2,y
transfer_byte:
        lda $ffff,y
        sta PAYLOAD+2,y
        dey
        bpl transfer_loop
        lda #0
        rts
graphics_install:
        lda #$0c
        sta install_page+1
        lda #$c7
        sta graphics_source+2
install_page:
        ldy #$0c
        lda #0
        jsr write_address
        ldx #0
graphics_source:
        lda $c700,x
        jsr MEMORY_GATE
        inx
        bne graphics_source
        inc graphics_source+2
        inc install_page+1
        lda install_page+1
        cmp #$12
        bne install_page
        lda #0
        rts
invalid:
        lda #22                     ; EINVAL
        rts
busy:
        lda #16                     ; EBUSY
        rts
release:
        jsr clear_metadata           ; also after a public WAITPID already reaped
        ldx slot
        lda #0
        sta banked_owned,x
        txa
        asl
        asl
        asl
        asl
        tax
        ldy #16
        lda #0
release_header:
        sta banked_headers,x
        inx
        dey
        bne release_header
        rts
load_image:
        ldx #37
save_request:
        lda REQUEST,x
        sta saved_request,x
        lda #0
        sta REQUEST,x
        dex
        bpl save_request
        ldx #5
request_header:
        lda signature,x
        sta REQUEST,x
        dex
        bpl request_header
        ldx #4
path_prefix:
        lda prefix,x
        sta PAYLOAD,x
        dex
        bpl path_prefix
        ldx #15
path_name:
        lda saved_request+15,x
        sta PAYLOAD+5,x
        dex
        bpl path_name
        lda name_length
        clc
        adc #5
        sta REQUEST+10
        lda #2                      ; OPEN_EXEC
        sta REQUEST+9
        lda #6
        jsr request
        lda REQUEST+12
        jne done
        ldx slot
        lda bases,x
        sta base
        sta store+2
        lda limits,x
        sta limit
        lda #0
        sta store+1
        sta file_size
        sta file_size+1
read:
        lda #4
        sta REQUEST+9
        lda #24
        sta REQUEST+10
        lda #1
        jsr request
        lda REQUEST+12
        jne close
        ldx REQUEST+11
        beq eof
        cpx #25
        bcs io_error
        ldy #0
read_byte:
        lda store+2
        cmp limit
        beq too_large
        lda PAYLOAD,y
store:  sta $ffff
        inc store+1
        bne :+
        inc store+2
:       inc file_size
        bne :+
        inc file_size+1
:       iny
        dex
        bne read_byte
        jmp read
io_error:
        lda #5                      ; EIO
        bne close
too_large:
        lda #12                     ; ENOMEM
        bne close
eof:
        lda #0
close:
        pha
        lda #4
        sta REQUEST+9
        lda #0
        sta REQUEST+10
        lda #9
        jsr request
        pla
        jne done
        lda REQUEST+12
        jne done
        jsr validate
        bne done
        jsr install
        ldx slot
        lda #1                      ; publish only after image + BSS complete
        sta banked_owned,x
        lda #0
done:
        pha
        ldx #37
restore_request:
        lda saved_request,x
        sta REQUEST,x
        dex
        bpl restore_request
        pla
        rts
request:
        sta REQUEST+7
        lda #1
        sta REQUEST+6
        jmp IO_GATE

validate:
        lda file_size+1
        bne :+
        lda file_size
        cmp #17                     ; header plus at least one instruction
        jcc bad_image
:       lda base
        sta header_read+2
        sta jump_read+2
        sta target_lo+2
        sta target_hi+2
        ldx #15
header_read:
        lda $ff00,x
        sta header,x
        dex
        bpl header_read
        ldx #4                      ; magic and major
magic:  lda header,x
        cmp udex,x
        jne bad_image
        dex
        bpl magic
        lda header+5
        cmp #2
        jcs bad_image
        lda header+6
        cmp #1
        jne bad_image
        lda header+7
        beq :+
        cmp #2                      ; retain old managed load-only validation
        jne bad_image
:       lda header+8
        jne bad_image
        lda header+9
        cmp base
        jne bad_image
        ; Exact EOF (header+image), reject overflow and truncated/trailing data.
        clc
        lda header+10
        adc #16
        sta allocation
        lda header+11
        adc #0
        jcs bad_image
        cmp file_size+1
        jne bad_image
        lda allocation
        cmp file_size
        jne bad_image
        lda header+10
        ora header+11
        jeq bad_image
        clc
        lda header+10
        adc header+12
        sta allocation
        lda header+11
        adc header+13
        jcs no_memory
        clc
        adc base
        jcs no_memory
        cmp limit
        jcc allocation_ok
        jne no_memory
        lda allocation
        jne no_memory
allocation_ok:
        clc
        lda header+11
        adc base
        sta image_end_hi
        lda header+15
        cmp base
        jcc bad_image
        cmp image_end_hi
        bcc entry_ok
        jne bad_image
        lda header+14
        cmp header+10
        jcs bad_image
entry_ok:
        lda header+7
        jeq valid_image
        lda header+14
        jne bad_image
        lda header+15
        cmp base
        jne bad_image
        lda header+11
        bne :+
        lda header+10
        cmp #19
        jcc bad_image
:       ldx #0
jump_read:
        lda $ff10,x
        cmp #$4c
        jne bad_image
target_lo:
        lda $ff11,x
        sta target
target_hi:
        lda $ff12,x
        cmp base
        jcc bad_image
        bne :+
        lda target
        cmp #18
        jcc bad_image
        lda base
:       cmp image_end_hi
        bcc jump_ok
        jne bad_image
        lda target
        cmp header+10
        jcs bad_image
jump_ok:
        inx
        inx
        inx
        cpx #18
        bne jump_read
valid_image:
        lda #0
        rts
bad_image:
        lda #8                      ; ENOEXEC
        rts
no_memory:
        lda #12
        rts
install:
        lda #16
        sta source+1
        lda #0
        sta destination+1
        lda base
        sta source+2
        sta destination+2
        lda header+10
        sta remaining
        lda header+11
        sta remaining+1
copy:   jsr more
        beq clear_setup
source: lda $ff10
destination:
        sta $ff00
        jsr advance_destination
        inc source+1
        bne copy
        inc source+2
        jmp copy
clear_setup:
        lda destination+1
        sta clear+1
        lda destination+2
        sta clear+2
        lda header+12
        sta remaining
        lda header+13
        sta remaining+1
clear_loop:
        jsr more
        beq save_header
        lda #0
clear:  sta $ffff
        inc clear+1
        bne clear_loop
        inc clear+2
        jmp clear_loop
save_header:
        lda slot
        asl
        asl
        asl
        asl
        tax
        ldy #0
header_copy:
        lda header,y
        sta banked_headers,x
        inx
        iny
        cpy #16
        bne header_copy
        rts
advance_destination:
        inc destination+1
        bne :+
        inc destination+2
:       rts
more:
        lda remaining
        ora remaining+1
        beq :+
        lda remaining
        bne decrement
        dec remaining+1
decrement:
        dec remaining
        lda #1
:       rts

; Only fixed, build-bound addresses are used with this private SMC gate.
; The outer gate holds IRQs masked until kernel mapping has been restored.
read_address:
        sta BANK0_ACCESS+1
        sty BANK0_ACCESS+2
        lda #$bd                    ; LDA abs,X
        sta BANK0_ACCESS
        rts
write_address:
        jsr read_address
        lda #$9d                    ; STA abs,X
        sta BANK0_ACCESS
        rts

activate:
        ldx slot
        lda banked_owned,x
        jeq invalid
        cmp #1
        jne busy                    ; a reaped process needs a fresh load
        txa
        asl
        asl
        asl
        asl
        tax
        lda banked_headers+7,x
        jne bad_image               ; bank-0 managed callbacks must never run
        lda banked_headers+14,x
        sta initial_context+5
        lda banked_headers+15,x
        sta initial_context+6
        ; Parent is explicitly root-session task 1, never inferred from the
        ; scheduler's last selected task. FREE/ZOMBIE cannot acquire children.
        ldx #0
        jsr MEMORY_GATE             ; still reads BANK0_SLOTS+1
        jeq invalid
        cmp #6
        jeq invalid
        ldx slot
        lda zero_pages,x
        sta clear_zero+2
        sta initial_context+7
        clc
        adc #1
        sta clear_stack+2
        sta initial_context+9
        sta stack_marker+2
        sta return_low+2
        sta return_high+2
        lda stack_pages,x
        sta guard_low+2
        clc
        adc #2
        sta stack_pointer+1
        sta guard_high+2
        sta exit_copy+2
        sta return_page
        sta return_signature+2
        sta return_stuck+2
        lda #<($c0+return_sig_data-return_code)
        sta return_signature+1
        lda #<($c0+return_stuck-return_code)
        sta return_stuck+1
        lda zero_pages,x
        sta stack_pointer_store+2
        sta stack_pointer_high_store+2
        ldy #0
        tya
clear_pages:
clear_zero:  sta $d500,y
clear_stack: sta $d600,y
        iny
        bne clear_pages
        lda #$a5
stack_marker: sta $d600
        ldy #15
guards:
guard_low: sta $8a00,y
guard_high: sta $8cb0,y
        dey
        bpl guards
        lda #$b0
        ldy #2
stack_pointer_store:
        sta $d500,y
        iny
stack_pointer:
        lda #$8c
stack_pointer_high_store:
        sta $d500,y
        lda #$bf
return_low: sta $d6fe
        lda return_page
return_high: sta $d6ff
        ldy #return_code_end-return_code-1
copy_exit:
        lda return_code,y
exit_copy: sta $8cc0,y
        dey
        bpl copy_exit
        jsr clear_metadata
        ldx slot
        lda context_offsets,x
        tax
        ldy #10
copy_context:
        lda initial_context,y
        jsr MEMORY_GATE             ; clear_metadata leaves context write address
        dex
        dey
        bpl copy_context
        lda #<BANK0_SLOTS
        ldy #>BANK0_SLOTS
        jsr write_address
        ldx slot
        lda #2
        sta banked_owned,x           ; active/exited, cannot be activated twice
        ldx slot_offset
        lda #1
        jsr MEMORY_GATE             ; parent
        inx
        inx
        inx
        jsr MEMORY_GATE             ; user flag, no persistent flag
        lda #<BANK0_EVENT
        ldy #>BANK0_EVENT
        jsr write_address
        ldx #0
        lda #2                      ; ADMIT
        jsr MEMORY_GATE
        lda #<BANK0_SLOTS
        ldy #>BANK0_SLOTS
        jsr write_address
        ldx slot_offset
        inx
        lda #2                      ; RUNNABLE is the publication commit byte
        jsr MEMORY_GATE
        lda #0
        rts

reap:
        lda live_state
        beq release_reaped          ; normal WAITPID may already have reaped it
        cmp #6
        jne busy
        ldx slot
        lda banked_owned,x
        jeq invalid
        ldx slot_offset
        dex
        jsr MEMORY_GATE             ; parent: read base is SLOTS+1
        cmp #1
        jne invalid
        lda #<BANK0_EVENT
        ldy #>BANK0_EVENT
        jsr write_address
        ldx #0
        lda #10                     ; REAP
        jsr MEMORY_GATE
release_reaped:
        jmp release

clear_metadata:
        lda #<BANK0_SLOTS
        ldy #>BANK0_SLOTS
        jsr write_address
        lda slot_offset
        clc
        adc #7
        tax
        ldy #8
        lda #0
clear_slot:
        jsr MEMORY_GATE
        dex
        dey
        bne clear_slot
        lda #<BANK0_WAITS
        ldy #>BANK0_WAITS
        jsr write_address
        lda slot
        clc
        adc #74                     ; last of ten arrays, task index 2/3
        tax
clear_wait:
        lda #0
        jsr MEMORY_GATE
        txa
        sec
        sbc #8
        tax
        bcs clear_wait
        lda #<BANK0_CONTEXTS
        ldy #>BANK0_CONTEXTS
        jsr write_address
        ldx slot
        lda context_offsets,x       ; offset of last of eleven context bytes
        tax
        ldy #11
        lda #0
clear_context:
        jsr MEMORY_GATE
        dex
        dey
        bne clear_context
        rts

return_code:
        sta PAYLOAD
        ldx #5
return_signature:
        lda $ffff,x                 ; signature lives in this client's tail
        sta REQUEST,x
        dex
        bpl return_signature
        lda #0
        sta REQUEST+9
        sta REQUEST+13
        lda #11
        sta REQUEST+7
        lda #1
        sta REQUEST+10
        sta REQUEST+6
        jsr $ff16
        ; EXIT never returns. If rejected, stay here without corrupting a peer.
return_stuck:
        jmp $ffff                   ; patched to this private trampoline
return_sig_data: .byte "UTRQ",0,8
return_code_end:
        .assert return_code_end-return_code <= $40, error, "native return exceeds private stack tail"

signature: .byte "UTRQ",0,8
prefix: .byte "/bin/"
udex: .byte "UDEX",0
bases: .byte $23,$35
limits: .byte $35,$40
banked_owned: .byte 0,0
banked_headers: .res 32,0
saved_request: .res 38,0
header: .res 16,0
selector: .byte 0
slot: .byte 0
name_length: .byte 0
base: .byte 0
limit: .byte 0
file_size: .word 0
allocation: .byte 0
image_end_hi: .byte 0
target: .byte 0
remaining: .word 0
slot_offset: .byte 0
live_state: .byte 0
return_page: .byte 0
zero_pages: .byte $d5,$d7
stack_pages: .byte $8a,$8d
context_offsets: .byte 32,43
initial_context: .byte 0,0,0,$24,$fd,0,0,$d5,1,$d6,1
banked_end:
        .assert banked_end <= $e000, error, "banked loader reaches storage state"
