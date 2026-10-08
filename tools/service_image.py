#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded USVM 0.1 image contract for the first disk-service candidate.

This validates a complete image; it does not authorize arbitrary executable
code or install anything. Runtime registration is a separate integration gate.
"""
import struct

HEADER_SIZE = 48
TIME_BASE = 0x9300
TIME_LIMIT = 0x96A8


def checksum(data):
    return (sum(data[:16]) + sum(data[18:])) & 0xffff


def validate(data, *, base=TIME_BASE, limit=TIME_LIMIT, service_class=4,
             instance=1):
    if not 0 <= base < limit <= 0x10000:
        raise ValueError('invalid module reservation')
    if len(data) < HEADER_SIZE:
        raise ValueError('truncated service header')
    if data[:6] != b'USVM\x00\x01':
        raise ValueError('unsupported service image format')
    if data[6:8] != bytes((service_class, instance)):
        raise ValueError('service identity mismatch')
    address, size, bss, flags, expected, revision, request = struct.unpack_from('<7H', data, 8)
    if flags or any(data[22:32]):
        raise ValueError('reserved service image fields are nonzero')
    if not revision:
        raise ValueError('zero module revision')
    if address != base or size != len(data) or size <= HEADER_SIZE:
        raise ValueError('invalid service placement or emitted size')
    if size + bss > limit - base:
        raise ValueError('service image/BSS exceeds reservation')
    if data[32:42] != b'USVC\x00\x01' + bytes((service_class, instance, 0, 16)):
        raise ValueError('invalid loadable service descriptor')
    start, poll, stop = struct.unpack_from('<3H', data, 42)
    # This first candidate requires all lifecycle entries, plus its request
    # entry. No vector may target the header, BSS or a private kernel helper.
    for entry in (request, start, poll, stop):
        if not base + HEADER_SIZE <= entry < base + size:
            raise ValueError('service entry is outside emitted code')
    if checksum(data) != expected:
        raise ValueError('service checksum mismatch')
    return dict(base=base, image_size=size, bss_size=bss,
                allocation=size+bss, spare=limit-base-size-bss,
                revision=revision, request=request, start=start, poll=poll,
                stop=stop, checksum=expected)


def seal(data):
    image = bytearray(data)
    if len(image) < HEADER_SIZE:
        raise ValueError('truncated service header')
    struct.pack_into('<H', image, 16, checksum(image))
    validate(image)
    return bytes(image)
