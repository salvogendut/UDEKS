; SPDX-License-Identifier: GPL-3.0-or-later
;
; Raster-paced native pointer driver.  A two-phase VIC-IIe interrupt first
; selects the port-1 POT pair, then samples it 26 raster lines later.  Motion
; is decoded in the IRQ itself, so synchronous graphics work cannot turn a
; delayed modulo-64 1351 reading into a reversed or lost movement.

        .setcpu "6502"

        .export _udeks_pointer_start
        .export _udeks_pointer_poll
        .export _udeks_pointer_resynchronize
        .export _udeks_pointer_keyboard_allowed
        .export _udeks_pointer_x
        .export _udeks_pointer_y
        .export _udeks_pointer_buttons
        .import _udeks_control_ports_active

PTR                     = $f1d0
IRQ_TRAMPOLINE          = $ffc5
IRQ_RETURN              = $f909

MMU_CR_ALWAYS           = $ff00
MMU_LCR_KERNEL_IO       = $ff01

CIA1_PRA                = $dc00
CIA1_PRB                = $dc01
CIA1_DDRA               = $dc02
CIA1_DDRB               = $dc03
CIA1_ICR                = $dc0d
CIA2_ICR                = $dd0d
SID_POTX                = $d419
SID_POTY                = $d41a
VIC_CONTROL_1           = $d011
VIC_RASTER              = $d012
VIC_IRQ_STATUS          = $d019
VIC_IRQ_MASK            = $d01a

RASTER_SELECT           = 200
RASTER_SAMPLE           = 226
JOYSTICK_STEP           = 5

X_MIN_LO                = <18
X_MIN_HI                = >18
X_MAX_LO                = <326
X_MAX_HI                = >326
Y_MIN                   = 45
Y_MAX                   = 234

        .segment "BSS"
old_pot_x:              .res 1
old_pot_y:              .res 1
joystick_candidate:     .res 1
warmup_samples:         .res 1
saved_pra:              .res 1
saved_prb:              .res 1
saved_ddra:             .res 1
saved_ddrb:             .res 1
active_switches:        .res 1
axis_current:           .res 1
mouse_dx:               .res 1
mouse_dy:               .res 1
total_dx:               .res 1
total_dy:               .res 1
new_x_lo:               .res 1
new_x_hi:               .res 1
source_flags:           .res 1
button_state:           .res 1

        .segment "CODE"

_udeks_pointer_start:
        sei
        lda #$00
        ldx #$1f
clear_status:
        sta PTR,x
        dex
        bpl clear_status
        lda #'P'
        sta PTR+0
        lda #'T'
        sta PTR+1
        lda #'R'
        sta PTR+2
        lda #'I'
        sta PTR+3
        lda #$01
        sta PTR+4
        sta PTR+5
        lda #$0f                ; mouse1, joystick2, 1351, raster-paced
        sta PTR+7
        lda #<172
        sta PTR+8
        lda #>172
        sta PTR+9
        lda #140
        sta PTR+10
        lda #$02
        sta warmup_samples

        ; Leave the keyboard matrix idle and select the port-1 POT inputs.
        lda CIA1_PRA
        and #$3f
        ora #$40
        sta CIA1_PRA
        lda #$c0
        sta CIA1_DDRA
        lda #$00
        sta CIA1_DDRB

        ; The common trampoline is visible in every bank/profile.  Its first
        ; PHA saves the interrupted A; the second saves the MMU profile.  A
        ; write to $FF01 selects kernel bank 0 with I/O before the long jump.
        ldx #irq_trampoline_end-irq_trampoline-1
copy_trampoline:
        lda irq_trampoline,x
        sta IRQ_TRAMPOLINE,x
        dex
        bpl copy_trampoline
        ldx #irq_return_stub_end-irq_return_stub-1
copy_return_stub:
        lda irq_return_stub,x
        sta IRQ_RETURN,x
        dex
        bpl copy_return_stub
        lda #<IRQ_TRAMPOLINE
        sta $fffe
        lda #>IRQ_TRAMPOLINE
        sta $ffff

        ; UDEKS owns maskable interrupts.  Remove inherited ROM timer sources
        ; and enable only the VIC raster source used by the input service.
        lda #$00
        sta VIC_IRQ_MASK
        lda #$0f
        sta VIC_IRQ_STATUS
        lda #$7f
        sta CIA1_ICR
        sta CIA2_ICR
        lda CIA1_ICR
        lda CIA2_ICR
        lda VIC_CONTROL_1
        and #$7f
        sta VIC_CONTROL_1
        lda #RASTER_SELECT
        sta VIC_RASTER
        lda #$01
        sta VIC_IRQ_MASK
        lda #$02
        sta PTR+5
        cli
        lda #$00
        rts

; Sampling and decoding happen in the ISR.  Poll remains an ABI lifecycle
; hook and reports success without making input latency depend on service work.
_udeks_pointer_poll:
        lda #$00
        rts

; The IRQ stream never stops during a repaint, so there is no stale baseline
; to discard after dragging.  Preserve this API for the window service.
_udeks_pointer_resynchronize:
        rts

_udeks_pointer_keyboard_allowed:
        php
        sei
        lda PTR+26
        bne keyboard_blocked
        ; Button and joystick edges are asynchronous and can arrive after the
        ; last raster sample.  Probe the CIA pins immediately before each
        ; keyboard scan so a fresh mouse click cannot become matrix input.
        jsr _udeks_control_ports_active
        beq keyboard_allowed
keyboard_blocked:
        plp
        lda #$00
        rts
keyboard_allowed:
        plp
        lda #$01
        rts

_udeks_pointer_x:
        php
        sei
        lda PTR+8
        ldx PTR+9
        plp
        rts

_udeks_pointer_y:
        lda PTR+10
        rts

_udeks_pointer_buttons:
        lda PTR+11
        rts

; Exactly eleven bytes: this occupies the reserved $FFC5-$FFCF common slot.
irq_trampoline:
        pha
        lda MMU_CR_ALWAYS
        pha
        sta MMU_LCR_KERNEL_IO
        jmp pointer_irq
irq_trampoline_end:
        .assert irq_trampoline_end-irq_trampoline = 11, error, "pointer IRQ trampoline size drift"

; Restoring a worker-bank profile makes the kernel handler disappear, so the
; final MMU write and RTI must also execute from common RAM.
irq_return_stub:
        sta MMU_CR_ALWAYS
        pla
        rti
irq_return_stub_end:
        .assert irq_return_stub_end-irq_return_stub = 5, error, "pointer IRQ return size drift"

pointer_irq:
        txa
        pha
        tya
        pha
        cld
        lda VIC_IRQ_STATUS
        and #$01
        bne raster_irq
        ; Ignore and clear any unexpected inherited CIA source without
        ; advancing the two-phase mouse sampler.
        lda CIA1_ICR
        lda CIA2_ICR
        jmp irq_return
raster_irq:
        lda #$01
        sta VIC_IRQ_STATUS
        lda PTR+26
        beq irq_select
        jmp irq_sample

irq_select:
        ; Read joystick 2 at both high and low drive levels on the opposite
        ; keyboard-matrix half.  A keyboard-induced low changes with that
        ; level; a grounded joystick switch persists in both samples.
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
        eor #$1f
        and #$1f
        sta active_switches
        lda #$00
        sta CIA1_PRB
        lda CIA1_PRA
        eor #$ff
        and #$1f
        and active_switches
        sta PTR+12
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

        ; Repurpose PA6/PA7 as the POT mux outputs for the settling window.
        lda CIA1_PRA
        and #$3f
        ora #$40
        sta CIA1_PRA
        lda CIA1_DDRA
        ora #$c0
        sta CIA1_DDRA
        lda #$01
        sta PTR+26
        lda #RASTER_SAMPLE
        sta VIC_RASTER
        jmp irq_return

irq_sample:
        lda #RASTER_SELECT
        sta VIC_RASTER
        lda #$00
        sta PTR+26

        ; Isolate the two CIA halves while sampling buttons, then restore the
        ; mux configuration established by irq_select.
        lda CIA1_PRA
        sta saved_pra
        lda CIA1_DDRA
        sta saved_ddra
        lda CIA1_DDRB
        sta saved_ddrb
        lda #$00
        sta CIA1_DDRA
        sta CIA1_DDRB
        lda CIA1_PRB
        eor #$ff
        and #$1f
        sta PTR+13
        lda SID_POTX
        sta PTR+14
        lda SID_POTY
        sta PTR+15
        lda saved_pra
        sta CIA1_PRA
        lda saved_ddra
        sta CIA1_DDRA
        lda saved_ddrb
        sta CIA1_DDRB

        lda warmup_samples
        beq decode_sample
        lda PTR+14
        sta old_pot_x
        lda PTR+15
        sta old_pot_y
        lda PTR+12
        sta joystick_candidate
        dec warmup_samples
        lda #$00
        sta PTR+11
        sta PTR+16
        sta PTR+17
        sta PTR+27
        ldx #18
        jsr increment_counter
        jmp irq_return

decode_sample:
        lda #$00
        sta source_flags
        sta button_state

        lda PTR+14
        ldx #$00
        jsr decode_axis
        sta mouse_dx
        sta total_dx
        lda PTR+15
        ldx #$01
        jsr decode_axis
        eor #$ff
        clc
        adc #$01
        sta mouse_dy
        sta total_dy

        lda PTR+13
        and #$10
        beq no_mouse_left
        lda button_state
        ora #$01
        sta button_state
no_mouse_left:
        lda PTR+13
        and #$01
        beq no_mouse_right
        lda button_state
        ora #$02
        sta button_state
no_mouse_right:
        lda mouse_dx
        ora mouse_dy
        ora button_state
        beq no_mouse_source
        lda source_flags
        ora #$01
        sta source_flags
        ldx #22
        jsr increment_counter
no_mouse_source:

        lda PTR+12
        cmp joystick_candidate
        beq joystick_stable
        sta joystick_candidate
        jmp joystick_done
joystick_stable:
        lda PTR+12
        and #$04
        beq joystick_not_left
        lda PTR+12
        and #$08
        bne joystick_horizontal_done
        lda total_dx
        sec
        sbc #JOYSTICK_STEP
        sta total_dx
        jmp joystick_horizontal_done
joystick_not_left:
        lda PTR+12
        and #$08
        beq joystick_horizontal_done
        lda total_dx
        clc
        adc #JOYSTICK_STEP
        sta total_dx
joystick_horizontal_done:
        lda PTR+12
        and #$01
        beq joystick_not_up
        lda PTR+12
        and #$02
        bne joystick_vertical_done
        lda total_dy
        sec
        sbc #JOYSTICK_STEP
        sta total_dy
        jmp joystick_vertical_done
joystick_not_up:
        lda PTR+12
        and #$02
        beq joystick_vertical_done
        lda total_dy
        clc
        adc #JOYSTICK_STEP
        sta total_dy
joystick_vertical_done:
        lda PTR+12
        and #$10
        beq joystick_no_fire
        lda button_state
        ora #$04
        sta button_state
joystick_no_fire:
        lda PTR+12
        beq joystick_done
        lda source_flags
        ora #$02
        sta source_flags
        ldx #24
        jsr increment_counter
joystick_done:

        lda total_dx
        sta PTR+16
        jsr apply_x_delta
        lda total_dy
        sta PTR+17
        jsr apply_y_delta
        lda button_state
        sta PTR+11
        lda source_flags
        sta PTR+27
        lda total_dx
        ora total_dy
        beq no_movement
        ldx #20
        jsr increment_counter
no_movement:
        ldx #18
        jsr increment_counter

irq_return:
        pla
        tay
        pla
        tax
        pla                     ; interrupted MMU profile
        jmp IRQ_RETURN

; A=current POT value, X=0 for X or 1 for Y.  Return signed modulo-64 delta.
decode_axis:
        sta axis_current
        sec
        sbc old_pot_x,x
        and #$7f
        cmp #$40
        bcs axis_negative
        lsr
        beq axis_zero
        pha
        lda axis_current
        sta old_pot_x,x
        pla
        rts
axis_negative:
        eor #$7f
        clc
        adc #$01
        lsr
        beq axis_zero
        pha
        lda axis_current
        sta old_pot_x,x
        pla
        eor #$ff
        clc
        adc #$01
axis_zero:
        rts

apply_x_delta:
        beq apply_x_done
        bmi apply_x_negative
        clc
        adc PTR+8
        sta new_x_lo
        lda PTR+9
        adc #$00
        sta new_x_hi
        cmp #X_MAX_HI
        bcc store_new_x
        bne clamp_x_max
        lda new_x_lo
        cmp #X_MAX_LO+1
        bcc store_new_x
clamp_x_max:
        lda #X_MAX_LO
        sta PTR+8
        lda #X_MAX_HI
        sta PTR+9
apply_x_done:
        rts
store_new_x:
        lda new_x_lo
        sta PTR+8
        lda new_x_hi
        sta PTR+9
        rts
apply_x_negative:
        eor #$ff
        clc
        adc #$01
        sta axis_current
        sec
        lda PTR+8
        sbc axis_current
        sta new_x_lo
        lda PTR+9
        sbc #$00
        sta new_x_hi
        bcc clamp_x_min
        bne store_new_x
        lda new_x_lo
        cmp #X_MIN_LO
        bcs store_new_x
clamp_x_min:
        lda #X_MIN_LO
        sta PTR+8
        lda #X_MIN_HI
        sta PTR+9
        rts

apply_y_delta:
        beq apply_y_done
        bmi apply_y_negative
        clc
        adc PTR+10
        bcs clamp_y_max
        cmp #Y_MAX+1
        bcc store_new_y
clamp_y_max:
        lda #Y_MAX
store_new_y:
        sta PTR+10
apply_y_done:
        rts
apply_y_negative:
        eor #$ff
        clc
        adc #$01
        sta axis_current
        sec
        lda PTR+10
        sbc axis_current
        bcc clamp_y_min
        cmp #Y_MIN
        bcs store_new_y
clamp_y_min:
        lda #Y_MIN
        sta PTR+10
        rts

increment_counter:
        inc PTR,x
        bne counter_done
        inc PTR+1,x
counter_done:
        rts
