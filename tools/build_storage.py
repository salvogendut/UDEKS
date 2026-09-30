#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add the private bank-1 IEC service to the existing secondary boot file."""
from __future__ import annotations

ROUTER = 0xC880
BOOTFS_BASE = 0xA000
BOOTFS_LIMIT = 0xD100


def install_router(tail: bytes, start: int, bss_end: int, router: bytes) -> bytes:
    if bss_end >= ROUTER or len(tail) > ROUTER - start:
        raise ValueError('scheduler code/BSS reaches storage router')
    if not router or len(router) > 0x80:
        raise ValueError('storage router exceeds $C880-$C8FF')
    return tail.ljust(ROUTER - start, b'\0') + router


def wrap_storage(payload: bytes, constants: str, module: bytes,
                 policy: bytes, driver: bytes, ush: bytes) -> tuple[bytes, str]:
    start = int.from_bytes(payload[:2], 'little')
    end = start + len(payload) - 2
    if start not in (0x4200, 0x5000) or end > 0x8000:
        raise ValueError('unexpected cache/scheduler envelope')
    if not module or len(module) > 0xE00 or module[3:9] != b'UIEC\x00\x01':
        raise ValueError('invalid $1200 storage module')
    if not policy or len(policy) > 0x600 or not driver or len(driver) > 0x600:
        raise ValueError('storage policy/driver exceeds its bank-1 hole')
    # ush's UDEX reserves $50 BSS bytes after the image (not just linked BSS).
    if not ush or len(ush) + 0x50 > 0xA00:
        raise ValueError('ush reaches the storage driver at $9A00')
    load = 0x1200
    # Reserved in the common envelope; build_d71 fills it with the selected
    # bootfs (normal or a test-specific ush) without changing LOAD bounds.
    limit = BOOTFS_LIMIT
    image = bytearray(limit - load)
    for address, data in ((load, module), (start, payload[2:]),
                          (0x8A00, policy), (0x9A00, driver)):
        image[address-load:address-load+len(data)] = data
    # Keep SCHEDULER_OVERLAY_END as the USOV source end: activation uses it.
    constants += (f'SECONDARY_PAYLOAD_LOAD = ${load:04x}\n'
                  f'SECONDARY_PAYLOAD_END = ${limit:04x}\n')
    return load.to_bytes(2, 'little') + image, constants


def install_bootfs(payload: bytes, bootfs: bytes) -> bytes:
    if len(payload) != 2 + BOOTFS_LIMIT - 0x1200 or payload[:2] != b'\0\x12':
        raise ValueError('secondary bootfs requires the $1200-$D0FF envelope')
    if payload[5:11] != b'UIEC\0\1':
        raise ValueError('secondary bootfs lacks the storage service identity')
    offset = 2 + BOOTFS_BASE - 0x1200
    if any(payload[offset:]):
        raise ValueError('secondary bootfs reservation is not empty')
    if len(bootfs) < 16 or bootfs[:6] != b'UBFS\0\1' or len(bootfs) > BOOTFS_LIMIT-BOOTFS_BASE:
        raise ValueError('secondary bootfs has invalid header or exceeds $A000-$D0FF')
    if int.from_bytes(bootfs[12:14], 'little') != len(bootfs):
        raise ValueError('secondary bootfs size does not match header')
    return payload[:offset] + bootfs.ljust(BOOTFS_LIMIT-BOOTFS_BASE, b'\0')
