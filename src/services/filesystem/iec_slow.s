; SPDX-License-Identifier: GPL-3.0-or-later
; Slow IEC controller for the C128 8502. This is storage-service code, not a
; resident-kernel/KERNAL dependency. One channel/transaction at a time.
;
; CIA2 PA0/1 also select the VIC bank. Every line write reads the live port
; and changes only PA3..5. A transfer may not run from a worker-flat profile.
; The output buffer is inverted: 1 pulls a serial line low. Inputs PA6/7
; read 1 when CLK/DATA are released. The protocol follows the original C128
; serial routine's slow-path handshakes, but all line waits are bounded.
; A receive byte masks IRQs from first CLK release through DATA acknowledge.

        .setcpu "6502"
        .export _udeks_iec_open_directory
        .export _udeks_iec_open_file
        .export _udeks_iec_prepare_file, _udeks_iec_open_status
        .export _udeks_iec_talk_file, _udeks_iec_untalk
        .export _udeks_iec_command
        .export _udeks_iec_filename
        .export _udeks_iec_filename_length
        .export _udeks_iec_read_byte
        .export _udeks_iec_close
        .export _udeks_iec_probe_phase
        .export _udeks_iec_probe_subphase
        .export _udeks_iec_probe_bus
        .export _udeks_iec_probe_lines
        .export _udeks_iec_probe_bits

        .ifdef UDEKS_IEC_WRITE
        .export _udeks_iec_listen_file, _udeks_iec_write_byte
        .export _udeks_iec_unlisten, _udeks_iec_finish
IEC_FILENAME_MAX = 22
        .else
IEC_FILENAME_MAX = 16
        .endif

CIA2_PRA       = $dd00
CIA2_DDRA      = $dd02
SPEED_REG      = $d030
ATN_OUT        = $08
CLK_OUT        = $10
DATA_OUT       = $20
CLK_IN         = $40
DATA_IN        = $80
IEC_OK         = $00
IEC_EOI        = $01
IEC_TIMEOUT    = $02
IEC_NO_DEVICE  = $03
IEC_BAD_STATE  = $04

        .segment "BSS"
iec_lines:      .res 1
iec_device:     .res 1
iec_secondary:  .res 1
iec_open:       .res 1
iec_pending:    .res 1       ; prepared channel 2 survives UNTALK/status reads
iec_defer:      .res 1
_udeks_iec_filename_length: .res 1
_udeks_iec_filename: .res IEC_FILENAME_MAX
iec_name_index: .res 1
iec_value:      .res 1
iec_eoi:        .res 1
_udeks_iec_probe_bits:
iec_bits:       .res 1
iec_status:     .res 1
iec_busy_rounds: .res 1
iec_saved_speed: .res 1
_udeks_iec_probe_phase: .res 1
_udeks_iec_probe_subphase: .res 1
_udeks_iec_probe_bus: .res 1
_udeks_iec_probe_lines: .res 1

        .ifdef UDEKS_STORAGE_MODULE
        .segment "IECCODE"
        .else
        .segment "CODE"
        .endif

; Only our three IEC output bits change. The read/modify/write is atomic
; against the VIC graphics gateway's own protected DD00 bank selection.
store_lines:
        php
        sei
        lda CIA2_PRA
        and #$c7
        ora iec_lines
        sta CIA2_PRA
        plp
        rts

release_bus:
        lda #$00
        sta iec_lines
        jmp store_lines

release_command:
        ; Commodore's UNLISTEN/UNTALK path releases ATN first, holds CLK
        ; low for a short turnaround, then releases CLK and DATA.
        jsr atn_high
        jsr delay_20us
        jsr delay_20us
        jsr delay_20us
        jsr clock_high
        jmp data_high

clock_low:
        lda iec_lines
        ora #CLK_OUT
        sta iec_lines
        jmp store_lines
clock_high:
        lda iec_lines
        and #$ef
        sta iec_lines
        jmp store_lines
data_low:
        lda iec_lines
        ora #DATA_OUT
        sta iec_lines
        jmp store_lines
data_high:
        lda iec_lines
        and #$df
        sta iec_lines
        jmp store_lines
atn_low:
        lda iec_lines
        ora #ATN_OUT
        sta iec_lines
        jmp store_lines
atn_high:
        lda iec_lines
        and #$f7
        sta iec_lines
        jmp store_lines

; Roughly 20us at 1 MHz. The service is deliberately slow-serial only.
delay_20us:
        ldx #$04
@again: dex
        bne @again
        rts
delay_1ms:
        ldx #$c8
@again: dex
        bne @again
        rts

; The initial listener-low wait is short; a drive processing OPEN may hold
; DATA low significantly longer before accepting the next command. All waits
; remain finite even if device 8 is unplugged.
; Return C=1 on timeout. No unbounded ATN, clock, or data spin exists.
wait_data_low:
        ldx #$40
@outer: ldy #$00
@inner: bit CIA2_PRA
        bpl @found
        dey
        bne @inner
        dex
        bne @outer
        sec
        rts
@found: clc
        rts
wait_data_high:
        lda #$08
        sta iec_busy_rounds
@round:
        ldx #$00
@outer: ldy #$00
@inner: bit CIA2_PRA
        bmi @found
        dey
        bne @inner
        dex
        bne @outer
        dec iec_busy_rounds
        bne @round
        sec
        rts
@found: clc
        rts
wait_clock_low:
        ldx #$40
@outer: ldy #$00
@inner: bit CIA2_PRA
        bvc @found
        dey
        bne @inner
        dex
        bne @outer
        sec
        rts
@found: clc
        rts
; Disk firmware may pause between BASIC-directory records while fetching the
; next sector. Only the start-of-byte handshake gets this larger bound; the
; eight clock edges within a byte keep the short bound above.
wait_clock_high_start:
        lda #$08
        sta iec_busy_rounds
@round: ldx #$00
@outer: ldy #$00
@inner: bit CIA2_PRA
        bvs @found
        dey
        bne @inner
        dex
        bne @outer
        dec iec_busy_rounds
        bne @round
        sec
        rts
@found: clc
        rts

; A=byte, C=1 if the last byte of a LISTEN data stream (EOI). Returns A=0
; on success, A=NO_DEVICE for absent listener, A=TIMEOUT otherwise.
send_byte:
        sta iec_value
        lda #$00
        rol a
        sta iec_eoi
        lda #$01
        sta _udeks_iec_probe_subphase
        jsr data_high
        jsr wait_data_low
        bcc @ready
        lda #IEC_NO_DEVICE
        rts
@ready: jsr clock_high
        inc _udeks_iec_probe_subphase
        jsr wait_data_high
        bcs @timeout
        lda iec_eoi
        beq @send
        ; The listener acknowledges EOI by briefly pulling DATA low when
        ; CLK has remained high beyond the inter-byte timeout.
        jsr wait_data_low
        bcs @timeout
        jsr wait_data_high
        bcs @timeout
@send: jsr clock_low
        inc _udeks_iec_probe_subphase
        lda #$08
        sta iec_bits
        ; Keep the eight bit edges together. The long listener-ready waits
        ; above and the inter-byte wait below leave IRQs enabled.
        php
        sei
@bit:  lsr iec_value
        bcs @one
        jsr data_low
        jmp @clock
@one:  jsr data_high
@clock:
        jsr clock_high
        jsr delay_20us
        jsr clock_low
        jsr data_high
        jsr delay_20us
        dec iec_bits
        bne @bit
        plp
        inc _udeks_iec_probe_subphase
        jsr wait_data_low
        bcs @timeout
        lda #IEC_OK
        rts
@timeout:
        lda CIA2_PRA
        sta _udeks_iec_probe_bus
        lda iec_lines
        sta _udeks_iec_probe_lines
        lda #IEC_TIMEOUT
        rts

; Start an ATN command sequence. Keep CLK low until the first command byte;
; this is the same slow-serial initial posture as the C128 KERNAL.
attention:
        ; Recovery may follow a timeout which already restored 2 MHz.
        ; Re-enter slow-serial timing without replacing the saved caller speed.
        lda SPEED_REG
        and #$fe
        sta SPEED_REG
        jsr clock_low
        jsr data_high
        jsr atn_low
        jsr delay_1ms
        rts

; A=device (8..11). No KERNAL calls and no resident state mutation.
_udeks_iec_open_directory:
        pha
        lda iec_open
        bne @already_open
        ldx #$00
        stx iec_secondary
        pla
        jmp open_common
@already_open:
        pla
        lda #IEC_BAD_STATE
        rts

; A=device, with a caller-filled PETSCII filename. Channel 2 is independent
; of the command channel and works for both PRG and SEQ file reads.
_udeks_iec_open_file:
        ldx #0
        stx iec_defer
        jmp prepare_file
_udeks_iec_prepare_file:
        ldx #1
        stx iec_defer
prepare_file:
        pha
        lda _udeks_iec_filename_length
        beq @bad_name
        cmp #IEC_FILENAME_MAX+1
        bcs @bad_name
        lda iec_open
        .ifdef UDEKS_IEC_WRITE
        ora iec_pending
        .endif
        bne @bad_name
        lda #$02
        sta iec_secondary
        pla
        jmp open_common
@bad_name:
        pla
        lda #IEC_BAD_STATE
        rts

open_common:
        cmp #$08
        bcs @at_least_8
        lda #IEC_BAD_STATE
        rts
@at_least_8:
        cmp #$0c
        bcc @valid_device
        lda #IEC_BAD_STATE
        rts
@valid_device:
        pha
        lda iec_open
        beq @new_transaction
        pla
        lda #IEC_BAD_STATE
        rts
@new_transaction:
        pla
        sta iec_device
        lda #$01
        sta _udeks_iec_probe_phase
        lda #$00
        sta iec_open
        lda SPEED_REG
        sta iec_saved_speed
        and #$fe              ; original C128 slow IEC uses 1 MHz
        sta SPEED_REG
        .ifdef UDEKS_IEC_WRITE
        ; Once OPEN has been attempted, cleanup must send CLOSE even if a
        ; later filename/UNLISTEN handshake times out. The drive may have
        ; accepted it. Keep the production read-only build byte-identical.
        lda iec_secondary
        beq :+
        lda #1
        sta iec_pending
:
        .endif
        lda CIA2_DDRA
        ora #$38
        sta CIA2_DDRA
        jsr release_bus
        jsr attention
        lda iec_device
        ora #$20              ; LISTEN
        clc
        jsr send_byte
        beq :+
        jmp @failed
:
        inc _udeks_iec_probe_phase
        lda iec_secondary
        ora #$f0              ; OPEN secondary channel
        clc
        jsr send_byte
        beq :+
        jmp @failed
:
        inc _udeks_iec_probe_phase
        jsr atn_high
        lda iec_secondary
        bne @file_name
        lda #$24              ; "$"
        sec                   ; last filename byte carries EOI
        jsr send_byte
        bne @failed
        jmp @name_done
@file_name:
        lda #$00
        sta iec_name_index
@name_loop:
        ldx iec_name_index
        lda _udeks_iec_filename,x
        inx
        cpx _udeks_iec_filename_length
        beq @last_name_byte
        clc
        jsr send_byte
        bne @failed
        inc iec_name_index
        bne @name_loop
@last_name_byte:
        sec
        jsr send_byte
        bne @failed
@name_done:
        inc _udeks_iec_probe_phase
        jsr attention
        lda #$3f              ; UNLISTEN
        clc
        jsr send_byte
        bne @failed
        inc _udeks_iec_probe_phase
        jsr release_command
        ; A listener needs to observe a released bus between command phases.
        ; The stock C128 release path leaves a settling gap before next ATN.
        jsr delay_1ms
        lda iec_secondary
        beq @start_talk
        lda #1
        sta iec_pending
        lda iec_defer
        beq @start_talk
        lda #IEC_OK
        rts
@start_talk:
        lda iec_secondary
        jmp talk_channel
@timeout:
        lda #IEC_TIMEOUT
@failed:
        sta iec_status
        jsr release_bus
        lda iec_saved_speed
        sta SPEED_REG
        lda iec_status
        rts

; The status stream is read while file channel 2 stays open, before TALK 2.
; DOS status interpretation is C policy, not part of this electrical driver.
_udeks_iec_open_status:
        lda #15
        bne talk_channel
_udeks_iec_talk_file:
        lda #2
talk_channel:
        pha
        jsr attention
        lda iec_device
        ora #$40              ; TALK
        clc
        jsr send_byte
        beq :+
        tax
        pla
        txa
        jmp @failed
:
        inc _udeks_iec_probe_phase
        pla
        ora #$60              ; selected secondary channel
        clc
        jsr send_byte
        bne @failed
        inc _udeks_iec_probe_phase
        jsr data_low
        jsr atn_high
        jsr clock_high
        jsr wait_clock_low
        bcs @timeout
        inc _udeks_iec_probe_phase
        lda #$01
        sta iec_open
        lda #IEC_OK
        rts
@timeout:
        lda #IEC_TIMEOUT
@failed:
        sta iec_status
        jsr release_bus
        lda iec_saved_speed
        sta SPEED_REG
        lda iec_status
        rts

; AX result: A=data, X=status. On EOI the returned data is still valid.
_udeks_iec_read_byte:
        lda iec_open
        bne @begin
        lda #$00
        ldx #IEC_BAD_STATE
        rts
@begin: lda #$00
        sta iec_eoi
        lda #$10
        sta _udeks_iec_probe_subphase
        ; C128 KERNAL ACPTR masks IRQs from the first clock release through
        ; the final DATA acknowledgement, not just during the eight bits.
        php
        sei
        jsr clock_high
        jsr wait_clock_high_start
        bcc @start_ok
        jmp @timeout
@start_ok:
        inc _udeks_iec_probe_subphase
        jsr data_high
        ; The drive's >200us CLK-high EOI gap is acknowledged by a short
        ; DATA-low pulse. Ordinary inter-byte gaps are shorter.
        ; This loop is leaner than the original C128 debounced loop. About
        ; 170us leaves room to recognize the drive's EOI gap before CLK
        ; falls for its final byte.
        ldx #$12
@eoi_wait:
        bit CIA2_PRA
        bvc @bits
        dex
        bne @eoi_wait
        jsr data_low
        jsr delay_20us
        jsr delay_20us
        jsr delay_20us
        jsr data_high
        lda #$01
        sta iec_eoi
        jsr wait_clock_low
        bcs @timeout
@bits: lda #$00
        sta iec_value
        lda #$08
        sta iec_bits
        lda #$12
        sta _udeks_iec_probe_subphase
@next: ldx #$40
@high_outer:
        ldy #$00
@high: lda CIA2_PRA
        asl a                 ; sample CLK and DATA atomically (N and C)
        bmi @sample
        dey
        bne @high
        dex
        bne @high_outer
        jmp @bit_timeout
@sample:
        ror iec_value
        ldx #$40
@low_outer:
        ldy #$00
@low:  bit CIA2_PRA
        bvc @low_seen
        dey
        bne @low
        dex
        bne @low_outer
        jmp @bit_timeout
@low_seen:
        dec iec_bits
        bne @next
        jsr data_low         ; byte accepted
        lda iec_eoi
        beq @return
        jsr delay_20us
        jsr data_high
@return:
        lda iec_value
        ldx iec_eoi
        plp
        rts
@bit_timeout:
@timeout:
        lda CIA2_PRA
        sta _udeks_iec_probe_bus
        lda iec_lines
        sta _udeks_iec_probe_lines
        lda #$00
        sta iec_open
        jsr release_bus
        lda iec_saved_speed
        sta SPEED_REG
        lda #$00
        ldx #IEC_TIMEOUT
        plp
        rts

_udeks_iec_close:
        lda iec_open
        ora iec_pending
        bne @active
        lda #IEC_BAD_STATE
        rts
@active: lda #$00
        sta iec_open
        sta iec_pending
        jsr attention
        lda #$5f              ; UNTALK
        clc
        jsr send_byte
        bne @failed
        jsr release_command
        jsr attention
        lda iec_device
        ora #$20              ; LISTEN
        clc
        jsr send_byte
        bne @failed
        lda iec_secondary
        ora #$e0              ; CLOSE selected channel
        clc
        jsr send_byte
        bne @failed
        jsr attention
        lda #$3f              ; UNLISTEN
        clc
        jsr send_byte
@failed:
        sta iec_status
        jsr release_bus
        lda iec_saved_speed
        sta SPEED_REG
        lda iec_status
        rts

; End TALK without closing the prepared file or restoring transaction speed.
_udeks_iec_untalk:
        lda #0
        sta iec_open
        jsr attention
        lda #$5f
        clc
        jsr send_byte
        sta iec_status
        jsr release_command
        lda iec_status
        rts

; Private DOS command bytes supplied by the storage service, not user input.
_udeks_iec_command:
        jsr attention
        lda iec_device
        ora #$20
        clc
        jsr send_byte
        bne @done
        lda #$6f
        clc
        jsr send_byte
        bne @done
        jsr atn_high
        lda #0
        sta iec_name_index
@byte: ldx iec_name_index
        lda _udeks_iec_filename,x
        inx
        cpx _udeks_iec_filename_length
        beq @last
        clc
        jsr send_byte
        bne @done
        inc iec_name_index
        bne @byte
@last: sec
        jsr send_byte
        bne @done
        jsr attention
        lda #$3f
        clc
        jsr send_byte
@done: sta iec_status
        jsr release_command
        lda iec_status
        rts

        .ifdef UDEKS_IEC_WRITE
; Prepared channel 2 remains owned across status reads and write chunks.
_udeks_iec_listen_file:
        lda iec_pending
        beq @bad
        lda iec_open
        bne @bad
        jsr attention
        lda iec_device
        ora #$20
        clc
        jsr send_byte
        bne @done
        lda #$62
        clc
        jsr send_byte
        bne @done
        jsr atn_high
        lda #IEC_OK
@done: rts
@bad:  lda #IEC_BAD_STATE
        rts

; cc65 fastcall uint16: AX. X=1 requests EOI on the final chunk byte.
_udeks_iec_write_byte:
        cpx #1
        jmp send_byte

_udeks_iec_unlisten:
        jsr attention
        lda #$3f
        clc
        jsr send_byte
        sta iec_status
        jsr release_command
        lda iec_status
        rts

_udeks_iec_finish:
        lda #0
        sta iec_open
        sta iec_pending
        jsr release_bus
        lda iec_saved_speed
        sta SPEED_REG
        rts
        .endif
