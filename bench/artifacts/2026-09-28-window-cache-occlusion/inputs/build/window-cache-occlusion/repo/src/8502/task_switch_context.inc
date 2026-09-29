; SPDX-License-Identifier: GPL-3.0-or-later
;
; Private common-RAM handoff record shared by the switch tail and the
; bank-0 context table. This is not a public UDEX ABI.

TASK_SWITCH_CONTEXT       = $ffb9
TASK_SWITCH_CONTEXT_SIZE  = $0b

TASK_CTX_A                = $00
TASK_CTX_X                = $01
TASK_CTX_Y                = $02
TASK_CTX_P                = $03
TASK_CTX_SP               = $04
TASK_CTX_PC_LO            = $05
TASK_CTX_PC_HI            = $06
TASK_CTX_PAGE0_PAGE       = $07
TASK_CTX_PAGE0_BANK       = $08
TASK_CTX_PAGE1_PAGE       = $09
TASK_CTX_PAGE1_BANK       = $0a
