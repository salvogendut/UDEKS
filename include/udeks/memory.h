/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_MEMORY_H
#define UDEKS_MEMORY_H

/* Physical RAM banks selected by MMU configuration-register bit 6. */
#define UDEKS_BANK_KERNEL             0x00u
#define UDEKS_BANK_WORKER             0x01u

/* Native boot and resident-image addresses. */
#define UDEKS_BOOT_SECTOR_BASE        0x0B00u
#define UDEKS_RECLAIMED_STATE_BASE    0x0C00u
#define UDEKS_RECLAIMED_STATE_LIMIT   0x1C00u
#define UDEKS_BOOTSTRAP_BASE          0x1C00u
#define UDEKS_KERNEL_BASE             0x2000u
#define UDEKS_KERNEL_LIMIT            0xD000u
#define UDEKS_IO_BASE                 0xD000u
#define UDEKS_IO_LIMIT                0xE000u
#define UDEKS_KERNEL_HIGH_BASE        0xE000u
#define UDEKS_KERNEL_HIGH_LIMIT       0xF000u
#define UDEKS_VIC_ROW_TABLE_BASE      0xE000u
#define UDEKS_VIC_ROW_TABLE_LIMIT     0xE190u
#define UDEKS_VIC_DIRTY_MAP_BASE      0xE190u
#define UDEKS_VIC_DIRTY_MAP_LIMIT     0xE1B0u
#define UDEKS_VIC_CLIP_STATE_BASE     0xE1B0u
#define UDEKS_VIC_CLIP_STATE_LIMIT    0xE1B8u
#define UDEKS_MODULE_HIGH_BSS_BASE    0xE1B8u
#define UDEKS_MODULE_HIGH_BSS_LIMIT   0xE300u
#define UDEKS_C_STACK_BOTTOM          0xE300u
#define UDEKS_C_STACK_TOP             0xEFF0u

/* Bank-1 resident worker and the initial VIC-visible 16 KiB reservation. */
#define UDEKS_Z80_CODE_BASE           0x2000u
#define UDEKS_Z80_CODE_LIMIT          0x4000u
#define UDEKS_VIC_WINDOW_BASE         0x4000u
#define UDEKS_VIC_WINDOW_LIMIT        0x8000u
#define UDEKS_Z80_STACK_TOP           0xEFF0u

/* Four KiB of bank-0 RAM shared at the top of every RAM-bank view. */
#define UDEKS_COMMON_BASE             0xF000u
#define UDEKS_COMMON_SIZE             0x1000u
#define UDEKS_COMMON_LIMIT            0x10000ul
#define UDEKS_BOOT_STATUS_BASE        0xF040u
#define UDEKS_BOOT_STATUS_SIZE        16u
#define UDEKS_BOOT_CHAIN_BASE         0xF050u
#define UDEKS_BOOT_CHAIN_SIZE         24u
#define UDEKS_GATEWAY_BASE            0xF800u
#define UDEKS_MMU_MIRROR_BASE         0xFF00u
#define UDEKS_MMU_MIRROR_LIMIT        0xFF05u
#define UDEKS_HANDOFF_BASE            0xFFD0u
#define UDEKS_VECTOR_BASE             0xFFFAu

/* MMU Configuration Register profiles. */
#define UDEKS_MMU_KERNEL_IO           0x3Eu
#define UDEKS_MMU_KERNEL_FLAT         0x3Fu
#define UDEKS_MMU_WORKER_IO           0x7Eu
#define UDEKS_MMU_WORKER_FLAT         0x7Fu

/* Four KiB common at the top; VIC initially observes RAM bank 0. */
#define UDEKS_MMU_RCR_TOP_4K          0x09u
#define UDEKS_MMU_RCR_VIC_BANK1       0x40u

#endif
