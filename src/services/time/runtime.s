; SPDX-License-Identifier: GPL-3.0-or-later
; UAPP 0.1 / resident cc65 runtime zero-page contract. Code helpers link
; privately into the service; no private kernel code addresses are imported.
        .exportzp sp, sreg, regsave, ptr1, ptr2, ptr3, ptr4
        .exportzp tmp1, tmp2, tmp3, tmp4, regbank
sp = $06
sreg = $08
regsave = $0a
ptr1 = $0e
ptr2 = $10
ptr3 = $12
ptr4 = $14
tmp1 = $16
tmp2 = $17
tmp3 = $18
tmp4 = $19
regbank = $1a
        .export _udeks_time_status
_udeks_time_status = $f200
