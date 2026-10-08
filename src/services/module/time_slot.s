; SPDX-License-Identifier: GPL-3.0-or-later
; Candidate lifecycle core, not linked into normal boot yet. Runs only in
; serialized root/kernel-I/O context. No foreign pointers; one bounded slot.
; A=0 status/no-op, 1 begin, 2 commit, 3 stop; A=errno (0 on success).
; COMMIT additionally takes X/Y=received byte count (low/high), not a header
; claim. The disk loader must bound every write to [SLOT,LIMIT) itself.
; A separate disk loader fills the slot only between successful begin/commit.
        .setcpu "6502"
        .macpack longbranch
        .importzp ptr1, ptr2, ptr3, tmp1, tmp2, tmp3
        .import _udeks_service_start_phase, _udeks_service_start_result
        .export _udeks_time_slot_control, _udeks_time_slot_poll
        .export _udeks_time_slot_set, _udeks_time_slot_state
        ; Internal fixture binding, not a published syscall or service ABI.
        .ifdef UDEKS_TIME_SLOT_TEST
        .export time_slot_validate = validate
        .endif

SLOT = $9300
LIMIT = $96a8
CAPACITY = LIMIT-SLOT
TIME_STATE = $f205

        .segment "BSS"
_udeks_time_slot_state: .res 1       ; 0 offline, 1 loading, 2 published

        .segment "RODATA"
identity: .byte "USVM",0,1,4,1,<SLOT,>SLOT
descriptor: .byte "USVC",0,1,4,1,0,16

        .segment "CODE"
_udeks_time_slot_control:
        stx tmp1
        sty tmp2
        cmp #4
        bcs invalid
        tax
        lda _udeks_service_start_phase
        cmp #2
        bne not_ready
        lda _udeks_service_start_result
        bne not_ready
        txa
        beq success
        cmp #3
        beq stop
        lda _udeks_time_slot_state
        cmp #2
        beq busy
        cpx #1
        bne commit
        cmp #0
        bne busy
        lda #1
        sta _udeks_time_slot_state
        lda #0
        sta TIME_STATE             ; never present a stale READY snapshot
success:
        lda #0
        tax
        rts
invalid:
        lda #22
        rts
not_ready:
        lda #11
        rts
busy:
        lda #16
        rts
stop:
        lda _udeks_time_slot_state
        cmp #2
        bne offline
        jsr stop_entry
        pha
        jsr offline
        pla
        beq success
io_error:
        lda #5
        rts
offline:
        lda #0
        sta _udeks_time_slot_state
        sta TIME_STATE
        rts
commit:
        cmp #1
        bne invalid
        jsr validate
        bcc accepted
        jsr offline
        lda #8
        rts
accepted:
        ; Zero BSS after complete validation; ptr1=code end, ptr3=BSS end.
        ldy #0
clear_bss:
        lda ptr1
        cmp ptr3
        bne clear_byte
        lda ptr1+1
        cmp ptr3+1
        beq bss_ready
clear_byte:
        lda #0
        sta (ptr1),y
        inc ptr1
        bne clear_bss
        inc ptr1+1
        bne clear_bss
bss_ready:
        ; Cache only validated vectors. Later edits of image-header bytes
        ; cannot redirect poll, request or stop into unrelated memory.
        ldx #1
vectors:
        lda SLOT+20,x
        sta set_entry+1,x
        lda SLOT+42,x
        sta start_entry+1,x
        lda SLOT+44,x
        sta poll_entry+1,x
        lda SLOT+46,x
        sta stop_entry+1,x
        dex
        bpl vectors
        jsr start_entry
        bne failed_start
        lda #2
        sta _udeks_time_slot_state  ; publication LAST, only after start
        jmp success
failed_start:
        jsr offline
        jmp io_error

_udeks_time_slot_poll:
        lda _udeks_time_slot_state
        cmp #2
        jne success
        jsr poll_entry
        jeq success
        jsr offline
        lda #$80
        sta TIME_STATE             ; optional service failure is not panic
        jmp success
_udeks_time_slot_set:
        pha
        lda _udeks_time_slot_state
        cmp #2
        bne set_offline
        pla
        jmp set_entry
set_offline:
        pla
        lda #1                     ; legacy CF40 nonzero failure convention
        rts
start_entry: jmp $0000
poll_entry: jmp $0000
stop_entry: jmp $0000
set_entry: jmp $0000

; C clear = complete image accepted, C set = invalid. Never execute payload
; or change slot state during validation. The checksum is corruption
; detection, not authentication: all installed service code remains trusted.
validate:
        lda tmp1
        cmp SLOT+10
        jne bad_header
        lda tmp2
        cmp SLOT+11
        jne bad_header
        ldx #9
headers:
        lda SLOT,x
        cmp identity,x
        jne bad_header
        lda SLOT+32,x
        cmp descriptor,x
        jne bad_header
        dex
        bpl headers
        lda SLOT+14
        ora SLOT+15
        bne bad_header
        ldx #31
reserved:
        lda SLOT,x
        bne bad_header
        dex
        cpx #22
        bcs reserved
        lda SLOT+18
        ora SLOT+19
        beq bad_header
        ; Emitted size must exceed the 48-byte header.
        lda SLOT+10
        cmp #49
        lda SLOT+11
        sbc #0
        bcc bad_header
        ; Addition must not wrap and image+BSS must fit the reservation.
        clc
        lda SLOT+10
        adc SLOT+12
        sta tmp3
        lda SLOT+11
        adc SLOT+13
        bcs bad_header
        cmp #>CAPACITY
        bcc size_ok
        bne bad_header
        lda tmp3
        cmp #<(CAPACITY+1)
        bcs bad_header
size_ok:
        ; ptr3 = exclusive end of initialized image + zero BSS.
        clc
        lda SLOT+10
        adc #<SLOT
        sta ptr2
        lda SLOT+11
        adc #>SLOT
        sta ptr2+1
        clc
        lda ptr2
        adc SLOT+12
        sta ptr3
        lda ptr2+1
        adc SLOT+13
        sta ptr3+1
        ldx #20
        jsr vector
        bcs bad_header
        ldx #46
next_vector:
        jsr vector
        bcs bad_header
        dex
        dex
        cpx #42
        bcs next_vector
        jmp sum_begin
bad_header:
        sec
        rts
vector:
        lda SLOT+1,x
        cmp #>(SLOT+48)
        bcc vector_bad
        bne vector_upper
        lda SLOT,x
        cmp #<(SLOT+48)
        bcc vector_bad
vector_upper:
        lda SLOT+1,x
        cmp ptr2+1
        bcc vector_ok
        bne vector_bad
        lda SLOT,x
        cmp ptr2
        bcs vector_bad
vector_ok:
        clc
        rts
vector_bad:
        sec
        rts
sum_begin:
        lda #<SLOT
        sta ptr1
        lda #>SLOT
        sta ptr1+1
        lda #0
        sta tmp1
        sta tmp2
        tay
sum_loop:
        lda ptr1
        cmp ptr2
        bne sum_byte
        lda ptr1+1
        cmp ptr2+1
        beq sum_done
sum_byte:
        lda ptr1+1
        cmp #>SLOT
        bne add_byte
        lda ptr1
        cmp #<(SLOT+16)
        beq sum_next
        cmp #<(SLOT+17)
        beq sum_next
add_byte:
        clc
        lda (ptr1),y
        adc tmp1
        sta tmp1
        bcc sum_next
        inc tmp2
sum_next:
        inc ptr1
        bne sum_loop
        inc ptr1+1
        jmp sum_loop
sum_done:
        lda tmp1
        cmp SLOT+16
        bne vector_bad
        lda tmp2
        cmp SLOT+17
        bne vector_bad
        clc
        rts
