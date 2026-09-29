; SPDX-License-Identifier: GPL-3.0-or-later
;
; Return the C128 bus to the resident 8502.  Execution resumes at RET when the
; next bounded worker lease begins.

        .module handoff
        .globl  _udeks_z80_yield

HANDOFF_GATEWAY = 0xffd0

        .area   _CODE
_udeks_z80_yield::
        jp      HANDOFF_GATEWAY
