; SPDX-License-Identifier: GPL-3.0-or-later

        .export _kernel_bench_mmu, _kernel_bench_cia, _kernel_bench_vdc

SCRATCH     = $f160
MMU_CR      = $ff00
CIA1_DDRA   = $dc02
VDC_ADDRESS = $d600
VDC_DATA    = $d601
ITERATIONS  = 128

        .segment "CODE"

_kernel_bench_mmu:
        lda MMU_CR
        sta SCRATCH
        ldy #ITERATIONS
mmu_loop:
        lda SCRATCH
        sta MMU_CR
        cmp MMU_CR
        bne access_failed
        dey
        bne mmu_loop
        lda #<ITERATIONS
        ldx #>ITERATIONS
        rts

_kernel_bench_cia:
        lda CIA1_DDRA
        sta SCRATCH
        ldy #ITERATIONS
cia_loop:
        lda SCRATCH
        sta CIA1_DDRA
        cmp CIA1_DDRA
        bne access_failed
        dey
        bne cia_loop
        lda #<ITERATIONS
        ldx #>ITERATIONS
        rts

_kernel_bench_vdc:
        ldy #ITERATIONS
vdc_loop:
        ldx #$00
vdc_wait_address:
        lda VDC_ADDRESS
        bmi vdc_address_ready
        dex
        bne vdc_wait_address
        beq access_failed
vdc_address_ready:
        lda #$12                 ; update-address high register
        sta VDC_ADDRESS
        ldx #$00
vdc_wait_data:
        lda VDC_ADDRESS
        bmi vdc_data_ready
        dex
        bne vdc_wait_data
        beq access_failed
vdc_data_ready:
        lda VDC_DATA
        dey
        bne vdc_loop
        lda #<ITERATIONS
        ldx #>ITERATIONS
        rts

access_failed:
        lda #$00
        tax
        rts
