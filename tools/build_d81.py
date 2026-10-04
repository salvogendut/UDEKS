#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Repack a built UDEKS D71 into a standard 1581 D81 (not a padded D71).

The native boot payload and DOS file byte streams are unchanged. Geometry,
directory chains and BAM allocation are rebuilt. Only closed SEQ/PRG files
are accepted; this is a build tool, not a general disk repair/converter.
Format: https://vice-emu.sourceforge.io/vice_17.html (D81 section).
"""
import argparse
from pathlib import Path
from build_d71 import PAYLOAD_BLOCKS, boot_locations, sector_offset as d71_offset

SIZE = 80 * 40 * 256


def sector_offset(track, sector):
    if not 1 <= track <= 80 or not 0 <= sector < 40:
        raise ValueError('invalid D81 track/sector')
    return ((track-1)*40+sector)*256


def bam_entry(track):
    if not 1 <= track <= 80: raise ValueError('invalid D81 track')
    return sector_offset(40, 1 if track <= 40 else 2)+16+((track-1)%40)*6


def is_free(image, track, sector):
    sector_offset(track, sector)
    return bool(image[bam_entry(track)+1+sector//8] & (1 << (sector%8)))


def mark_used(image, track, sector):
    entry = bam_entry(track)
    if is_free(image, track, sector):
        image[entry] -= 1
        image[entry+1+sector//8] &= ~(1 << (sector%8))


def blank_d81(name=b'UDEKS', disk_id=b'01'):
    if not 1 <= len(name) <= 16 or len(disk_id) != 2:
        raise ValueError('invalid D81 label/id')
    image = bytearray(SIZE)
    header = sector_offset(40, 0)
    image[header:header+4] = bytes((40, 3, 0x44, 0))
    image[header+4:header+29] = name.ljust(18,b'\xa0')+disk_id+b'\xa03D\xa0\xa0'
    for sector, link in ((1,bytes((40,2))), (2,b'\0\xff')):
        pos = sector_offset(40, sector)
        image[pos:pos+8] = link+b'\x44\xbb'+disk_id+b'\xc0\0'
    for track in range(1,81):
        pos = bam_entry(track)
        image[pos:pos+6] = bytes((40,255,255,255,255,255))
    for sector in range(4): mark_used(image,40,sector)
    pos = sector_offset(40,3); image[pos:pos+2] = b'\0\xff'
    return image


def entries(image, offset, track, sector):
    """Bounded chain traversal returning occupied DOS directory entries."""
    seen=set()
    while track:
        pos=offset(track,sector)
        if pos in seen or pos+256>len(image): raise ValueError('invalid directory chain')
        seen.add(pos)
        for slot in range(8):
            entry=pos+2+32*slot
            if image[entry]: yield bytes(image[entry:entry+30])
        track,sector=image[pos:pos+2]


def file_bytes(image, entry, offset):
    track,sector=entry[1:3]; data=bytearray(); seen=set()
    while track:
        pos=offset(track,sector)
        if pos in seen or pos+256>len(image): raise ValueError('invalid file chain')
        seen.add(pos); track,sector=image[pos:pos+2]
        count=254 if track else sector-1
        if not 0<=count<=254: raise ValueError('invalid last-sector length')
        data.extend(image[pos+2:pos+2+count])
    if len(seen)!=int.from_bytes(entry[28:30],'little'):
        raise ValueError('file block count disagrees with chain')
    return bytes(data)


def install_file(image, name, data, *, file_type=0x81):
    if len(image)!=SIZE or file_type not in (0x81,0x82):
        raise ValueError('expected D81 and a closed SEQ/PRG')
    encoded=name.upper().encode('ascii')
    if not 1<=len(encoded)<=16: raise ValueError('invalid filename')
    if any(e[3:19].rstrip(b'\xa0')==encoded for e in entries(image,sector_offset,40,3)):
        raise ValueError('duplicate disk filename')
    blocks=max(1,(len(data)+253)//254)
    free=[(t,s) for t in range(1,81) if t!=40 for s in range(40) if is_free(image,t,s)]
    if len(free)<blocks: raise ValueError('D81 full')
    directory=3; seen=set(); entry=None
    while entry is None:
        if directory in seen: raise ValueError('cyclic directory')
        seen.add(directory); pos=sector_offset(40,directory)
        for slot in range(8):
            if not image[pos+2+32*slot]: entry=pos+2+32*slot; break
        if entry is not None: break
        track,sector=image[pos:pos+2]
        if track:
            if track!=40 or sector<3: raise ValueError('invalid directory link')
            directory=sector
        else:
            sector=next((s for s in range(4,40) if is_free(image,40,s)),None)
            if sector is None: raise ValueError('D81 directory full')
            image[pos:pos+2]=bytes((40,sector)); directory=sector
            pos=sector_offset(40,sector); image[pos:pos+256]=b'\0\xff'+bytes(254)
            mark_used(image,40,sector)
    for index,(track,sector) in enumerate(free[:blocks]):
        pos=sector_offset(track,sector); chunk=data[index*254:(index+1)*254]
        image[pos:pos+2]=bytes(free[index+1]) if index+1<blocks else bytes((0,len(chunk)+1))
        image[pos+2:pos+2+len(chunk)]=chunk
        mark_used(image,track,sector)
    image[entry:entry+30]=bytes((file_type,*free[0]))+encoded.ljust(16,b'\xa0')+bytes(9)+blocks.to_bytes(2,'little')


def build_image(source):
    if len(source)!=349696 or source[:7]!=b'CBM\0\x1c\0\xd4':
        raise ValueError('expected the standard UDEKS native-boot D71')
    pos=d71_offset(18,0)
    image=blank_d81(source[pos+0x90:pos+0xa0].rstrip(b'\xa0'),source[pos+0xa2:pos+0xa4])
    # Native C128 BOOT uses 21 sectors/track across this small boot payload,
    # even with a 1581. Preserve T/S, not byte offsets or linear D81 blocks.
    # Unused sectors 21..39 remain available to ordinary DOS files.
    for track,sector in boot_locations(1+PAYLOAD_BLOCKS):
        source_pos=d71_offset(track,sector)
        pos=sector_offset(track,sector)
        image[pos:pos+256]=source[source_pos:source_pos+256]
        mark_used(image,track,sector)
    for entry in entries(source,d71_offset,18,1):
        install_file(image,entry[3:19].rstrip(b'\xa0').decode('ascii'),
                     file_bytes(source,entry,d71_offset),file_type=entry[0])
    return bytes(image)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path); parser.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.input.resolve()==args.output.resolve(): parser.error('output must not replace source')
    args.output.write_bytes(build_image(args.input.read_bytes()))


if __name__=='__main__': main()
