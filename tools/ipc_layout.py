#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check the measured IPC reservation against the normal and panic links."""
import json
import re
from pathlib import Path
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
ROOT=Path(__file__).resolve().parents[1]

def main():
    records=[]
    for name in ('udeks-8502','udeks-8502-panic-probe'):
        text=(ROOT/f'build/8502/{name}.map').read_text();symbols=map_exports(text);segments=map_segments(text)
        state=symbols['_udeks_ipc_state'][0]
        module=re.search(r'^ipc\.o:\n((?:[ \t].*\n)+)',text,re.M)[1]
        sizes={label:(int(offset,16),int(size,16)) for label,offset,size in
               re.findall(r'(\w+)\s+Offs=([0-9A-F]+)\s+Size=([0-9A-F]+)',module)}
        if {label:size for label,(_,size) in sizes.items()}!={'CODE':32,'BITMAPCODE':602,'BITMAPSTATE':64}:
            raise ValueError('IPC object exceeds measured reservation')
        for symbol in ('_udeks_ipc_request','_udeks_ipc_retire'):
            if not 0x2006<=symbols[symbol][0]<0x93d0:raise ValueError('IPC veneer outside resident code')
        if state!=segments['BITMAPSTATE'][0]+sizes['BITMAPSTATE'][0] or state+64>segments['BITMAPSTATE'][1]+1:
            raise ValueError('IPC state outside checked startup image')
        if segments['BSS'][1]>=0x93d0 or segments['BITMAPSTATE'][1]>=0xdff0:raise ValueError('IPC overlaps startup or trailer')
        for label,base,end in (('HIGHBSS',0xe1b8,0xe2e0),('VICSHADOW',0xa1e0,0xc11f),('GRAPHICSCODE',0xc00,0x12bf)):
            if segments[label][:2]!=(base,end):raise ValueError('existing reservation changed: '+label)
        records.append(dict(variant=name,resident_free=0x93d0-segments['BSS'][1]-1,
            hidden_free=0xdff0-segments['BITMAPSTATE'][1]-1,state_base=state,state_bytes=64,
            resident_code_bytes=32,hidden_code_bytes=602,endpoints=2,message_bytes=16))
    if len({tuple(sorted((k,v) for k,v in r.items() if k!='variant')) for r in records})!=1:
        raise ValueError('normal/panic IPC layout differs')
    out=ROOT/'build/ipc/layout.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(records,indent=2)+'\n');print(out.read_text(),end='')
if __name__=='__main__':main()
