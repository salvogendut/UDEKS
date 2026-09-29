; SPDX-License-Identifier: GPL-3.0-or-later
;
; Fixed UDEKS control-port policy: a proportional 1351 mouse on physical
; control port 1 and a digital joystick on physical control port 2.

        .setcpu "6502"
        .export _udeks_control_ports_start
        .export _udeks_control_ports_sample
        .export _udeks_control_ports_active
        .export _udeks_control_joystick2
        .export _udeks_control_mouse1_buttons
        .export _udeks_control_mouse1_x
        .export _udeks_control_mouse1_y

CIA1_PRA                = $dc00
CIA1_PRB                = $dc01
CIA1_DDRA               = $dc02
CIA1_DDRB               = $dc03
SID_POTX                = $d419
SID_POTY                = $d41a

        .segment "BSS"
_udeks_control_joystick2:
        .res 1
_udeks_control_mouse1_buttons:
        .res 1
_udeks_control_mouse1_x:
        .res 1
_udeks_control_mouse1_y:
        .res 1
saved_pra:
        .res 1
saved_prb:
        .res 1
saved_ddra:
        .res 1
saved_ddrb:
        .res 1
active_switches:
        .res 1

        .segment "CODE"

_udeks_control_ports_start:
        ; PA6 high selects port-1 POT lines; PA7 low deselects port 2.
        ; PA0-PA5 remain inputs so the joystick cannot drive an output pin.
        lda CIA1_PRA
        and #$3f
        ora #$40
        sta CIA1_PRA
        lda #$c0
        sta CIA1_DDRA
        lda #$00
        sta CIA1_DDRB
        rts

_udeks_control_ports_sample:
        lda CIA1_PRA
        sta saved_pra
        and #$1f
        eor #$1f
        sta _udeks_control_joystick2
        lda CIA1_DDRA
        sta saved_ddra
        lda CIA1_DDRB
        sta saved_ddrb

        ; With both CIA ports inputs, a selected keyboard column cannot turn
        ; a key into a false mouse button (or vice versa).
        lda #$00
        sta CIA1_DDRA
        sta CIA1_DDRB
        lda CIA1_PRB
        eor #$ff
        and #$1f
        sta _udeks_control_mouse1_buttons

        ; These values were converted while the port-1 mux was stable during
        ; the pointer service's settling gate; read before restoring the pins.
        lda SID_POTX
        sta _udeks_control_mouse1_x
        lda SID_POTY
        sta _udeks_control_mouse1_y

        lda saved_pra
        sta CIA1_PRA
        lda saved_ddra
        sta CIA1_DDRA
        lda saved_ddrb
        sta CIA1_DDRB
        rts

_udeks_control_ports_active:
        ; Read each control port twice, with the opposite keyboard-matrix half
        ; driven high and then low. Keyboard-induced lows change with that
        ; drive level; a grounded control-port switch persists in both reads.
        lda CIA1_PRA
        sta saved_pra
        lda CIA1_PRB
        sta saved_prb
        lda CIA1_DDRA
        sta saved_ddra
        lda CIA1_DDRB
        sta saved_ddrb
        lda #$00
        sta CIA1_DDRA
        lda #$ff
        sta CIA1_PRB
        sta CIA1_DDRB
        lda CIA1_PRA
        eor #$ff
        and #$1f
        sta active_switches
        lda #$00
        sta CIA1_PRB
        lda CIA1_PRA
        eor #$ff
        and #$1f
        and active_switches
        sta active_switches
        bne restore_after_activity
        lda #$00
        sta CIA1_DDRB
        lda #$ff
        sta CIA1_PRA
        sta CIA1_DDRA
        lda CIA1_PRB
        eor #$ff
        and #$1f
        sta active_switches
        lda #$00
        sta CIA1_PRA
        lda CIA1_PRB
        eor #$ff
        and #$1f
        and active_switches
        sta active_switches
restore_after_activity:
        ; Return both halves to inputs before restoring their output latches,
        ; then restore the caller's directions.
        lda #$00
        sta CIA1_DDRA
        sta CIA1_DDRB
        lda saved_pra
        sta CIA1_PRA
        lda saved_prb
        sta CIA1_PRB
        lda saved_ddra
        sta CIA1_DDRA
        lda saved_ddrb
        sta CIA1_DDRB
        lda active_switches
        rts
