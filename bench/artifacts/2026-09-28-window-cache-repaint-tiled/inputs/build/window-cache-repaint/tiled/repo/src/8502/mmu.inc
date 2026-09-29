; SPDX-License-Identifier: GPL-3.0-or-later
;
; Native memory constants mirrored by include/udeks/memory.h. Host tests keep
; the C and assembly representations synchronized.

MMU_CR_ALWAYS              = $ff00
MMU_PCR_KERNEL_IO          = $d501
MMU_PCR_KERNEL_FLAT        = $d502
MMU_PCR_WORKER_IO          = $d503
MMU_PCR_WORKER_FLAT        = $d504
MMU_MODE                   = $d505
MMU_RCR                    = $d506
MMU_PAGE0_PAGE             = $d507
MMU_PAGE0_BANK             = $d508
MMU_PAGE1_PAGE             = $d509
MMU_PAGE1_BANK             = $d50a

UDEKS_MMU_KERNEL_IO        = $3e
UDEKS_MMU_KERNEL_FLAT      = $3f
UDEKS_MMU_WORKER_IO        = $7e
UDEKS_MMU_WORKER_FLAT      = $7f
UDEKS_MMU_RCR_TOP_4K       = $09
UDEKS_C_STACK_TOP          = $eff0

BOOT_STATUS                = $f040
BOOT_STATUS_STATE          = BOOT_STATUS + 5
