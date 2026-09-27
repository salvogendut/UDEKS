; SPDX-License-Identifier: GPL-3.0-or-later
;
; Fixed kernel entry vectors at $2000. The resident core starts after them.
; $2000 continues the boot into _kernel_main; $2003 is the boot-delivery
; gather entry called by the protected $F700 final installer before crt0.

        .setcpu "6502"
        .import _kernel_main
        .import _boot_delivery_gather
        .export _kernel_main_entry
        .export _boot_delivery_entry

        .segment "KERNELENTRY"
_kernel_main_entry:
        jmp _kernel_main
_boot_delivery_entry:
        jmp _boot_delivery_gather
        .assert _kernel_main_entry = $2000, error, "kernel entry vector moved"
        .assert _boot_delivery_entry = $2003, error, "boot delivery vector moved"
