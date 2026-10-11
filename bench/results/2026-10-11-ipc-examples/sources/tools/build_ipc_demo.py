#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Package independently linked IPC examples on full D71/D81 system copies."""
import hashlib
import json
from pathlib import Path
from add_disk_apps import add_apps
from native_app_layout import fitting_allocations,check_coexistence
ROOT=Path(__file__).resolve().parents[1]

def main():
    out=ROOT/'build/ipc/demo';out.mkdir(parents=True,exist_ok=True)
    programs={name:(ROOT/f'build/ipc/{folder}/{name}.BIN').read_bytes() for name,folder in
              [('IPCSRV','server'),('IPCPING','client')]}
    fits={name.lower():fitting_allocations(image) for name,image in programs.items()}
    fits.update({name:fitting_allocations((ROOT/f'build/user/{name}.udx').read_bytes()) for name in ('xclock','xdraw')})
    orders=check_coexistence(fits)
    digest=lambda data:hashlib.sha256(data).hexdigest()
    report=dict(scope='slice 2 independent IPC SDK/server/client; no kernel change',
        programs={name:dict(sha256=digest(data),fits=fits[name.lower()]) for name,data in programs.items()},
        four_task_launch_orders=orders,disks={},
        d64='Full baseline has 16 free blocks; examples need '+str(sum((len(data)+253)//254 for data in programs.values()))+'; D64 is unchanged')
    for fmt in ('d71','d81'):
        original=(ROOT/f'build/boot/udeks.{fmt}').read_bytes()
        data=add_apps(original,[(name+'.BIN',image) for name,image in programs.items()])
        (out/f'udeks-ipc.{fmt}').write_bytes(data)
        report['disks'][fmt]=dict(source_sha256=digest(original),sha256=digest(data))
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
