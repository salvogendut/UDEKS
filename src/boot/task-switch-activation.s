; SPDX-License-Identifier: GPL-3.0-or-later
;
; Post-service-startup installer for the production task context binding and
; common-RAM switch tail. The checksum-protected boot-console installer copies
; this body directly to the disposable VIC gateway workspace at $F68A. It is
; therefore not callable until that final boot-only service has finished.
;
; This image is delivered but deliberately not invoked yet.  Enabling the
; call is coupled to the ABI 0.3 YIELD/resume contract: the legacy /bin/ush
; poll entry cannot run on the new persistent task stack.

        .setcpu "6502"
        .include "scheduler-overlay-delivery.inc"
MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_WORKER_FLAT     = $ff04

        .segment "ACTCOMMON"

        .export _udeks_task_switch_activate

_udeks_task_switch_activate:
activation_common:
        ; Copy the emitted context code/rodata.  The destination BSS is
        ; cleared separately, keeping this common body inside 48 bytes.
        ldy #TASK_ACTIVATION_CONTEXT_IMAGE_SIZE-1
copy_context:
        sta MMU_LCR_WORKER_FLAT
        lda TASK_ACTIVATION_CONTEXT_SOURCE,y
        sta MMU_LCR_KERNEL_IO
        sta TASK_ACTIVATION_CONTEXT_DESTINATION,y
        dey
        bpl copy_context

        lda #$00
        ldy #TASK_ACTIVATION_CONTEXT_BSS_SIZE-1
clear_context_bss:
        sta TASK_ACTIVATION_CONTEXT_BSS,y
        dey
        bpl clear_context_bss

        ldy #TASK_ACTIVATION_TAIL_SIZE-1
copy_switch_tail:
        sta MMU_LCR_WORKER_FLAT
        lda TASK_ACTIVATION_TAIL_SOURCE,y
        sta MMU_LCR_KERNEL_IO
        sta TASK_ACTIVATION_TAIL_DESTINATION,y
        dey
        bpl copy_switch_tail
        rts

activation_common_end:
        .assert TASK_ACTIVATION_CONTEXT_IMAGE_SIZE <= $ff, error, "context image needs a wider copier"
        .assert TASK_ACTIVATION_CONTEXT_BSS_SIZE <= $80, error, "context BSS exceeds branch range"
        .assert TASK_ACTIVATION_TAIL_SIZE <= $ff, error, "switch tail needs a wider copier"
        .assert activation_common = $f68a, error, "activation common run address moved"
        .assert activation_common_end-activation_common <= $30, error, "activation common body exceeds 48 bytes"
