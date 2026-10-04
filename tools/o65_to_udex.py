#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert linker-authored o65 relocations to bounded, page-relocatable UDEX 0.2.

No address scanning or binary-difference inference. Only contiguous 6502
text/data/BSS, fixed private ZP, no dynamic imports, and page-aligned moves.
See abi/executable.md. The reference relocator is also used by qualification.
"""
import argparse
from pathlib import Path
import struct
from build_udex import build_executable
from gen_capability_imports import map_exports

CANONICAL_BASE = 0x1000


class Reader:
    def __init__(self, data): self.data, self.position = data, 0
    def take(self, size):
        end = self.position + size
        if end > len(self.data): raise ValueError('truncated o65 stream')
        result = self.data[self.position:end]; self.position = end
        return result
    def byte(self): return self.take(1)[0]
    def word(self): return int.from_bytes(self.take(2), 'little')


def pack_o65(data, entry):
    reader = Reader(data)
    if reader.take(6) != b'\x01\x00o65\0' or reader.word() != 0x0800:
        raise ValueError('requires ld65 small 6502 byte-relocation o65')
    base, text_size, data_base, data_size, bss_base, bss, zp, zp_size, stack = (
        reader.word() for _ in range(9))
    size = text_size + data_size
    if (base != CANONICAL_BASE or not text_size or data_base != base+text_size or
            bss_base != base+size or base+size+bss > 0x10000 or
            zp != 2 or zp_size > 30 or stack):
        raise ValueError('noncontiguous segments, incompatible ZP/stack, or invalid allocation')
    while True:
        length = reader.byte()
        if not length: break
        if length < 2: raise ValueError('invalid o65 option length')
        reader.take(length-1)  # timestamps/filenames are not executable data
    image = reader.take(size)
    if reader.word(): raise ValueError('dynamic o65 imports are not supported')
    patches = []
    for segment_offset, segment_size in ((0, text_size), (text_size, data_size)):
        address, occupied, escaping = -1, set(), False
        while True:
            delta = reader.byte()
            if delta == 0:
                if escaping: raise ValueError('unfinished relocation offset escape')
                break
            if delta == 255:
                address += 254; escaping = True
                continue
            address += delta; escaping = False
            descriptor = reader.byte()
            kind, target = descriptor & 0xe0, descriptor & 7
            if descriptor & 0x18 or kind not in (0x20, 0x40, 0x80) or target not in (1,2,3,4,5):
                raise ValueError('unsupported o65 relocation')
            width = 2 if kind == 0x80 else 1
            if address < 0 or address+width > segment_size:
                raise ValueError('relocation outside its emitted segment')
            cells = set(range(address,address+width))
            if occupied & cells: raise ValueError('overlapping relocations')
            occupied |= cells
            if kind == 0x40: reader.byte()  # low addend: no carry for page moves
            if target in (2,3,4) and kind != 0x20:
                patches.append(segment_offset+address+(kind == 0x80))
    if reader.word(): raise ValueError('dynamic o65 exports are not supported')
    if reader.position != len(data): raise ValueError('trailing o65 bytes')
    header = bytearray(build_executable(image, cpu=1, load_address=base,
        entry_address=entry, bss_size=bss, flags=0))
    header[5] = 2
    offsets = sorted(patches)
    if len(offsets) != len(set(offsets)): raise ValueError('duplicate high-byte patches')
    result = bytes(header)+struct.pack('<H',len(offsets))+b''.join(struct.pack('<H',p) for p in offsets)
    if len(result) > 0xffff: raise ValueError('relocatable file exceeds 16-bit stream limit')
    return result


def relocate_executable(data, base, capacity):
    """Host specification: return a normal installed UDEX view, never mutate input.

    Capacity includes disk staging (header/image/table) as well as image+BSS.
    The caller owns allocation/overlap policy; this function never selects RAM.
    """
    if len(data)<19 or data[:8] != b'UDEX\0\2\1\0':
        raise ValueError('invalid relocatable UDEX header')
    old, size, bss, entry = struct.unpack('<4H',data[8:16])
    if old != CANONICAL_BASE or not size or not old <= entry < old+size:
        raise ValueError('invalid canonical load address, size or entry')
    if old+size+bss>0x10000 or base&255 or not 0<base<0x10000 or capacity<=0 or base+capacity>0x10000:
        raise ValueError('invalid relocation destination/allocation')
    end = 16+size
    if end+2>len(data): raise ValueError('truncated image/relocation count')
    count = int.from_bytes(data[end:end+2],'little')
    if end+2+2*count != len(data): raise ValueError('incorrect relocation table length')
    if max(len(data),size+bss)>capacity: raise ValueError('allocation too small')
    patches = list(struct.unpack('<'+str(count)+'H',data[end+2:]))
    if any(p>=size for p in patches) or any(a>=b for a,b in zip(patches,patches[1:])):
        raise ValueError('out-of-range, duplicate or unsorted relocation')
    image = bytearray(data[16:end])
    delta = (base-old)//256
    for offset in patches: image[offset]=(image[offset]+delta)&255
    return build_executable(image,cpu=1,load_address=base,
        entry_address=base+entry-old,bss_size=bss,flags=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('map',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    try:
        entry=map_exports(args.map.read_text())['_udeks_program_entry'][0]
        result=pack_o65(args.input.read_bytes(),entry)
    except (ValueError,KeyError) as error: parser.exit(1,str(error)+'\n')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(result)


if __name__=='__main__': main()
