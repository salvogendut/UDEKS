; SPDX-License-Identifier: GPL-3.0-or-later
;
; Post-service-startup installer for the production task context binding and
; common-RAM switch tail. The checksum-protected boot-console installer copies
; this body directly to the disposable VIC gateway workspace at $F68A. It is
; therefore not callable until that final boot-only service has finished.
;
; The scheduler bootstrap tail-calls this image after service startup. It
; installs the ABI 0.3 YIELD/resume path and initializes persistent /bin/ush
; on its relocated page zero and page one.

        .setcpu "6502"
        .include "scheduler-overlay-delivery.inc"
MMU_LCR_KERNEL_IO       = $ff01
MMU_LCR_WORKER_FLAT     = $ff04

        .segment "ACTCOMMON"

        .export _udeks_task_switch_activate

_udeks_task_switch_activate:
activation_common:
        ; Copy the emitted context code/rodata. The reset callback clears its
        ; BSS, so no separate clear loop is required here.
        ldy #$00
copy_context:
        sta MMU_LCR_WORKER_FLAT
        lda TASK_ACTIVATION_CONTEXT_SOURCE,y
        sta MMU_LCR_KERNEL_IO
        sta TASK_ACTIVATION_CONTEXT_DESTINATION,y
        iny
        cpy #TASK_ACTIVATION_CONTEXT_IMAGE_SIZE
        bne copy_context

        ldy #$00
copy_switch_tail:
        sta MMU_LCR_WORKER_FLAT
        lda TASK_ACTIVATION_TAIL_SOURCE,y
        sta MMU_LCR_KERNEL_IO
        sta TASK_ACTIVATION_TAIL_DESTINATION,y
        iny
        cpy #TASK_ACTIVATION_TAIL_SIZE
        bne copy_switch_tail

        ; Replace the scheduler's retired one-shot bootstrap prefix only after
        ; it tail-calls this common body. The fixed vectors at $1FFA survive.
        ldy #TASK_ACTIVATION_YIELD_SIZE-1
copy_yield_handler:
        sta MMU_LCR_WORKER_FLAT
        lda TASK_ACTIVATION_YIELD_SOURCE,y
        sta MMU_LCR_KERNEL_IO
        sta TASK_ACTIVATION_YIELD_DESTINATION,y
        dey
        bpl copy_yield_handler

        ; Initialize context records and relocated task pages through the new
        ; fixed reset vector, then return directly to init_start.
        jsr $ff10
        rts

activation_common_end:
        .assert TASK_ACTIVATION_CONTEXT_IMAGE_SIZE <= $ff, error, "context image needs a wider copier"
        .assert TASK_ACTIVATION_CONTEXT_BSS_SIZE <= $80, error, "context BSS exceeds branch range"
        .assert TASK_ACTIVATION_TAIL_SIZE <= $ff, error, "switch tail needs a wider copier"
        .assert TASK_ACTIVATION_YIELD_SIZE <= $ff, error, "YIELD handler needs a wider copier"
        .assert activation_common = $f68a, error, "activation common run address moved"
        .assert activation_common_end-activation_common <= $3e, error, "activation common body exceeds 62 bytes"
