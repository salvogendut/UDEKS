; SPDX-License-Identifier: GPL-3.0-or-later
; No bytes: enforce the UDEX header reservation against the actual C link.
        .import __BSS_SIZE__, __BSS_RUN__
        .assert __BSS_SIZE__ <= UDEKS_USH_BSS, lderror, "ush UDEX BSS reservation too small"
        .assert __BSS_RUN__+UDEKS_USH_BSS <= $a000, lderror, "ush reaches bootfs"
