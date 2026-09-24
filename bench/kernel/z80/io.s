; SPDX-License-Identifier: GPL-3.0-or-later

        .module kernel_io_z80
        .globl  _kernel_bench_mmu
        .globl  _kernel_bench_cia
        .globl  _kernel_bench_vdc

ITERATIONS = 128

        .area   _CODE

_kernel_bench_mmu::
        ld      a, (0xff00)
        ld      l, a
        ld      h, #ITERATIONS
mmu_loop:
        ld      a, l
        ld      (0xff00), a
        ld      a, (0xff00)
        cp      l
        jr      nz, access_failed
        dec     h
        jr      nz, mmu_loop
        ld      de, #ITERATIONS
        ret

_kernel_bench_cia::
        ld      bc, #0xdc02
        in      a, (c)
        ld      l, a
        ld      h, #ITERATIONS
cia_loop:
        ld      a, l
        out     (c), a
        in      a, (c)
        cp      l
        jr      nz, access_failed
        dec     h
        jr      nz, cia_loop
        ld      de, #ITERATIONS
        ret

_kernel_bench_vdc::
        ld      h, #ITERATIONS
vdc_loop:
        ld      bc, #0xd600
        ld      l, #0x00
vdc_wait_address:
        in      a, (c)
        bit     7, a
        jr      nz, vdc_address_ready
        dec     l
        jr      nz, vdc_wait_address
        jr      access_failed
vdc_address_ready:
        ld      a, #0x12         ; update-address high register
        out     (c), a
        ld      l, #0x00
vdc_wait_data:
        in      a, (c)
        bit     7, a
        jr      nz, vdc_data_ready
        dec     l
        jr      nz, vdc_wait_data
        jr      access_failed
vdc_data_ready:
        inc     c
        in      a, (c)
        dec     h
        jr      nz, vdc_loop
        ld      de, #ITERATIONS
        ret

access_failed:
        ld      de, #0x0000
        ret

        .area   _DATA
