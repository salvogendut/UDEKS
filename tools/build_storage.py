#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add the private bank-1 IEC service to the existing secondary boot file."""
from __future__ import annotations

ROUTER = 0xC880
BOOTFS_BASE = 0xA000
BOOTFS_LIMIT = 0xB000
POLICY_BASE = 0xB000
POLICY_SIZE = 0x2000
DRIVER_BASE = 0xE300
SECONDARY_LIMIT = 0xE900
USH_BSS = 0x170
BANKED_LOADER_BASE = 0xD900
BANKED_LOADER_LIMIT = 0xE000


def install_router(tail: bytes, start: int, bss_end: int, router: bytes) -> bytes:
    if bss_end >= ROUTER or len(tail) > ROUTER - start:
        raise ValueError('scheduler code/BSS reaches storage router')
    if not router or len(router) > 0x80:
        raise ValueError('storage router exceeds $C880-$C8FF')
    return tail.ljust(ROUTER - start, b'\0') + router


def wrap_storage(payload: bytes, constants: str, module: bytes,
                 policy: bytes, driver: bytes, ush: bytes,
                 lookup: bytes, banked_loader: bytes = b'',
                 banked_graphics: bytes = b'', banked_reloc: bytes = b'',
                 banked_access: bytes = b'', retained_paths: bytes = b'') -> tuple[bytes, str]:
    start = int.from_bytes(payload[:2], 'little')
    end = start + len(payload) - 2
    if start not in (0x4200, 0x5000) or end > 0x8000:
        raise ValueError('unexpected cache/scheduler envelope')
    if not module or len(module) > 0x800 or module[3:9] != b'UIEC\x00\x01':
        raise ValueError('invalid $1200 storage module')
    if not lookup or len(lookup) > 0x600 or lookup[3:9] != b'ULKP\0\1':
        raise ValueError('loader lookup exceeds $1A00-$1FFF')
    if not policy or len(policy) > POLICY_SIZE or not driver or len(driver) > 0x600:
        raise ValueError('storage policy/driver exceeds its bank-1 hole')
    if not ush or len(ush) + USH_BSS > 0x1000:
        raise ValueError('ush reaches bootfs at $A000')
    load = 0x1200
    # Reserved in the common envelope; build_d71 fills it with the selected
    # bootfs (normal or a test-specific ush) without changing LOAD bounds.
    limit = SECONDARY_LIMIT
    image = bytearray(limit - load)
    for address, data in ((load, module), (0x1A00, lookup), (start, payload[2:]),
                          (POLICY_BASE, policy), (DRIVER_BASE, driver)):
        image[address-load:address-load+len(data)] = data
    if banked_loader:
        if (len(banked_loader) > BANKED_LOADER_LIMIT - BANKED_LOADER_BASE or
                banked_loader[3:9] != b'BLOD\0\1' or banked_loader[0] != 0x4C):
            raise ValueError('invalid banked loader at $D900-$DFFF')
        first, last = BANKED_LOADER_BASE-load, BANKED_LOADER_LIMIT-load
        if any(image[first:last]):
            raise ValueError('banked loader reservation is occupied')
        image[first:first+len(banked_loader)] = banked_loader
    if retained_paths:
        if len(banked_graphics) != 0x600 or len(retained_paths) != 0x3F0 or len(policy) > 0x1600:
            raise ValueError('graphics/path delivery requires $C600-$CFFF free from policy')
        first, last = 0xC600-load, 0xD000-load
        if any(image[first:last]):
            raise ValueError('graphics/path delivery overlaps live data')
        image[first:first+0x600] = banked_graphics
        image[first+0x600:first+0x9F0] = retained_paths
    elif banked_graphics:  # Accept archived pre-paths envelope fixtures.
        if len(banked_graphics) != 0x600 or len(policy) > 0x1700:
            raise ValueError('banked graphics requires $C700-$CFFF free from policy')
        first, last = 0xC700-load, 0xD000-load
        if any(image[first:last]):
            raise ValueError('banked graphics staging/retained images overlap live data')
        image[first:first+0x600] = banked_graphics
    if banked_reloc or banked_access:
        if not banked_loader or len(module)>0x680 or len(lookup)>0x500:
            raise ValueError('relocation requires storage/lookup within their reduced reservations')
        for address,capacity,blob,magic in ((0x1880,0x180,banked_reloc,b'BREL\0\1'),
                                          (0x1f00,0x100,banked_access,b'BACC\0\1')):
            if not 9<len(blob)<=capacity or blob[0]!=0x4c or blob[3:9]!=magic:
                raise ValueError('invalid banked relocation/access module')
            first,last=address-load,address-load+capacity
            if any(image[first:last]):
                raise ValueError('banked relocation/access overlaps live delivery')
            image[first:first+len(blob)]=blob
    # Keep SCHEDULER_OVERLAY_END as the USOV source end: activation uses it.
    constants += (f'SECONDARY_PAYLOAD_LOAD = ${load:04x}\n'
                  f'SECONDARY_PAYLOAD_END = ${limit:04x}\n')
    return load.to_bytes(2, 'little') + image, constants


def install_bootfs(payload: bytes, bootfs: bytes) -> bytes:
    if len(payload) != 2 + SECONDARY_LIMIT - 0x1200 or payload[:2] != b'\0\x12':
        raise ValueError('secondary bootfs requires the $1200-$E8FF envelope')
    if payload[5:11] != b'UIEC\0\1':
        raise ValueError('secondary bootfs lacks the storage service identity')
    offset = 2 + BOOTFS_BASE - 0x1200
    end = 2 + BOOTFS_LIMIT - 0x1200
    if any(payload[offset:end]):
        raise ValueError('secondary bootfs reservation is not empty')
    if len(bootfs) < 16 or bootfs[:6] != b'UBFS\0\1' or len(bootfs) > BOOTFS_LIMIT-BOOTFS_BASE:
        raise ValueError('secondary bootfs has invalid header or exceeds $A000-$AFFF')
    if int.from_bytes(bootfs[12:14], 'little') != len(bootfs):
        raise ValueError('secondary bootfs size does not match header')
    return payload[:offset] + bootfs.ljust(BOOTFS_LIMIT-BOOTFS_BASE, b'\0') + payload[end:]
